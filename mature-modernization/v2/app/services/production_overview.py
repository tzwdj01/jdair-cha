from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import asdict, is_dataclass
from typing import Any


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class ProductionOverviewService:
    """Compact, read-only overview aggregation over the production store.

    PHASE 6 builds the CHA Overview on top of the already-ingested
    PostgreSQL history. This service projects a small, JSON-safe summary from
    the existing deterministic domain overviews (devices / media / realtime /
    inspections / alarms / locations / data quality) instead of inventing new
    KPI logic. Every value comes from durable rows; coverage stays honest
    (FULL / PARTIAL / EMPTY). A failing domain is reported with
    ``available=False`` instead of aborting the whole overview.
    """

    def __init__(
        self,
        inspection_service: Any,
        record_service: Any,
        *,
        business_timezone: dt.tzinfo = SHANGHAI,
    ) -> None:
        self._inspection_service = inspection_service
        self._record_service = record_service
        self._business_tz = business_timezone

    async def build(
        self,
        *,
        days: int = 1,
        as_of: dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Build the production overview for the trailing ``days`` window."""

        end = _aware(as_of) if as_of is not None else dt.datetime.now(UTC)
        end = end.astimezone(UTC)
        start = end - dt.timedelta(days=max(1, min(days, 30)))

        devices, media, realtime, inspections, alarms, locations, quality = (
            await asyncio.gather(
                self._devices(start, end),
                self._media(start, end),
                self._realtime(start, end),
                self._inspections(start, end),
                self._alarms(start, end),
                self._locations(start, end),
                self._data_quality(start, end),
            )
        )
        return {
            "generated_at": dt.datetime.now(UTC).isoformat().replace(
                "+00:00", "Z"
            ),
            "scope": {
                "start": _iso(start),
                "end": _iso(end),
                "days": max(1, min(days, 30)),
            },
            "devices": devices,
            "media": media,
            "realtime": realtime,
            "inspections": inspections,
            "alarms": alarms,
            "locations": locations,
            "data_quality": quality,
        }

    async def _devices(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._inspection_service is None:
            return _unavailable("inspection_service_not_wired")
        try:
            overview = await self._inspection_service.device_overview(
                start=start,
                end=end,
                requested_window_days=_days(start, end),
            )
            uptime = overview.uptime
            return {
                "available": True,
                "distinct_devices": len(overview.latest_by_device),
                "current_online": overview.current_online_count,
                "current_offline": overview.current_offline_count,
                "current_unknown": overview.current_unknown_count,
                "observed_transitions": sum(
                    device.offline_transition_count
                    for device in uptime.devices
                ),
                "latest_observed_at": _latest_iso(
                    item.latest_occurred_at
                    for item in overview.latest_by_device
                ),
                "coverage": _coverage(overview.coverage),
                "quality_flags": list(uptime.quality_flags),
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))

    async def _media(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._inspection_service is None:
            return _unavailable("inspection_service_not_wired")
        try:
            overview = await self._inspection_service.media_overview(
                start=start,
                end=end,
                requested_window_days=_days(start, end),
            )
            media = overview.media
            return {
                "available": True,
                "files": sum(d.total_files for d in media.devices),
                "video_files": sum(d.video_count for d in media.devices),
                "video_duration_seconds": sum(
                    d.video_duration_seconds for d in media.devices
                ),
                "size_bytes": sum(d.file_size_bytes for d in media.devices),
                "uploading_devices": len(media.devices),
                "latest_uploaded_at": _iso(overview.latest_uploaded_at),
                "no_recent_upload_devices": len(
                    overview.long_no_upload_devices
                ),
                "no_recent_upload_governed": overview.long_no_upload_governed,
                "coverage": _coverage(overview.coverage),
                "quality_flags": list(media.quality_flags),
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))

    async def _realtime(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._inspection_service is None:
            return _unavailable("inspection_service_not_wired")
        try:
            overview = await self._inspection_service.realtime_overview(
                start=start,
                end=end,
                requested_window_days=_days(start, end),
            )
            agg = overview.aggregation
            return {
                "available": True,
                "view_count": agg.event_count,
                "played_count": agg.played_count,
                "first_frame_count": agg.first_frame_count,
                "users": len(agg.users),
                "devices_viewed": len(agg.devices),
                "view_duration_seconds": round(
                    agg.view_duration_seconds, 1
                ),
                "connection_duration_seconds": round(
                    agg.connection_duration_seconds, 1
                ),
                "latest_closed_at": _iso(overview.latest_closed_at),
                "result_counts": _pairs(agg.result_counts),
                "coverage": _coverage(overview.coverage),
                "quality_flags": list(agg.quality_flags),
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))

    async def _inspections(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._record_service is None:
            return _unavailable("record_service_not_wired")
        try:
            metrics = await self._record_service.dashboard_metrics(
                start=start,
                end=end,
            )
            completeness, requested, available, detail = metrics.coverage
            return {
                "available": True,
                "total_count": metrics.total_count,
                "total_duration_seconds": round(
                    metrics.total_duration_seconds, 1
                ),
                "participant_count": metrics.participant_count,
                "aircraft_count": metrics.aircraft_count,
                "flight_count": metrics.flight_count,
                "task_count": metrics.task_count,
                "issue_found_count": metrics.issue_found_count,
                "no_issue_count": metrics.no_issue_count,
                "issue_rate": metrics.issue_rate,
                "issue_type_counts": _pairs(metrics.issue_type_counts),
                "issue_level_counts": _pairs(metrics.issue_level_counts),
                "coverage": {
                    "completeness": completeness,
                    "requested_window_days": requested,
                    "available_coverage_days": available,
                    "detail": detail,
                },
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))

    async def _alarms(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._inspection_service is None:
            return _unavailable("inspection_service_not_wired")
        try:
            overview = await self._inspection_service.alarm_overview(
                start=start,
                end=end,
                requested_window_days=_days(start, end),
            )
            agg = overview.aggregation
            return {
                "available": True,
                "alarm_count": agg.alarm_count,
                "affected_devices": len(agg.devices),
                "top_types": _pairs(agg.alarm_type_counts)[:5],
                "latest_occurred_at": _iso(overview.latest_occurred_at),
                "coverage": _coverage(overview.coverage),
                "quality_flags": list(agg.quality_flags),
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))

    async def _locations(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._inspection_service is None:
            return _unavailable("inspection_service_not_wired")
        try:
            overview = await self._inspection_service.location_overview(
                start=start,
                end=end,
                requested_window_days=_days(start, end),
            )
            agg = overview.aggregation
            return {
                "available": True,
                "located_devices": len(agg.devices),
                "event_count": agg.included_event_count,
                "latest_gps_at": _latest_iso(
                    device.last_gps_at for device in agg.devices
                ),
                "coverage": _coverage(overview.coverage),
                "quality_flags": list(agg.quality_flags),
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))

    async def _data_quality(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> dict[str, Any]:
        if self._inspection_service is None:
            return _unavailable("inspection_service_not_wired")
        try:
            overview = await self._inspection_service.data_quality(
                start=start,
                end=end,
            )
            return {
                "available": True,
                "total_rows": overview.total_rows,
                "tables": [
                    {
                        "table": table.table,
                        "row_count": table.row_count,
                        "latest_at": _iso(table.latest_at),
                        "distinct_device_count": table.distinct_device_count,
                        "rows_with_quality_flags": (
                            table.rows_with_quality_flags
                        ),
                    }
                    for table in overview.tables
                ],
                "top_flags": _pairs(overview.quality_flag_counts)[:15],
                "source_system_counts": _pairs(
                    overview.source_system_counts
                ),
            }
        except Exception as exc:  # pragma: no cover - defensive
            return _unavailable(_error_code(exc))


def _unavailable(code: str) -> dict[str, Any]:
    return {"available": False, "error": code}


def _error_code(exc: Exception) -> str:
    return getattr(exc, "code", None) or type(exc).__name__


def _days(start: dt.datetime, end: dt.datetime) -> int:
    return max(1, round((end - start).total_seconds() / 86400))


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _latest_iso(values: Any) -> str | None:
    candidates = [
        value
        for value in values
        if value is not None
    ]
    if not candidates:
        return None
    return _iso(max(candidates))


def _coverage(coverage: Any) -> dict[str, Any]:
    return {
        "requested_window_days": coverage.requested_window_days,
        "available_coverage_days": coverage.available_coverage_days,
        "completeness": coverage.completeness,
        "coverage_start_date": coverage.coverage_start_date,
        "coverage_end_date": coverage.coverage_end_date,
    }


def _pairs(items: Any) -> list[list[Any]]:
    return [[k, v] for k, v in items]


def _aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value
