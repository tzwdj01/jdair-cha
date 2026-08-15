from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .aee_http import AEEDataHTTPError


MAX_PAGE_SIZE = 10_000


class AEEDataTransport(Protocol):
    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class AEEPageResult:
    rows: tuple[dict[str, Any], ...]
    records_total: int | None
    page: int
    page_size: int
    has_more: bool | None
    invalid_row_count: int
    quality_flags: tuple[str, ...]


class AEEReadOnlyDataAdapter:
    """Endpoint-specific Class A queries over the guarded HTTP transport."""

    def __init__(self, client: AEEDataTransport) -> None:
        self._client = client

    def get_device_tree(self) -> dict[str, Any]:
        return self._client.get_json("/api/v1/ext/DevTree")

    def list_device_online(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        source_timezone: dt.tzinfo,
        enterprise_id: str | int,
        group_id: str | int = 0,
        device_id: str = "",
        keywords: str = "",
        page: int = 1,
        page_size: int = 1_000,
    ) -> AEEPageResult:
        query = _build_common_range_query(
            start=start,
            end=end,
            source_timezone=source_timezone,
            enterprise_id=enterprise_id,
            group_id=group_id,
            device_id=device_id,
            keywords=keywords,
            page=page,
            page_size=page_size,
        )
        payload = self._client.get_json(
            "/api/v1/DevOnlineList",
            query=query,
        )
        return _parse_page_result(
            payload,
            page=page,
            page_size=page_size,
        )

    def list_record_files(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        source_timezone: dt.tzinfo,
        enterprise_id: str | int,
        group_id: str | int = 0,
        device_id: str = "",
        keywords: str = "",
        page: int = 1,
        page_size: int = 1_000,
    ) -> AEEPageResult:
        query = _build_common_range_query(
            start=start,
            end=end,
            source_timezone=source_timezone,
            enterprise_id=enterprise_id,
            group_id=group_id,
            device_id=device_id,
            keywords=keywords,
            page=page,
            page_size=page_size,
        )
        payload = self._client.get_json(
            "/api/v1/RecordFileList",
            query=query,
        )
        return _parse_page_result(
            payload,
            page=page,
            page_size=page_size,
        )

    def list_alarms(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        source_timezone: dt.tzinfo,
        time_type: str | int,
        group_with_child: str | int,
        group_id: str | int = 0,
        device_id: str = "",
        alarm_type: str | int = "",
        alarm_status: str | int = "",
        deal_type: str | int = "",
        deal_status: str | int = "",
        keywords: str = "",
        page: int = 1,
        page_size: int = 1_000,
    ) -> AEEPageResult:
        start_value, end_value = _validate_range_and_page(
            start=start,
            end=end,
            source_timezone=source_timezone,
            page=page,
            page_size=page_size,
        )
        query = {
            "st": _format_source_time(start_value, source_timezone),
            "et": _format_source_time(end_value, source_timezone),
            "timeType": _required_query_value(time_type, "time_type"),
            "groupWithChild": _required_query_value(
                group_with_child,
                "group_with_child",
            ),
            "groupId": _optional_text(group_id, default="0"),
            "devId": _optional_text(device_id),
            "alarmType": _optional_text(alarm_type),
            "alarmStatus": _optional_text(alarm_status),
            "dealType": _optional_text(deal_type),
            "dealStatus": _optional_text(deal_status),
            "keywords": _optional_text(keywords),
            "page": page,
            "pagesize": page_size,
        }
        payload = self._client.get_json(
            "/api/v1/AlarmList",
            query=query,
        )
        return _parse_page_result(
            payload,
            page=page,
            page_size=page_size,
        )


def _build_common_range_query(
    *,
    start: dt.datetime,
    end: dt.datetime,
    source_timezone: dt.tzinfo,
    enterprise_id: str | int,
    group_id: str | int,
    device_id: str,
    keywords: str,
    page: int,
    page_size: int,
) -> dict[str, str | int]:
    start_value, end_value = _validate_range_and_page(
        start=start,
        end=end,
        source_timezone=source_timezone,
        page=page,
        page_size=page_size,
    )

    if enterprise_id is None or isinstance(enterprise_id, bool):
        raise ValueError("enterprise_id is required")
    enterprise = str(enterprise_id).strip()
    if not enterprise:
        raise ValueError("enterprise_id is required")
    return {
        "st": _format_source_time(start_value, source_timezone),
        "et": _format_source_time(end_value, source_timezone),
        "enterId": enterprise,
        "groupId": _optional_text(group_id, default="0"),
        "devId": _optional_text(device_id),
        "keywords": _optional_text(keywords),
        "page": page,
        "pagesize": page_size,
    }


def _validate_range_and_page(
    *,
    start: dt.datetime,
    end: dt.datetime,
    source_timezone: dt.tzinfo,
    page: int,
    page_size: int,
) -> tuple[dt.datetime, dt.datetime]:
    start_value = _require_aware(start, "start")
    end_value = _require_aware(end, "end")
    if end_value <= start_value:
        raise ValueError("end must be after start")
    _validate_source_timezone(source_timezone)
    if page <= 0:
        raise ValueError("page must be positive")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"page_size must be between 1 and {MAX_PAGE_SIZE}"
        )
    return start_value, end_value


def _parse_page_result(
    payload: Mapping[str, Any],
    *,
    page: int,
    page_size: int,
) -> AEEPageResult:
    result_code = payload.get("result")
    try:
        result_ok = int(result_code) == 200
    except (TypeError, ValueError):
        result_ok = False
    if not result_ok:
        raise AEEDataHTTPError(
            "AEE_DATA_UPSTREAM_REJECTED",
            "AEE data endpoint rejected the request",
        )

    raw_rows = payload.get("data")
    if not isinstance(raw_rows, list):
        raise AEEDataHTTPError(
            "AEE_DATA_INVALID_RESPONSE",
            "AEE data endpoint returned an invalid page",
        )

    rows: list[dict[str, Any]] = []
    invalid_row_count = 0
    for row in raw_rows:
        if isinstance(row, Mapping):
            rows.append(dict(row))
        else:
            invalid_row_count += 1

    records_total = _optional_non_negative_int(payload.get("recordsTotal"))
    flags: set[str] = set()
    if records_total is None:
        flags.add("records_total_unknown")
    if invalid_row_count:
        flags.add("invalid_rows_ignored")

    has_more: bool | None = None
    if records_total is not None:
        consumed = (page - 1) * page_size + len(raw_rows)
        has_more = consumed < records_total

    return AEEPageResult(
        rows=tuple(rows),
        records_total=records_total,
        page=page,
        page_size=page_size,
        has_more=has_more,
        invalid_row_count=invalid_row_count,
        quality_flags=tuple(sorted(flags)),
    )


def _format_source_time(
    value: dt.datetime,
    source_timezone: dt.tzinfo,
) -> str:
    return value.astimezone(source_timezone).strftime("%Y-%m-%d %H:%M:%S")


def _require_aware(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _validate_source_timezone(value: dt.tzinfo) -> None:
    probe = dt.datetime(2026, 8, 15, tzinfo=value)
    if probe.utcoffset() is None:
        raise ValueError("source_timezone must be usable")


def _optional_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _optional_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _required_query_value(value: Any, name: str) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError(f"{name} is required")
    return text
