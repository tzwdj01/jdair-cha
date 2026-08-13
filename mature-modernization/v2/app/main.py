from __future__ import annotations

import datetime as dt
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .services.legacy import (
    LegacyClient,
    LegacyPayloadError,
    LegacyTransportError,
)


UTC = dt.timezone.utc
settings = Settings.from_env()
legacy_client = LegacyClient(
    settings.legacy_base_url,
    settings.legacy_timeout_seconds,
)
started_monotonic = time.monotonic()
started_at = dt.datetime.now(UTC)


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
    yield


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
    ready = not required or legacy_status == "ok"
    return envelope(
        request,
        {
            "status": "ready" if ready else "not_ready",
            "dependencies": {
                "legacy_service": {
                    "status": legacy_status,
                    "required": required,
                    "latency_ms": legacy_latency_ms,
                },
                "postgresql": {"status": "not_enabled", "required": False},
                "redis": {"status": "not_enabled", "required": False},
                "mcs8": {"status": "not_enabled", "required": False},
            },
        },
        ok=ready,
        status_code=200 if ready else 503,
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
                }
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
                }
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


@app.get("/api/v2/dashboard/overview")
async def dashboard_overview(request: Request):
    if not settings.feature_dashboard_v2:
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

    cookie = request.headers.get("cookie", "")
    if not cookie:
        return envelope(
            request,
            {
                "code": "authentication_required",
                "message": "An authenticated CHA session is required.",
            },
            ok=False,
            status_code=401,
        )

    try:
        result = await legacy_client.dashboard(cookie)
    except LegacyTransportError:
        return envelope(
            request,
            {
                "code": "legacy_unavailable",
                "message": "The existing CHA data service is unavailable.",
            },
            ok=False,
            status_code=503,
        )

    if result.status_code in {401, 403}:
        return envelope(
            request,
            {
                "code": "authentication_required",
                "message": "The CHA session is missing or expired.",
            },
            ok=False,
            status_code=401,
        )
    if result.status_code != 200:
        return envelope(
            request,
            {
                "code": "legacy_error",
                "message": "The existing CHA data service returned an error.",
            },
            ok=False,
            status_code=502,
        )

    try:
        legacy_data = result.json()
    except LegacyPayloadError:
        return envelope(
            request,
            {
                "code": "legacy_payload_error",
                "message": "The existing CHA dashboard payload is invalid.",
            },
            ok=False,
            status_code=502,
        )

    devices = legacy_data.get("devices", {})
    cities = legacy_data.get("cities", [])
    return envelope(
        request,
        {
            "summary": {
                "devices": {
                    "total": int(devices.get("total", 0) or 0),
                    "online": int(devices.get("online", 0) or 0),
                    "offline": int(devices.get("offline", 0) or 0),
                },
                "cities": cities if isinstance(cities, list) else [],
            },
            "source": {
                "kind": "legacy_compatibility_adapter",
                "latency_ms": round(result.latency_ms, 2),
            },
        },
    )
