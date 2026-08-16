from __future__ import annotations

import datetime as dt
from typing import Any, Mapping

from .aee_adapter import AEEPageResult, _format_source_time, _validate_range_and_page
from .aee_http import AEEDataHTTPError
from .mcs8_http import MCS8DataHTTPClient


class MCS8ReadOnlyDataAdapter:
    """Read-only Class A adapter over the MCS8 native server channel.

    MCS8 native (``/api/GetDevListByGroupId``, ``/api/v1/RecordFileList``,
    ``/api/v1/AlarmList``) is the supported server-side data path that does
    not pass through the aee.jdcloud.com JFE front-end. Device rows come from
    ``GetDevListByGroupId`` and are a **current status snapshot** (``nOnline``
    present), not a historical transition feed.

    The adapter keeps source-level isolation and completeness metadata via the
    shared ``AEEPageResult`` contract so the existing pagination collector and
    ingestion pipeline can be reused unchanged.
    """

    def __init__(self, client: MCS8DataHTTPClient) -> None:
        self._client = client

    def list_device_snapshot(
        self,
    ) -> AEEPageResult:
        """Return the current device status snapshot (all devices).

        ``GetDevListByGroupId`` returns the device rows directly (no paginated
        envelope on this endpoint). ``nOnline`` is the current online state.
        """

        payload = self._client.get_json("/api/GetDevListByGroupId", query={})
        rows = _coerce_rows(payload)
        return AEEPageResult(
            rows=tuple(rows),
            records_total=len(rows),
            page=1,
            page_size=max(1, len(rows)),
            has_more=False,
            invalid_row_count=0,
            quality_flags=("mcs8_device_snapshot",),
        )

    def list_record_files(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        source_timezone: dt.tzinfo,
        time_type: str | int,
        group_with_child: str | int,
        group_id: str | int = 0,
        device_id: str = "",
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
        query: dict[str, str | int] = {
            "st": _format_source_time(start_value, source_timezone),
            "et": _format_source_time(end_value, source_timezone),
            "devId": device_id.strip(),
            "timeType": _required_value(time_type, "time_type"),
            "groupId": _optional(group_id, default="0"),
            "groupWithChild": _required_value(
                group_with_child,
                "group_with_child",
            ),
            "isDeleted": "false",
            "page": page,
            "pagesize": page_size,
        }
        payload = self._client.get_json(
            "/api/v1/RecordFileList",
            query=query,
        )
        return _parse_mcs8_page(
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
        query: dict[str, str | int] = {
            "st": _format_source_time(start_value, source_timezone),
            "et": _format_source_time(end_value, source_timezone),
            "devId": device_id.strip(),
            "timeType": _required_value(time_type, "time_type"),
            "groupId": _optional(group_id, default="0"),
            "groupWithChild": _required_value(
                group_with_child,
                "group_with_child",
            ),
            "page": page,
            "pagesize": page_size,
        }
        payload = self._client.get_json(
            "/api/v1/AlarmList",
            query=query,
        )
        return _parse_mcs8_page(
            payload,
            page=page,
            page_size=page_size,
        )


def _parse_mcs8_page(
    payload: Mapping[str, Any],
    *,
    page: int,
    page_size: int,
) -> AEEPageResult:
    error_code = payload.get("error")
    try:
        error_ok = int(error_code) == 200
    except (TypeError, ValueError):
        error_ok = False
    if not error_ok:
        raise AEEDataHTTPError(
            "MCS8_DATA_UPSTREAM_REJECTED",
            f"MCS8 data endpoint rejected the request (error={error_code})",
        )

    raw_rows = payload.get("data")
    if not isinstance(raw_rows, list):
        raise AEEDataHTTPError(
            "MCS8_DATA_INVALID_RESPONSE",
            "MCS8 data endpoint returned an invalid page",
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


def _coerce_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            dict(row)
            for row in payload
            if isinstance(row, Mapping)
        ]
    if isinstance(payload, Mapping):
        raw = payload.get("data")
        if isinstance(raw, list):
            return [
                dict(row)
                for row in raw
                if isinstance(row, Mapping)
            ]
    raise AEEDataHTTPError(
        "MCS8_DATA_INVALID_RESPONSE",
        "MCS8 GetDevListByGroupId returned an invalid payload",
    )


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


def _optional(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _required_value(value: Any, name: str) -> str:
    text = _optional(value)
    if not text:
        raise ValueError(f"{name} is required")
    return text
