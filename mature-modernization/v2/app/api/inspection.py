from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..config import Settings
from ..services.inspection import InspectionDataService


UTC = dt.timezone.utc
Envelope = Callable[..., JSONResponse]


def create_inspection_router(
    settings: Settings,
    service: InspectionDataService | None,
    envelope: Envelope,
) -> APIRouter:
    """Read-only inspection history API over the InspectionStore.

    The endpoints are honest about availability:

    * feature flag off: 404 ``feature_disabled``;
    * feature on but no store wired: 503 ``store_not_configured``;
    * store wired: computed metrics from durable rows, or empty result sets
      with explicit scope when no history exists yet.
    """

    router = APIRouter()

    def disabled(request: Request) -> JSONResponse:
        return envelope(
            request,
            {
                "code": "feature_disabled",
                "feature": "inspection_v2",
                "message": "M4 inspection data center is not enabled.",
            },
            ok=False,
            status_code=404,
        )

    def store_unavailable(request: Request) -> JSONResponse:
        return envelope(
            request,
            {
                "code": "store_not_configured",
                "message": (
                    "No durable inspection store is configured for this "
                    "release."
                ),
            },
            ok=False,
            status_code=503,
        )

    def invalid_scope(request: Request, message: str) -> JSONResponse:
        return envelope(
            request,
            {"code": "invalid_scope", "message": message},
            ok=False,
            status_code=400,
        )

    def parse_scope(
        request: Request,
        *,
        start_raw: str | None,
        end_raw: str | None,
        days: int,
    ) -> tuple[dt.datetime, dt.datetime] | JSONResponse:
        end: dt.datetime | None = None
        if end_raw:
            parsed = _parse_iso(end_raw)
            if parsed is None:
                return invalid_scope(
                    request,
                    "end must be an ISO-8601 datetime.",
                )
            end = parsed
        if end is None:
            end = dt.datetime.now(UTC)

        start: dt.datetime | None = None
        if start_raw:
            parsed = _parse_iso(start_raw)
            if parsed is None:
                return invalid_scope(
                    request,
                    "start must be an ISO-8601 datetime.",
                )
            start = parsed
        if start is None:
            start = end - dt.timedelta(days=max(1, min(days, 90)))
        if start >= end:
            return invalid_scope(request, "start must be before end.")
        return start.astimezone(UTC), end.astimezone(UTC)

    def scope_payload(
        start: dt.datetime,
        end: dt.datetime,
        days: int,
    ) -> dict[str, Any]:
        return {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "days": max(1, min(days, 90)),
        }

    @router.get("/api/v2/inspection/devices")
    async def inspection_devices(
        request: Request,
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        device: str = Query("", max_length=64),
    ) -> JSONResponse:
        if not settings.feature_inspection_v2:
            return disabled(request)
        if service is None:
            return store_unavailable(request)
        scope = parse_scope(
            request,
            start_raw=start,
            end_raw=end,
            days=days,
        )
        if isinstance(scope, JSONResponse):
            return scope
        scope_start, scope_end = scope
        device_ids = _device_ids(device)
        overview = await service.device_overview(
            start=scope_start,
            end=scope_end,
            device_ids=device_ids,
        )
        return envelope(
            request,
            {
                "source": "inspection_store",
                "store_configured": True,
                "scope": scope_payload(scope_start, scope_end, days),
                "overview": _json_safe(overview),
            },
        )

    @router.get("/api/v2/inspection/media")
    async def inspection_media(
        request: Request,
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        device: str = Query("", max_length=64),
    ) -> JSONResponse:
        if not settings.feature_inspection_v2:
            return disabled(request)
        if service is None:
            return store_unavailable(request)
        scope = parse_scope(
            request,
            start_raw=start,
            end_raw=end,
            days=days,
        )
        if isinstance(scope, JSONResponse):
            return scope
        scope_start, scope_end = scope
        overview = await service.media_overview(
            start=scope_start,
            end=scope_end,
            device_ids=_device_ids(device),
        )
        return envelope(
            request,
            {
                "source": "inspection_store",
                "store_configured": True,
                "scope": scope_payload(scope_start, scope_end, days),
                "overview": _json_safe(overview),
            },
        )

    @router.get("/api/v2/inspection/realtime")
    async def inspection_realtime(
        request: Request,
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        device: str = Query("", max_length=64),
        user: str = Query("", max_length=64),
    ) -> JSONResponse:
        if not settings.feature_inspection_v2:
            return disabled(request)
        if service is None:
            return store_unavailable(request)
        scope = parse_scope(
            request,
            start_raw=start,
            end_raw=end,
            days=days,
        )
        if isinstance(scope, JSONResponse):
            return scope
        scope_start, scope_end = scope
        overview = await service.realtime_overview(
            start=scope_start,
            end=scope_end,
            device_ids=_device_ids(device),
            usernames=_ids(user),
        )
        return envelope(
            request,
            {
                "source": "inspection_store",
                "store_configured": True,
                "scope": scope_payload(scope_start, scope_end, days),
                "overview": _json_safe(overview),
            },
        )

    @router.get("/api/v2/inspection/alarms")
    async def inspection_alarms(
        request: Request,
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        device: str = Query("", max_length=64),
    ) -> JSONResponse:
        if not settings.feature_inspection_v2:
            return disabled(request)
        if service is None:
            return store_unavailable(request)
        scope = parse_scope(
            request,
            start_raw=start,
            end_raw=end,
            days=days,
        )
        if isinstance(scope, JSONResponse):
            return scope
        scope_start, scope_end = scope
        overview = await service.alarm_overview(
            start=scope_start,
            end=scope_end,
            device_ids=_device_ids(device),
        )
        return envelope(
            request,
            {
                "source": "inspection_store",
                "store_configured": True,
                "scope": scope_payload(scope_start, scope_end, days),
                "overview": _json_safe(overview),
            },
        )

    @router.get("/api/v2/inspection/locations")
    async def inspection_locations(
        request: Request,
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        device: str = Query("", max_length=64),
    ) -> JSONResponse:
        if not settings.feature_inspection_v2:
            return disabled(request)
        if service is None:
            return store_unavailable(request)
        scope = parse_scope(
            request,
            start_raw=start,
            end_raw=end,
            days=days,
        )
        if isinstance(scope, JSONResponse):
            return scope
        scope_start, scope_end = scope
        overview = await service.location_overview(
            start=scope_start,
            end=scope_end,
            device_ids=_device_ids(device),
        )
        return envelope(
            request,
            {
                "source": "inspection_store",
                "store_configured": True,
                "scope": scope_payload(scope_start, scope_end, days),
                "overview": _json_safe(overview),
            },
        )

    return router


def _parse_iso(value: str) -> dt.datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _device_ids(value: str) -> tuple[str, ...] | None:
    return _ids(value)


def _ids(value: str) -> tuple[str, ...] | None:
    items = tuple(
        item.strip() for item in value.split(",") if item.strip()
    )
    return items or None


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dt.datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
