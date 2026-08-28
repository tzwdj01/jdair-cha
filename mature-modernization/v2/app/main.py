from __future__ import annotations

import datetime as dt
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .api.inspection import create_inspection_router
from .api.inspection_access import InspectionAccess
from .api.inspections import create_inspections_router
from .config import Settings
from .data.store import StoreViewEventSink
from .realtime.api import create_realtime_router
from .realtime.session_manager import RealtimeSessionManager
from .services.dashboard import (
    DashboardAuthenticationError,
    DashboardService,
    DashboardSourceError,
)
from .services.business_candidates import (
    InspectionBusinessCandidateService,
    LegacyBusinessDataClient,
)
from .services.production_overview import ProductionOverviewService
from .services.legacy import (
    LegacyClient,
    LegacyTransportError,
)
from .services.inspection import InspectionDataService
from .services.inspection_readiness import inspection_postgresql_readiness
from .services.inspection_records import InspectionRecordService
from .services.store_factory import (
    build_inspection_record_store,
    build_inspection_store,
)


UTC = dt.timezone.utc
settings = Settings.from_env()
legacy_client = LegacyClient(
    settings.legacy_base_url,
    settings.legacy_timeout_seconds,
)
dashboard_service = DashboardService(legacy_client, settings)
started_monotonic = time.monotonic()
started_at = dt.datetime.now(UTC)
dashboard_template_path = (
    Path(__file__).resolve().parent / "templates" / "m2_dashboard.html"
)
# The inspection store is optional. Production always returns None until a
# durable PostgreSQL store is wired and rehearsed. A non-production deployment
# may explicitly request the process-local memory store for local testing.
inspection_store = build_inspection_store(settings)
view_event_sink = (
    StoreViewEventSink(inspection_store)
    if inspection_store is not None
    else None
)
realtime_manager = RealtimeSessionManager(
    settings,
    view_event_sink=view_event_sink,
)
inspection_service = (
    InspectionDataService(
        inspection_store,
        thresholds=settings.inspection_thresholds,
        business_client=LegacyBusinessDataClient(
            legacy_client,
        ),
    )
    if inspection_store is not None
    else None
)
inspection_record_store = build_inspection_record_store(settings)
inspection_record_service = (
    InspectionRecordService(inspection_record_store)
    if inspection_record_store is not None
    else None
)
production_overview_service = (
    ProductionOverviewService(
        inspection_service,
        inspection_record_service,
    )
    if (
        inspection_service is not None
        and inspection_record_service is not None
    )
    else None
)


def iso_now() -> str:
    return dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")


def envelope(
    request: Request,
    data: Any,
    *,
    ok: bool = True,
    status_code: int = 200,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": ok,
            "data": data,
            "meta": {
                "request_id": request_id,
                "generated_at": iso_now(),
                "service": settings.service_name,
                "version": settings.version,
                "build": settings.build,
            },
        },
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    await realtime_manager.start()
    try:
        yield
    finally:
        await realtime_manager.shutdown()
        closed_store_ids: set[int] = set()
        for store in (inspection_store, inspection_record_store):
            if store is None or id(store) in closed_store_ids:
                continue
            closed_store_ids.add(id(store))
            close = getattr(store, "close", None)
            if callable(close):
                close()


app = FastAPI(
    title="CHA Aviation Inspection API v2",
    description=(
        "Modular compatibility layer for dashboard, realtime video and "
        "future platform governance."
    ),
    version=settings.version,
    lifespan=lifespan,
    docs_url="/api/v2/docs",
    redoc_url=None,
    openapi_url="/api/v2/openapi.json",
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=list(settings.allowed_hosts),
)


async def inspection_identity(request: Request) -> tuple[str | None, str]:
    """Resolve the existing CHA login session; never trust client identity."""

    cookie_header = request.headers.get("cookie", "")
    session_cookie = request.cookies.get("jdair_mcs8_session", "")
    if not cookie_header or not session_cookie:
        raise RuntimeError("authentication_required")
    response = await legacy_client.session(cookie_header)
    payload = response.json()
    if (
        response.status_code != 200
        or not isinstance(payload, dict)
        or not payload.get("authenticated")
    ):
        raise RuntimeError("authentication_required")
    return None, str(payload.get("username") or "authenticated-user")[:128]


inspection_access = InspectionAccess(
    inspection_record_store,
    inspection_identity,
    envelope,
)


async def dashboard_access_error(request: Request) -> JSONResponse | None:
    """Apply the M4 Canary access boundary without changing pre-M4 M2 mode."""

    if not settings.feature_inspection_v2:
        return None
    _identity, error = await inspection_access.require_authorized(request)
    return error


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(
    create_realtime_router(
        settings,
        legacy_client,
        realtime_manager,
        envelope,
    )
)
app.include_router(
    create_inspection_router(
        settings,
        inspection_service,
        envelope,
        realtime_manager,
        inspection_access,
    )
)
if inspection_record_store is not None and inspection_record_service is not None:

    candidate_service = InspectionBusinessCandidateService(
        LegacyBusinessDataClient(legacy_client),
    )

    app.include_router(
        create_inspections_router(
            settings,
            inspection_record_service,
            inspection_record_store,
            envelope,
            inspection_access,
            candidate_service,
        )
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, _: Exception):
    return envelope(
        request,
        {
            "code": "internal_error",
            "message": "The v2 service could not complete the request.",
        },
        ok=False,
        status_code=500,
    )


