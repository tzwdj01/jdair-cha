from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "mature-modernization" / "v2"
sys.path.insert(0, str(V2_ROOT))

from app.config import Settings  # noqa: E402
from app.realtime.aee_adapter import (  # noqa: E402
    AEEAdapter,
    MEDIA_REQUEST_METHODS,
)
from app.realtime.errors import AEEUpstreamError  # noqa: E402


COOKIE_NAME = "cha_m32a_probe"
SDK_PATH = V2_ROOT / "app" / "static" / "vendor" / "mcs8Client.js"


class ProbeAEEAdapter(AEEAdapter):
    """Isolated, local-only adapter used to measure actual AEE multi-stream behavior."""

    def __init__(
        self,
        session_id: str,
        settings: Settings,
        devices: set[str],
    ) -> None:
        super().__init__(session_id, settings)
        self.devices = devices
        self.monitors: set[str] = set()
        self.connection_totals = {"gateway": 0, "media": 0}
        self.connection_current = {"gateway": 0, "media": 0}
        self.request_counts: dict[str, int] = {}
        self.consumers: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []

    async def proxy(
        self,
        kind: str,
        client: WebSocket,
        *,
        proxy_host: str,
    ) -> None:
        self.connection_totals[kind] += 1
        self.connection_current[kind] += 1
        self._event("proxy_connected", kind=kind)
        try:
            await super().proxy(kind, client, proxy_host=proxy_host)
        finally:
            self.connection_current[kind] = max(
                0,
                self.connection_current[kind] - 1,
            )
            self._event("proxy_disconnected", kind=kind)

    def _validate_client_message(self, kind: str, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            raise AEEUpstreamError(
                "AEE_SIGNAL_INVALID",
                "Invalid AEE signaling JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise AEEUpstreamError(
                "AEE_SIGNAL_INVALID",
                "Invalid AEE signaling payload",
            )
        if payload.get("response") is True:
            return
        if payload.get("request") is not True:
            raise AEEUpstreamError(
                "AEE_COMMAND_FORBIDDEN",
                "Unsupported AEE signaling message",
            )

        method = str(payload.get("method") or "")
        if kind == "gateway":
            raise AEEUpstreamError(
                "AEE_COMMAND_FORBIDDEN",
                f"Gateway client request is not allowed: {method[:64]}",
            )
        if method not in MEDIA_REQUEST_METHODS:
            raise AEEUpstreamError(
                "AEE_COMMAND_FORBIDDEN",
                f"Media client request is not allowed: {method[:64]}",
            )
        self.request_counts[method] = self.request_counts.get(method, 0) + 1

        data = payload.get("data")
        if method == "createWebRtcTransport":
            if not isinstance(data, dict) or not (
                data.get("consuming") is True
                and data.get("producing") is False
            ):
                raise AEEUpstreamError(
                    "AEE_MEDIA_DIRECTION_FORBIDDEN",
                    "Only receive-only WebRTC transports are allowed",
                )
        elif method == "getRouterRtpCapabilities":
            if not isinstance(data, dict) or data.get("roomId") != "mcs8_admin":
                raise AEEUpstreamError(
                    "AEE_ROOM_FORBIDDEN",
                    "Only the mcs8_admin media room is allowed",
                )
        elif method in {"mediaMonitor", "closeMediaMonitor"}:
            if not isinstance(data, dict):
                raise AEEUpstreamError(
                    "AEE_VIDEO_REQUEST_INVALID",
                    "The AEE video request is invalid",
                )
            device_id = str(data.get("devId") or "")
            if (
                data.get("kind") != "video"
                or data.get("streamType") not in {2, "2"}
                or device_id not in self.devices
            ):
                raise AEEUpstreamError(
                    "AEE_VIDEO_REQUEST_FORBIDDEN",
                    "Only explicitly selected live video streams are allowed",
                )
            if method == "mediaMonitor":
                if device_id in self.monitors:
                    raise AEEUpstreamError(
                        "AEE_DUPLICATE_MONITOR",
                        "The device already has an active monitor",
                    )
                self.monitors.add(device_id)
                self._event("monitor_open", device_id=device_id)
            else:
                self.monitors.discard(device_id)
                self._event("monitor_close", device_id=device_id)

    async def _relay_messages(
        self,
        kind: str,
        client: WebSocket,
        upstream: Any,
        proxy_host: str,
    ) -> None:
        async def client_to_upstream() -> None:
            while True:
                message = await client.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                if message.get("text") is not None:
                    text = message["text"]
                    self._validate_client_message(kind, text)
                    await upstream.send(text)
                elif message.get("bytes") is not None:
                    raise AEEUpstreamError(
                        "AEE_BINARY_COMMAND_FORBIDDEN",
                        "Binary AEE signaling is not allowed",
                    )

        async def upstream_to_client() -> None:
            async for message in upstream:
                if isinstance(message, str):
                    self._observe_upstream(kind, message)
                    if kind == "gateway":
                        message = self._capture_and_rewrite_gateway(
                            message,
                            proxy_host,
                        )
                    await client.send_text(message)
                else:
                    await client.send_bytes(message)

        tasks = {
            asyncio.create_task(client_to_upstream()),
            asyncio.create_task(upstream_to_client()),
        }
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            exception = task.exception()
            if exception is not None:
                raise exception

    def _observe_upstream(self, kind: str, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return
        if kind != "media":
            return
        method = str(payload.get("method") or "")
        if method:
            self._event("upstream_method", method=method)
        if method != "newConsumer":
            return
        data = payload.get("data")
        if not isinstance(data, dict):
            return
        consumer_id = str(data.get("id") or "")
        if not consumer_id:
            return
        app_data = data.get("appData")
        device_id = ""
        transport_id = ""
        if isinstance(app_data, dict):
            device_id = str(
                app_data.get("devId")
                or data.get("deviceId")
                or data.get("peerId")
                or ""
            )
            transport_id = str(app_data.get("transportId") or "")
        self.consumers[consumer_id] = {
            "consumer_id": consumer_id,
            "device_id": device_id,
            "producer_id": str(data.get("producerId") or ""),
            "transport_id": transport_id,
            "kind": str(data.get("kind") or ""),
        }
        self._event(
            "consumer_created",
            device_id=device_id,
            consumer_id=consumer_id,
            transport_id=transport_id,
        )

    def _event(self, event: str, **data: Any) -> None:
        self.events.append(
            {
                "at_ms": round(time.time() * 1000),
                "event": event,
                **data,
            }
        )
        if len(self.events) > 300:
            del self.events[:100]

    def metrics(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "allowed_devices": sorted(self.devices),
            "active_monitors": sorted(self.monitors),
            "connection_totals": dict(self.connection_totals),
            "connection_current": dict(self.connection_current),
            "request_counts": dict(self.request_counts),
            "observed_consumer_count": len(self.consumers),
            "consumers": list(self.consumers.values()),
            "events": list(self.events),
        }


settings = Settings.from_env()
devices = {
    item.strip()
    for item in os.getenv("CHA_M32A_DEVICES", "").split(",")
    if item.strip()
}
if not devices:
    raise RuntimeError("CHA_M32A_DEVICES must name the explicitly approved probe devices")

app = FastAPI(title="CHA M3.2A isolated multi-stream probe")
sessions: dict[str, tuple[str, ProbeAEEAdapter]] = {}


def require_local(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="local probe only")


def require_lease(session_id: str, lease: str | None) -> ProbeAEEAdapter:
    record = sessions.get(session_id)
    if record is None or not lease or not secrets.compare_digest(record[0], lease):
        raise HTTPException(status_code=403, detail="invalid probe lease")
    return record[1]


@app.get("/probe", response_class=HTMLResponse)
async def probe_page(request: Request) -> HTMLResponse:
    require_local(request)
    return HTMLResponse(
        """<!doctype html>
<meta charset="utf-8">
<title>CHA M3.2A isolated AEE probe</title>
<style>
body{font-family:system-ui;background:#07121f;color:#dbeafe;margin:0;padding:16px}
#grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.tile{background:#0f2134;border:1px solid #29445e;padding:8px;border-radius:8px}
video{width:100%;aspect-ratio:16/9;background:#000;object-fit:contain}
pre{white-space:pre-wrap;font-size:12px}
</style>
<h1>M3.2A isolated AEE multi-stream probe</h1>
<div id="state">idle</div><div id="grid"></div><pre id="log"></pre>
<script src="/probe/mcs8Client.js"></script>
<script src="/probe/app.js"></script>"""
    )


@app.get("/probe/mcs8Client.js")
async def probe_sdk(request: Request) -> FileResponse:
    require_local(request)
    return FileResponse(SDK_PATH, media_type="application/javascript")


@app.get("/probe/app.js")
async def probe_js(request: Request) -> FileResponse:
    require_local(request)
    return FileResponse(
        Path(__file__).with_name("mature_m32a_probe_app.js"),
        media_type="application/javascript",
    )


@app.post("/api/probe/session")
async def create_probe_session(request: Request) -> JSONResponse:
    require_local(request)
    session_id = uuid.uuid4().hex
    lease = secrets.token_urlsafe(32)
    adapter = ProbeAEEAdapter(session_id, settings, devices)
    await adapter.prepare()
    sessions[session_id] = (lease, adapter)
    response = JSONResponse(
        {
            "session_id": session_id,
            "devices": sorted(devices),
            "gateway_path": f"/ws/v2/realtime/{session_id}/gateway",
        }
    )
    response.set_cookie(
        COOKIE_NAME,
        lease,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response


@app.get("/api/probe/session/{session_id}")
async def probe_metrics(
    request: Request,
    session_id: str,
) -> JSONResponse:
    require_local(request)
    adapter = require_lease(
        session_id,
        request.cookies.get(COOKIE_NAME),
    )
    return JSONResponse(adapter.metrics())


@app.delete("/api/probe/session/{session_id}")
async def close_probe_session(
    request: Request,
    session_id: str,
) -> JSONResponse:
    require_local(request)
    adapter = require_lease(
        session_id,
        request.cookies.get(COOKIE_NAME),
    )
    await adapter.disconnect()
    deadline = time.monotonic() + 3
    while (
        any(adapter.connection_current.values())
        and time.monotonic() < deadline
    ):
        await asyncio.sleep(0.05)
    metrics = adapter.metrics()
    sessions.pop(session_id, None)
    response = JSONResponse(metrics)
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
    )
    return response


async def relay(websocket: WebSocket, session_id: str, kind: str) -> None:
    if websocket.client and websocket.client.host not in {"127.0.0.1", "::1"}:
        await websocket.close(code=4403)
        return
    try:
        adapter = require_lease(
            session_id,
            websocket.cookies.get(COOKIE_NAME),
        )
        await adapter.proxy(
            kind,
            websocket,
            proxy_host=websocket.headers.get("host", "127.0.0.1"),
        )
    except (HTTPException, AEEUpstreamError):
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass


@app.websocket("/ws/v2/realtime/{session_id}/gateway")
async def gateway(websocket: WebSocket, session_id: str) -> None:
    await relay(websocket, session_id, "gateway")


@app.websocket("/ws/v2/realtime/{session_id}/media")
@app.websocket("/ws/v2/realtime/{session_id}/media/")
async def media(websocket: WebSocket, session_id: str) -> None:
    await relay(websocket, session_id, "media")
