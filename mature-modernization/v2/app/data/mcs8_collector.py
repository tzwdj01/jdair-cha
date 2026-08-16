from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any, Mapping

from .aee_http import AEEDataHTTPError
from .device_snapshot import MCS8DeviceSnapshotProcessor
from .mcs8_adapter import MCS8ReadOnlyDataAdapter
from .normalization import (
    normalize_alarm_events,
    normalize_mcs8_device_snapshot,
    normalize_media_files,
)
from .pagination import CollectedSource, collect_aee_pages
from .store import InspectionStore


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
logger = logging.getLogger("uvicorn.error.cha.inspection.mcs8_collector")


class MCS8InspectionCollector:
    """Collect MCS8 native inspection rows using snapshot semantics.

    DEVICE uses the current-status snapshot (``GetDevListByGroupId`` ->
    ``normalize_mcs8_device_snapshot`` -> ``MCS8DeviceSnapshotProcessor``),
    which never fabricates native transition events. MEDIA and ALARM reuse the
    page collector against the MCS8 native endpoints.

    Each source is fail-closed and fail-isolated: a failure in one source
    yields a ``CollectedSource`` with ``status="error"`` instead of aborting
    the other sources.
    """

    def __init__(
        self,
        adapter: MCS8ReadOnlyDataAdapter,
        store: InspectionStore,
        *,
        source_timezone: dt.tzinfo = SHANGHAI,
        group_id: str | int = 0,
        page_size: int = 1_000,
        max_pages: int = 100,
        max_records: int = 100_000,
        time_type: str | int = 0,
        group_with_child: str | int = 0,
        include_alarms: bool = True,
    ) -> None:
        if page_size <= 0 or max_pages <= 0 or max_records <= 0:
            raise ValueError("page_size/max_pages/max_records must be positive")
        self._adapter = adapter
        self._store = store
        self._source_timezone = source_timezone
        self._group_id = group_id
        self._page_size = page_size
        self._max_pages = max_pages
        self._max_records = max_records
        self._time_type = time_type
        self._group_with_child = group_with_child
        self._include_alarms = include_alarms

    def _collect_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Mapping[str, CollectedSource]:
        start_utc = _aware_utc(start, "start")
        end_utc = _aware_utc(end, "end")
        if end_utc <= start_utc:
            raise ValueError("end must be after start")
        collected_at = dt.datetime.now(UTC)

        result: dict[str, CollectedSource] = {
            "media_files": self._collect_media(
                start_utc,
                end_utc,
                collected_at,
            ),
        }
        if self._include_alarms:
            result["alarms"] = self._collect_alarms(
                start_utc,
                end_utc,
                collected_at,
            )
        return result

    def _collect_media(
        self,
        start: dt.datetime,
        end: dt.datetime,
        collected_at: dt.datetime,
    ) -> CollectedSource:
        try:
            collection = collect_aee_pages(
                lambda page, page_size: self._adapter.list_record_files(
                    start=start,
                    end=end,
                    source_timezone=self._source_timezone,
                    time_type=self._time_type,
                    group_with_child=self._group_with_child,
                    group_id=self._group_id,
                    device_id="",
                    page=page,
                    page_size=page_size,
                ),
                page_size=self._page_size,
                max_pages=self._max_pages,
                max_records=self._max_records,
            )
        except AEEDataHTTPError as exc:
            logger.warning(
                "mcs8_source_collection_failed source=media_files error_code=%s",
                exc.code,
            )
            return CollectedSource.failed("media_files", exc.code)
        except Exception:
            logger.exception(
                "mcs8_source_collection_failed source=media_files",
            )
            return CollectedSource.failed(
                "media_files",
                "MCS8_SOURCE_COLLECTION_FAILED",
            )
        normalized = normalize_media_files(
            collection.rows,
            source_timezone=self._source_timezone,
            observed_at=collected_at,
            ingested_at=collected_at,
            source_system="mcs8",
        )
        return CollectedSource(
            source="media_files",
            rows=tuple(normalized.files),
            records_total=collection.records_total,
            pages_fetched=collection.pages_fetched,
            fetched_source_count=collection.fetched_source_count,
            invalid_row_count=(
                collection.invalid_row_count + normalized.invalid_row_count
            ),
            duplicate_source_id_count=collection.duplicate_source_id_count,
            complete=collection.complete,
            quality_flags=tuple(
                sorted(
                    set(collection.quality_flags)
                    | set(normalized.quality_flags)
                    | {"source_system=mcs8"}
                )
            ),
            status="ok",
            error_code=None,
            last_successful_at=collected_at,
        )

    def _collect_alarms(
        self,
        start: dt.datetime,
        end: dt.datetime,
        collected_at: dt.datetime,
    ) -> CollectedSource:
        try:
            collection = collect_aee_pages(
                lambda page, page_size: self._adapter.list_alarms(
                    start=start,
                    end=end,
                    source_timezone=self._source_timezone,
                    time_type=self._time_type,
                    group_with_child=self._group_with_child,
                    group_id=self._group_id,
                    device_id="",
                    page=page,
                    page_size=page_size,
                ),
                page_size=self._page_size,
                max_pages=self._max_pages,
                max_records=self._max_records,
            )
        except AEEDataHTTPError as exc:
            logger.warning(
                "mcs8_source_collection_failed source=alarms error_code=%s",
                exc.code,
            )
            return CollectedSource.failed("alarms", exc.code)
        except Exception:
            logger.exception(
                "mcs8_source_collection_failed source=alarms",
            )
            return CollectedSource.failed(
                "alarms",
                "MCS8_SOURCE_COLLECTION_FAILED",
            )
        normalized = normalize_alarm_events(
            collection.rows,
            source_timezone=self._source_timezone,
            observed_at=collected_at,
            ingested_at=collected_at,
            source_system="mcs8",
        )
        return CollectedSource(
            source="alarms",
            rows=tuple(normalized.events),
            records_total=collection.records_total,
            pages_fetched=collection.pages_fetched,
            fetched_source_count=collection.fetched_source_count,
            invalid_row_count=(
                collection.invalid_row_count + normalized.invalid_row_count
            ),
            duplicate_source_id_count=collection.duplicate_source_id_count,
            complete=collection.complete,
            quality_flags=tuple(
                sorted(
                    set(collection.quality_flags)
                    | set(normalized.quality_flags)
                    | {"source_system=mcs8"}
                )
            ),
            status="ok",
            error_code=None,
            last_successful_at=collected_at,
        )

    async def collect(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Mapping[str, CollectedSource]:
        return await asyncio.to_thread(self._collect_sync, start, end)

    async def collect_device_snapshot(
        self,
        *,
        observed_at: dt.datetime | None = None,
    ) -> CollectedSource:
        """Collect the current device status snapshot and persist transitions.

        This is a snapshot, not a windowed event feed: it normalizes the
        current device states and asks ``MCS8DeviceSnapshotProcessor`` to
        compare against the store's latest known state so only initial
        observations and polling-observed transitions are stored.
        """

        collected_at = observed_at or dt.datetime.now(UTC)
        try:
            snapshot = await asyncio.to_thread(
                self._adapter.list_device_snapshot
            )
        except AEEDataHTTPError as exc:
            logger.warning(
                "mcs8_source_collection_failed source=device_status error_code=%s",
                exc.code,
            )
            return CollectedSource.failed("device_status", exc.code)
        except Exception:
            logger.exception(
                "mcs8_source_collection_failed source=device_status",
            )
            return CollectedSource.failed(
                "device_status",
                "MCS8_SOURCE_COLLECTION_FAILED",
            )

        normalized = normalize_mcs8_device_snapshot(
            snapshot.rows,
            observed_at=collected_at,
            ingested_at=collected_at,
        )
        processor = MCS8DeviceSnapshotProcessor(self._store)
        result = await processor.process_snapshot(
            normalized.events,
            source_system="mcs8",
        )
        stored = await processor.store_result(result)
        return CollectedSource(
            source="device_status",
            rows=tuple(result.events_to_store),
            records_total=snapshot.records_total,
            pages_fetched=1,
            fetched_source_count=len(snapshot.rows),
            invalid_row_count=snapshot.invalid_row_count + normalized.invalid_row_count,
            duplicate_source_id_count=0,
            complete=snapshot.has_more is False,
            quality_flags=tuple(
                sorted(
                    set(snapshot.quality_flags)
                    | set(normalized.quality_flags)
                    | set(result.quality_flags)
                    | {"source_system=mcs8"}
                )
            ),
            status="ok",
            error_code=None,
            last_successful_at=collected_at,
        )


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