@app.get("/api/v2/health", include_in_schema=False)
async def health(request: Request):
    return envelope(
        request,
        {
            "status": "ok",
            "environment": settings.environment,
            "uptime_seconds": round(time.monotonic() - started_monotonic, 3),
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
        },
    )


@app.get("/api/v2/health/live", include_in_schema=False)
async def liveness(request: Request):
    return envelope(request, {"status": "alive"})


@app.get("/api/v2/health/ready", include_in_schema=False)
async def readiness(request: Request):
    try:
        result = await legacy_client.health()
        legacy_status = "ok" if result.status_code == 200 else "error"
        legacy_latency_ms = round(result.latency_ms, 2)
    except LegacyTransportError:
        legacy_status = "unavailable"
        legacy_latency_ms = None

    required = settings.legacy_is_required()
    realtime_aee_configured = settings.realtime_aee_is_configured()
    realtime_canary_configured = (
        settings.realtime_canary_is_configured()
    )
    realtime_configured = settings.realtime_is_configured()
    realtime_required = settings.feature_realtime_readonly
    realtime_snapshot = await realtime_manager.telemetry_snapshot()
    realtime_manager_running = bool(
        realtime_snapshot["cleanup_task_running"]
    )
    core_ready = (
        (not required or legacy_status == "ok")
        and (
            not realtime_required
            or (realtime_configured and realtime_manager_running)
        )
    )
    postgresql = await inspection_postgresql_readiness(
        settings,
        inspection_store,
        inspection_record_store,
    )
    inspection_degraded = postgresql["status"] in {
        "misconfigured",
        "unavailable",
    }
    ready_status = (
        "not_ready"
        if not core_ready
        else "degraded"
        if inspection_degraded
        else "ready"
    )
    return envelope(
        request,
        {
            "status": ready_status,
            "dependencies": {
                "legacy_service": {
                    "status": legacy_status,
                    "required": required,
                    "latency_ms": legacy_latency_ms,
                },
                "postgresql": postgresql,
                "redis": {"status": "not_enabled", "required": False},
                "mcs8": {
                    "status": (
                        "configured"
                        if realtime_configured
                        else (
                            "misconfigured"
                            if realtime_required
                            else "not_enabled"
                        )
                    ),
                    "required": realtime_required,
                    "aee_configured": realtime_aee_configured,
                    "canary_configured": realtime_canary_configured,
                    "session_manager": (
                        "running"
                        if realtime_manager_running
                        else "not_running"
                    ),
                    "active_probe": "not_performed",
                },
            },
        },
        # An inspection-PG outage degrades only the M4 data center/workflow;
        # it must not make Legacy-compatible V2 endpoints appear unavailable.
        ok=core_ready,
        status_code=200 if core_ready else 503,
    )


@app.get("/api/v2/health/upstreams", include_in_schema=False)
async def upstream_health(request: Request):
    try:
        result = await legacy_client.health()
        status = "ok" if result.status_code == 200 else "error"
        return envelope(
            request,
            {
                "legacy_service": {
                    "status": status,
                    "http_status": result.status_code,
                    "latency_ms": round(result.latency_ms, 2),
                },
                "mcs8": {
                    "status": (
                        "configured"
                        if settings.realtime_is_configured()
                        else (
                            "misconfigured"
                            if settings.feature_realtime_readonly
                            else "not_enabled"
                        )
                    )
                },
            },
            status_code=200 if status == "ok" else 503,
        )
    except LegacyTransportError:
        return envelope(
            request,
            {
                "legacy_service": {
                    "status": "unavailable",
                    "http_status": None,
                    "latency_ms": None,
                },
                "mcs8": {
                    "status": (
                        "configured"
                        if settings.realtime_is_configured()
                        else (
                            "misconfigured"
                            if settings.feature_realtime_readonly
                            else "not_enabled"
                        )
                    )
                },
            },
            ok=False,
            status_code=503,
        )


@app.get("/api/v2/system/version")
async def version(request: Request):
    return envelope(
        request,
        {
            "service": settings.service_name,
            "version": settings.version,
            "build": settings.build,
            "environment": settings.environment,
        },
    )


@app.get("/api/v2/system/features")
async def features(request: Request):
    return envelope(request, {"features": settings.public_features()})


def feature_disabled(request: Request) -> JSONResponse:
    return envelope(
        request,
        {
            "code": "feature_disabled",
            "feature": "dashboard_v2",
            "message": "The v2 dashboard is not enabled for this release.",
        },
        ok=False,
        status_code=404,
    )


