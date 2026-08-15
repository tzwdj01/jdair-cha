from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Mapping

from .aee_adapter import AEEReadOnlyDataAdapter
from .pagination import CollectedSource, collect_aee_pages


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class AEEInspectionCollector:
    """Collect AEE inspection rows for a window using the adapter contracts.

    This is the AEE-specific link in the ingestion pipeline. It composes only
    already-defined, evidence-based contracts (``AEEReadOnlyDataAdapter`` plus
    ``collect_aee_pages``) and preserves completeness metadata via
    ``CollectedSource``. It never assumes authentication behavior: the token
    provider is owned by the injected adapter's transport.

    Alarm collection requires explicit ``time_type`` and ``group_with_child``
    selectors. They are never guessed: when absent, alarms are simply not
    collected.
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
        time_type: str | int | None = None,
        group_with_child: str | int | None = None,
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

    async def collect(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Mapping[str, CollectedSource]:
        return await asyncio.to_thread(self._collect_sync, start, end)

    def _collect_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Mapping[str, CollectedSource]:
        start_utc = _aware_utc(start, "start")
        end_utc = _aware_utc(end, "end")
        if end_utc <= start_utc:
            raise ValueError("end must be after start")

        device = collect_aee_pages(
            lambda page, page_size: self._adapter.list_device_online(
                start=start_utc,
                end=end_utc,
                source_timezone=self._source_timezone,
                enterprise_id=self._enterprise_id,
                group_id=self._group_id,
                page=page,
                page_size=page_size,
            ),
            page_size=self._page_size,
            max_pages=self._max_pages,
            max_records=self._max_records,
        )
        files = collect_aee_pages(
            lambda page, page_size: self._adapter.list_record_files(
                start=start_utc,
                end=end_utc,
                source_timezone=self._source_timezone,
                enterprise_id=self._enterprise_id,
                group_id=self._group_id,
                page=page,
                page_size=page_size,
            ),
            page_size=self._page_size,
            max_pages=self._max_pages,
            max_records=self._max_records,
        )
        result: dict[str, CollectedSource] = {
            "device_status": CollectedSource.from_collection(
                "device_status",
                device,
            ),
            "media_files": CollectedSource.from_collection(
                "media_files",
                files,
            ),
        }
        if (
            self._time_type is not None
            and self._group_with_child is not None
        ):
            alarms = collect_aee_pages(
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
                page_size=self._page_size,
                max_pages=self._max_pages,
                max_records=self._max_records,
            )
            result["alarms"] = CollectedSource.from_collection(
                "alarms",
                alarms,
            )
        return result


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
