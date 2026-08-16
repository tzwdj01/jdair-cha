from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any, Mapping

from .aee_adapter import AEEReadOnlyDataAdapter
from .aee_http import AEEDataHTTPError
from .pagination import CollectedSource, collect_aee_pages


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
logger = logging.getLogger("uvicorn.error.cha.inspection.collector")


class AEEInspectionCollector:
    """Collect AEE inspection rows for a window using the adapter contracts.

    This is the AEE-specific link in the ingestion pipeline. It composes only
    already-defined, evidence-based contracts (``AEEReadOnlyDataAdapter`` plus
    ``collect_aee_pages``) and preserves completeness metadata via
    ``CollectedSource``. It never assumes authentication behavior: the token
    provider is owned by the injected adapter's transport.

    ``time_type`` and ``group_with_child`` are required for RecordFileList
    collection, matching the live-verified request shape (the page sends 0/0).
    Alarm collection is opt-in via ``include_alarms``; alarms are never
    collected unless explicitly requested.

    Each source is collected independently (fail-closed, fail-isolated): a
    failure in one source yields a ``CollectedSource`` with
    ``status="error"`` and an ``error_code`` instead of aborting the other
    sources. The scheduler report exposes the per-source status.
    """

    def __init__(
        self,
        adapter: AEEReadOnlyDataAdapter,
        *,
        enterprise_id: str | int,
        source_timezone: dt.tzinfo = SHANGHAI,
        group_id: str | int = 0,
        page_size: int = 1_000,
        max_pages: int = 100,
        max_records: int = 100_000,
        time_type: str | int,
        group_with_child: str | int,
        time_selector: str | int | None = None,
        is_deleted: bool = False,
        include_alarms: bool = False,
    ) -> None:
        if enterprise_id is None or isinstance(enterprise_id, bool):
            raise ValueError("enterprise_id is required")
        if page_size <= 0 or max_pages <= 0 or max_records <= 0:
            raise ValueError("page_size/max_pages/max_records must be positive")
        self._adapter = adapter
        self._enterprise_id = enterprise_id
        self._source_timezone = source_timezone
        self._group_id = group_id
        self._page_size = page_size
        self._max_pages = max_pages
        self._max_records = max_records
        self._time_type = time_type
        self._group_with_child = group_with_child
        self._time_selector = time_selector
        self._is_deleted = is_deleted
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
            "device_status": self._collect_source(
                "device_status",
                collected_at,
                lambda page, page_size: self._adapter.list_device_online(
                    start=start_utc,
                    end=end_utc,
                    source_timezone=self._source_timezone,
                    enterprise_id=self._enterprise_id,
                    group_id=self._group_id,
                    page=page,
                    page_size=page_size,
                ),
            ),
            "media_files": self._collect_source(
                "media_files",
                collected_at,
                lambda page, page_size: self._adapter.list_record_files(
                    start=start_utc,
                    end=end_utc,
                    source_timezone=self._source_timezone,
                    time_type=self._time_type,
                    group_with_child=self._group_with_child,
                    group_id=self._group_id,
                    device_id="",
                    time_selector=self._time_selector,
                    is_deleted=self._is_deleted,
                    page=page,
                    page_size=page_size,
                ),
            ),
        }
        if self._include_alarms:
            result["alarms"] = self._collect_source(
                "alarms",
                collected_at,
                lambda page, page_size: self._adapter.list_alarms(
                    start=start_utc,
                    end=end_utc,
                    source_timezone=self._source_timezone,
                    time_type=self._time_type,
                    group_with_child=self._group_with_child,
                    group_id=self._group_id,
                    page=page,
                    page_size=page_size,
                ),
            )
        return result

    def _collect_source(
        self,
        source: str,
        collected_at: dt.datetime,
        fetch_page,
    ) -> CollectedSource:
        try:
            collection = collect_aee_pages(
                fetch_page,
                page_size=self._page_size,
                max_pages=self._max_pages,
                max_records=self._max_records,
            )
        except AEEDataHTTPError as exc:
            logger.warning(
                "aee_source_collection_failed source=%s error_code=%s",
                source,
                exc.code,
            )
            return CollectedSource.failed(source, exc.code)
        except Exception:
            logger.exception(
                "aee_source_collection_failed source=%s",
                source,
            )
            return CollectedSource.failed(
                source,
                "AEE_SOURCE_COLLECTION_FAILED",
            )
        return CollectedSource.from_collection(
            source,
            collection,
            last_successful_at=collected_at,
        )

    async def collect(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Mapping[str, CollectedSource]:
        return await asyncio.to_thread(self._collect_sync, start, end)


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