async def dashboard_snapshot(
    request: Request,
    days: int,
    city: str,
    refresh: bool,
) -> JSONResponse:
    if not settings.feature_dashboard_v2:
        return feature_disabled(request)
    access_error = await dashboard_access_error(request)
    if access_error is not None:
        return access_error
    try:
        data = await dashboard_service.snapshot(
            request.headers.get("cookie", ""),
            days=days,
            city=city,
            force=refresh,
        )
    except DashboardAuthenticationError:
        return envelope(
            request,
            {
                "code": "authentication_required",
                "message": "请先登录现有 CHA 系统，再打开 M2 态势看板。",
                "login_url": "/",
            },
            ok=False,
            status_code=401,
        )
    except DashboardSourceError as exc:
        return envelope(
            request,
            {
                "code": "dashboard_source_unavailable",
                "message": "设备数据源当前不可用，且没有可用缓存。",
                "detail": str(exc)[:180],
            },
            ok=False,
            status_code=503,
        )
    return envelope(request, data)


@app.get("/api/v2/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not settings.feature_dashboard_v2:
        return HTMLResponse(
            status_code=404,
            content=(
                "<!doctype html><meta charset='utf-8'>"
                "<title>M2 看板未启用</title>"
                "<body style='font-family:sans-serif;padding:32px'>"
                "<h1>M2 态势看板尚未启用</h1>"
                "<p>当前版本的 dashboard_v2 功能开关处于关闭状态。</p>"
                "<p><a href='/'>返回现有系统</a></p></body>"
            ),
        )
    access_error = await dashboard_access_error(request)
    if access_error is not None:
        return access_error
    try:
        html = dashboard_template_path.read_text(encoding="utf-8")
    except OSError:
        return HTMLResponse(
            status_code=500,
            content="M2 dashboard template is unavailable.",
        )
    return HTMLResponse(
        content=html.replace("{{CHA_V2_VERSION}}", settings.version).replace(
            "{{CHA_V2_BUILD}}",
            settings.build,
        )
    )


@app.get("/api/v2/dashboard/overview")
async def dashboard_overview(
    request: Request,
    days: int = Query(3, ge=1, le=30),
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, days, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    # PHASE 6: additive production PostgreSQL overview (backward compatible;
    # existing M2 keys are preserved verbatim).
    data["production_overview"] = (
        await _build_production_overview(days)
        if production_overview_service is not None
        else {"available": False, "error": "store_not_configured"}
    )
    return envelope(request, data)


@app.get("/api/v2/dashboard/production-overview")
async def dashboard_production_overview(
    request: Request,
    days: int = Query(1, ge=1, le=30),
):
    access_error = await dashboard_access_error(request)
    if access_error is not None:
        return access_error
    if production_overview_service is None:
        return envelope(
            request,
            {"available": False, "error": "store_not_configured"},
            ok=False,
            status_code=503,
        )
    overview = await _build_production_overview(days)
    return envelope(request, overview)


async def _build_production_overview(days: int) -> dict[str, Any]:
    assert production_overview_service is not None
    try:
        return await production_overview_service.build(days=days)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "available": False,
            "error": type(exc).__name__,
        }


@app.get("/api/v2/dashboard/device-trend")
async def dashboard_device_trend(
    request: Request,
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, 3, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    return envelope(
        request,
        {
            "mode": "sampled_snapshot",
            "device_status": data["device_status"],
            "device_trend": data["device_trend"],
        },
    )


@app.get("/api/v2/dashboard/video-trend")
async def dashboard_video_trend(
    request: Request,
    days: int = Query(3, ge=1, le=30),
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, days, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    return envelope(
        request,
        {"scope": data["scope"], "video_trend": data["video_trend"]},
    )


@app.get("/api/v2/dashboard/geography")
async def dashboard_geography(
    request: Request,
    days: int = Query(3, ge=1, le=30),
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, days, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    return envelope(
        request,
        {
            "scope": data["scope"],
            "geography": data["geography"],
            "map_points": data["map_points"],
        },
    )


@app.get("/api/v2/dashboard/coverage")
async def dashboard_coverage(
    request: Request,
    days: int = Query(3, ge=1, le=30),
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, days, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    return envelope(request, data["coverage"])


@app.get("/api/v2/dashboard/exceptions")
async def dashboard_exceptions(
    request: Request,
    days: int = Query(3, ge=1, le=30),
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, days, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    return envelope(request, data["exceptions"])


@app.get("/api/v2/dashboard/freshness")
async def dashboard_freshness(
    request: Request,
    days: int = Query(3, ge=1, le=30),
    city: str = Query("", max_length=32),
    refresh: bool = Query(False),
):
    response = await dashboard_snapshot(request, days, city, refresh)
    if response.status_code != 200:
        return response
    data = json.loads(response.body)["data"]
    return envelope(
        request,
        {"scope": data["scope"], "freshness": data["freshness"]},
    )
