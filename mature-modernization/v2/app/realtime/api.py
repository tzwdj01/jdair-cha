from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from ..config import Settings
from ..services.legacy import (
    LegacyClient,
    LegacyPayloadError,
    LegacyTransportError,
)
from .errors import AEEUpstreamError, RealtimeError
from .schemas import AddStreamRequest, CreateSessionRequest
from .session_manager import RealtimeSessionManager


Envelope = Callable[..., JSONResponse]
COOKIE_PREFIX = "cha_rt_"
MAINTENANCE_WXB_SCOPE = "maintenance_wxb"
ASSET_ROOT = Path(__file__).resolve().parents[1] / "static" / "realtime"
VENDOR_ROOT = Path(__file__).resolve().parents[1] / "static" / "vendor"
TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "templates" / "m3_realtime.html"
)


def create_realtime_router(
    settings: Settings,
    legacy_client: LegacyClient,
    manager: RealtimeSessionManager,
    envelope: Envelope,
) -> APIRouter:
    router = APIRouter()

    def disabled(request: Request) -> JSONResponse:
        return envelope(
            request,
            {
                "code": "feature_disabled",
                "feature": "realtime_readonly",
                "message": "M3.1 realtime video is not enabled.",
            },
            ok=False,
            status_code=404,
        )

    def failure(request: Request, exc: RealtimeError) -> JSONResponse:
        return envelope(
            request,
            {"code": exc.code, "message": exc.message},
            ok=False,
            status_code=exc.status_code,
        )

    async def identity(connection: Any) -> tuple[str, str]:
        cookie_header = connection.headers.get("cookie", "")
        session_cookie = connection.cookies.get("jdair_mcs8_session", "")
        if not cookie_header or not session_cookie:
            raise RealtimeError(
                "authentication_required",
                "Please sign in to the existing CHA system first.",
                status_code=401,
            )
        try:
            response = await legacy_client.session(cookie_header)
            payload = response.json()
        except (LegacyTransportError, LegacyPayloadError) as exc:
            raise RealtimeError(
                "authentication_unavailable",
                "The existing CHA login session could not be verified.",
                status_code=503,
            ) from exc
        if (
            response.status_code != 200
            or not isinstance(payload, dict)
            or not payload.get("authenticated")
        ):
            raise RealtimeError(
                "authentication_required",
                "The existing CHA login session is missing or expired.",
                status_code=401,
            )
        owner_key = hashlib.sha256(
            session_cookie.encode("utf-8")
        ).hexdigest()
        owner_name = str(payload.get("username") or "authenticated-user")[:64]
        return owner_key, owner_name

    async def canary_identity(connection: Any) -> tuple[str, str]:
        owner_key, owner_name = await identity(connection)
        if not settings.realtime_canary_user_allowed(owner_name):
            raise RealtimeError(
                "canary_forbidden",
                "This login is not authorized for the realtime Canary.",
                status_code=403,
            )
        return owner_key, owner_name

    def is_maintenance_wxb_device(row: dict[str, Any]) -> bool:
        """Return whether an online device is in the maintenance terminal fleet.

        The Legacy integration presents this fixed fleet as one ``维修部``
        group. The WXB identifier is the source-of-truth membership marker,
        not an arbitrary upstream display label.
        """

        device_id = str(row.get("devId") or "").strip().upper()
        return device_id.startswith("WXB") and bool(row.get("online"))

    def public_device(row: dict[str, Any], *, scope: str) -> dict[str, Any]:
        device_id = str(row.get("devId") or "").strip()
        return {
            "device_id": device_id,
            "name": str(row.get("name") or device_id)[:80],
            "group": (
                "维修部"
                if scope == MAINTENANCE_WXB_SCOPE
                else str(row.get("groupName") or "未分组")[:80]
            ),
            "online": bool(row.get("online")),
        }

    async def require_online_device(
        request: Request,
        device_id: str,
        *,
        scope: str,
    ) -> None:
        try:
            source = await legacy_client.devices(
                request.headers.get("cookie", "")
            )
            payload = source.json()
        except (LegacyTransportError, LegacyPayloadError) as exc:
            raise RealtimeError(
                "device_source_unavailable",
                "The device list is currently unavailable.",
                status_code=503,
            ) from exc
        if source.status_code != 200 or not isinstance(payload, list):
            raise RealtimeError(
                "device_source_unavailable",
                "The device list is currently unavailable.",
                status_code=503,
            )
        match = next(
            (
                row
                for row in payload
                if isinstance(row, dict)
                and str(row.get("devId") or "").strip() == device_id
            ),
            None,
        )
        if match is None:
            raise RealtimeError(
                "device_not_found",
                "The selected realtime device does not exist.",
                status_code=404,
            )
        if not bool(match.get("online")):
            raise RealtimeError(
                "device_offline",
                "The selected realtime device is offline.",
                status_code=409,
            )
        if (
            scope == MAINTENANCE_WXB_SCOPE
            and not is_maintenance_wxb_device(match)
        ):
            raise RealtimeError(
                "device_not_in_scope",
                "The selected device is outside the maintenance realtime scope.",
                status_code=403,
            )

    def require_same_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if not origin:
            return
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if origin.rstrip("/") != expected.rstrip("/"):
            raise RealtimeError(
                "origin_forbidden",
                "The realtime write request origin is not allowed.",
                status_code=403,
            )

    def set_lease_cookie(
        response: JSONResponse,
        request: Request,
        session_id: str,
        lease: str,
    ) -> None:
        cookie_name = COOKIE_PREFIX + session_id
        response.set_cookie(
            cookie_name,
            lease,
            max_age=settings.realtime_session_ttl_seconds,
            path=f"/ws/v2/realtime/{session_id}",
            secure=request.url.scheme == "https",
            httponly=True,
            samesite="strict",
        )

    def websocket_origin_allowed(websocket: WebSocket) -> bool:
        origin = websocket.headers.get("origin", "").rstrip("/")
        if not origin:
            return settings.realtime_allow_missing_ws_origin
        host = websocket.headers.get("host", "")
        if not host:
            return False
        scheme = websocket.url.scheme.replace("wss", "https").replace(
            "ws",
            "http",
        )
        expected = f"{scheme}://{host}".rstrip("/")
        configured = {
            item.rstrip("/") for item in settings.realtime_allowed_origins
        }
        return origin == expected or origin in configured

    @router.get("/api/v2/realtime", response_class=HTMLResponse)
    async def realtime_page(request: Request) -> HTMLResponse:
        if not settings.feature_realtime_readonly:
            return HTMLResponse(
                status_code=404,
                content=(
                    "<!doctype html><meta charset='utf-8'>"
                    "<title>实时视频监察未启用</title>"
                    "<body style='font-family:sans-serif;padding:32px'>"
                    "<h1>实时视频监察尚未启用</h1>"
                    "<p>realtime_readonly 功能开关当前为关闭状态。</p>"
                    "<p><a href='/'>返回现有系统</a></p></body>"
                ),
            )
        try:
            await canary_identity(request)
        except RealtimeError as exc:
            return HTMLResponse(
                status_code=exc.status_code,
                content=(
                    "<!doctype html><meta charset='utf-8'>"
                    "<title>实时视频监察访问受限</title>"
                    "<body style='font-family:sans-serif;padding:32px'>"
                    "<h1>实时视频监察访问受限</h1>"
                    "<p>当前登录用户不在受控 Canary 范围内。</p>"
                    "<p><a href='/'>返回现有系统</a></p></body>"
                ),
            )
        try:
            html = TEMPLATE_PATH.read_text(encoding="utf-8")
        except OSError:
            return HTMLResponse(
                status_code=500,
                content="Realtime inspection template is unavailable.",
            )
        return HTMLResponse(
            html.replace("{{CHA_V2_VERSION}}", settings.version).replace(
                "{{CHA_V2_BUILD}}",
                settings.build,
            )
        )

    @router.get(
        "/api/v2/realtime/assets/realtime.css",
        include_in_schema=False,
    )
    async def realtime_css() -> FileResponse:
        return FileResponse(ASSET_ROOT / "realtime.css", media_type="text/css")

    @router.get(
        "/api/v2/realtime/assets/realtime.js",
        include_in_schema=False,
    )
    async def realtime_js() -> FileResponse:
        return FileResponse(
            ASSET_ROOT / "realtime.js",
            media_type="application/javascript",
        )

    @router.get(
        "/api/v2/realtime/assets/multistream_runtime.js",
        include_in_schema=False,
    )
    async def multistream_runtime_js() -> FileResponse:
        return FileResponse(
            ASSET_ROOT / "multistream_runtime.js",
            media_type="application/javascript",
        )

    @router.get(
        "/api/v2/realtime/assets/mcs8Client.js",
        include_in_schema=False,
    )
    async def mcs8_sdk() -> FileResponse:
        return FileResponse(
            VENDOR_ROOT / "mcs8Client.js",
            media_type="application/javascript",
        )

    @router.get("/api/v2/realtime/devices")
    async def realtime_devices(
        request: Request,
        scope: str = "all",
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            await canary_identity(request)
            if scope not in {"all", MAINTENANCE_WXB_SCOPE}:
                raise RealtimeError(
                    "invalid_device_scope",
                    "The requested realtime device scope is invalid.",
                    status_code=400,
                )
            source = await legacy_client.devices(
                request.headers.get("cookie", "")
            )
            payload = source.json()
            if source.status_code != 200 or not isinstance(payload, list):
                raise RealtimeError(
                    "device_source_unavailable",
                    "The device list is currently unavailable.",
                    status_code=503,
                )
            devices = []
            for row in payload:
                if not isinstance(row, dict):
                    continue
                device_id = str(row.get("devId") or "").strip()
                if not device_id:
                    continue
                if (
                    scope == MAINTENANCE_WXB_SCOPE
                    and not is_maintenance_wxb_device(row)
                ):
                    continue
                devices.append(public_device(row, scope=scope))
            devices.sort(
                key=lambda item: (
                    not item["online"],
                    item["group"],
                    item["name"],
                )
            )
            return envelope(request, {"devices": devices})
        except RealtimeError as exc:
            return failure(request, exc)
        except (LegacyTransportError, LegacyPayloadError):
            return failure(
                request,
                RealtimeError(
                    "device_source_unavailable",
                    "The device list is currently unavailable.",
                    status_code=503,
                ),
            )

    @router.get("/api/v2/realtime/health", include_in_schema=False)
    async def realtime_health(request: Request) -> JSONResponse:
        snapshot = await manager.telemetry_snapshot()
        aee_configured = settings.realtime_aee_is_configured()
        canary_configured = settings.realtime_canary_is_configured()
        configured = settings.realtime_is_configured()
        enabled = settings.feature_realtime_readonly
        manager_ready = bool(snapshot["cleanup_task_running"])
        ready = manager_ready and (not enabled or configured)
        return envelope(
            request,
            {
                "status": "ready" if ready else "not_ready",
                "enabled": enabled,
                "configured": configured,
                "aee_configured": aee_configured,
                "canary_configured": canary_configured,
                "session_manager": (
                    "running" if manager_ready else "not_running"
                ),
                "upstream_probe": "not_performed",
            },
            ok=ready,
            status_code=200 if ready else 503,
        )

    @router.get("/api/v2/realtime/diagnostics")
    async def realtime_diagnostics(request: Request) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            await canary_identity(request)
            snapshot = await manager.telemetry_snapshot()
            return envelope(
                request,
                {
                    "runtime": snapshot,
                    "limits": {
                        "max_streams_per_session": (
                            settings.realtime_max_streams_per_session
                        ),
                        "max_sessions_per_owner": (
                            settings.realtime_max_sessions_per_owner
                        ),
                    },
                    "security": {
                        "credentials_server_side": True,
                        "receive_only": True,
                        "audio_enabled": settings.feature_realtime_audio,
                        "control_enabled": settings.feature_realtime_control,
                    },
                },
            )
        except RealtimeError as exc:
            return failure(request, exc)

    @router.post("/api/v2/realtime/sessions", status_code=201)
    async def create_session(
        request: Request,
        body: CreateSessionRequest | None = None,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, owner_name = await canary_identity(request)
            session, lease = await manager.create_session(
                owner_key=owner_key,
                owner_name=owner_name,
                device_scope=(body.scope if body is not None else "all"),
            )
            response = envelope(
                request,
                session.public(),
                status_code=201,
            )
            set_lease_cookie(
                response,
                request,
                session.session_id,
                lease,
            )
            return response
        except RealtimeError as exc:
            return failure(request, exc)

    @router.get("/api/v2/realtime/sessions/{session_id}")
    async def get_session(
        request: Request,
        session_id: str,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.get_session(
                session_id,
                owner_key=owner_key,
            )
            return envelope(request, session.public())
        except RealtimeError as exc:
            return failure(request, exc)

    @router.post("/api/v2/realtime/sessions/{session_id}/heartbeat")
    async def heartbeat(
        request: Request,
        session_id: str,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.heartbeat(
                session_id,
                owner_key=owner_key,
            )
            return envelope(request, session.public())
        except RealtimeError as exc:
            return failure(request, exc)

    @router.post(
        "/api/v2/realtime/sessions/{session_id}/streams",
        status_code=201,
    )
    async def add_stream(
        request: Request,
        session_id: str,
        body: AddStreamRequest,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.get_session(
                session_id,
                owner_key=owner_key,
            )
            await require_online_device(
                request,
                body.device_id,
                scope=session.device_scope,
            )
            stream = await manager.add_stream(
                session_id,
                owner_key=owner_key,
                device_id=body.device_id,
            )
            session = await manager.get_session(
                session_id,
                owner_key=owner_key,
            )
            return envelope(
                request,
                {
                    "session": session.public(),
                    "stream": stream.public(),
                    "connection": {
                        "control_path": (
                            f"/ws/v2/realtime/{session_id}/control"
                        ),
                        "gateway_path": (
                            f"/ws/v2/realtime/{session_id}/gateway"
                        ),
                        "sdk_path": (
                            "/api/v2/realtime/assets/mcs8Client.js"
                        ),
                        "runtime_path": (
                            "/api/v2/realtime/assets/"
                            "multistream_runtime.js"
                        ),
                        "uid": "cha-realtime",
                        "max_streams": (
                            settings.realtime_max_streams_per_session
                        ),
                    },
                },
                status_code=201,
            )
        except RealtimeError as exc:
            return failure(request, exc)

    @router.delete(
        "/api/v2/realtime/sessions/{session_id}/streams/{stream_id}"
    )
    async def delete_stream(
        request: Request,
        session_id: str,
        stream_id: str,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.delete_stream(
                session_id,
                stream_id,
                owner_key=owner_key,
            )
            return envelope(request, session.public())
        except RealtimeError as exc:
            return failure(request, exc)

    @router.post(
        "/api/v2/realtime/sessions/{session_id}/streams/{stream_id}/audio"
    )
    async def enable_audio(
        request: Request,
        session_id: str,
        stream_id: str,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.enable_audio(
                session_id,
                stream_id,
                owner_key=owner_key,
            )
            return envelope(request, session.public())
        except RealtimeError as exc:
            return failure(request, exc)

    @router.delete(
        "/api/v2/realtime/sessions/{session_id}/streams/{stream_id}/audio"
    )
    async def disable_audio(
        request: Request,
        session_id: str,
        stream_id: str,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.disable_audio(
                session_id,
                stream_id,
                owner_key=owner_key,
            )
            return envelope(request, session.public())
        except RealtimeError as exc:
            return failure(request, exc)

    @router.delete("/api/v2/realtime/sessions/{session_id}")
    async def close_session(
        request: Request,
        session_id: str,
    ) -> JSONResponse:
        if not settings.feature_realtime_readonly:
            return disabled(request)
        try:
            require_same_origin(request)
            owner_key, _ = await canary_identity(request)
            session = await manager.close_session(
                session_id,
                owner_key=owner_key,
            )
            response = envelope(request, session.public())
            response.delete_cookie(
                COOKIE_PREFIX + session_id,
                path=f"/ws/v2/realtime/{session_id}",
                secure=request.url.scheme == "https",
                httponly=True,
                samesite="strict",
            )
            return response
        except RealtimeError as exc:
            return failure(request, exc)

    async def lease_allowed(websocket: WebSocket, session_id: str) -> bool:
        if not websocket_origin_allowed(websocket):
            return False
        try:
            await canary_identity(websocket)
        except RealtimeError:
            return False
        return await manager.validate_lease(
            session_id,
            websocket.cookies.get(COOKIE_PREFIX + session_id),
        )

    @router.websocket("/ws/v2/realtime/{session_id}/control")
    async def realtime_control(
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        if (
            not settings.feature_realtime_readonly
            or not await lease_allowed(websocket, session_id)
        ):
            await websocket.close(code=4403)
            return
        await websocket.accept()
        await manager.attach_control(session_id, websocket)
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    await manager.handle_control_message(
                        session_id,
                        payload,
                    )
        except WebSocketDisconnect:
            pass
        finally:
            await manager.detach_control(session_id, websocket)

    async def relay(
        websocket: WebSocket,
        session_id: str,
        kind: str,
    ) -> None:
        if (
            not settings.feature_realtime_readonly
            or not await lease_allowed(websocket, session_id)
        ):
            await websocket.close(code=4403)
            return
        proxy_host = websocket.headers.get("host", "localhost")
        try:
            await manager.proxy_websocket(
                session_id,
                kind=kind,
                socket=websocket,
                proxy_host=proxy_host,
            )
        except (AEEUpstreamError, RealtimeError):
            try:
                await websocket.close(code=1011)
            except RuntimeError:
                pass

    @router.websocket("/ws/v2/realtime/{session_id}/gateway")
    async def realtime_gateway(
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        await relay(websocket, session_id, "gateway")

    @router.websocket("/ws/v2/realtime/{session_id}/media")
    @router.websocket("/ws/v2/realtime/{session_id}/media/")
    async def realtime_media(
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        await relay(websocket, session_id, "media")

    return router
