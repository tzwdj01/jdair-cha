from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from typing import Any

from fastapi import WebSocket

from ..config import Settings
from .errors import AEEUpstreamError


logger = logging.getLogger("uvicorn.error.cha.realtime.aee")
TOKEN_PATTERN = re.compile(
    r"(?i)((?:token|pwd|password|sessionid)=)[^&\s]+"
)
AUTH_PATTERN = re.compile(r"(?i)(authorization:\s*bearer\s+)\S+")
MEDIA_REQUEST_METHODS = frozenset(
    {
        "getRouterRtpCapabilities",
        "createWebRtcTransport",
        "connectWebRtcTransport",
        "join",
        "heartbeat",
        "mediaMonitor",
        "closeMediaMonitor",
    }
)


def redact_upstream_error(value: object) -> str:
    text = str(value)
    text = TOKEN_PATTERN.sub(r"\1<redacted>", text)
    text = AUTH_PATTERN.sub(r"\1<redacted>", text)
    return text[:500]


class AEEAdapter:
    """Server-side credential holder and transparent AEE WebSocket relay."""

    def __init__(self, session_id: str, settings: Settings) -> None:
        self.session_id = session_id
        self.settings = settings
        self._token: str | None = None
        self._media_info: dict[str, Any] | None = None
        self._media_ready = asyncio.Event()
        self._prepare_lock = asyncio.Lock()
        self._relay_lock = asyncio.Lock()
        self._upstreams: dict[str, Any] = {}
        self._authorized_devices: set[str] = set()
        self._open_monitors: set[str] = set()
        self._closed = False

    async def prepare(self) -> None:
        if self._token:
            return
        async with self._prepare_lock:
            if self._token:
                return
            self._validate_configuration()
            try:
                token = await asyncio.to_thread(self._login)
            except AEEUpstreamError:
                raise
            except Exception as exc:
                logger.error(
                    "aee_prepare_failed session_id=%s error=%s",
                    self.session_id,
                    redact_upstream_error(exc),
                )
                raise AEEUpstreamError(
                    "AEE_LOGIN_FAILED",
                    "AEE login failed",
                ) from exc
            self._token = token
            self._closed = False

    def _validate_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("CHA_V2_AEE_API_BASE_URL", self.settings.aee_api_base_url),
                ("CHA_V2_AEE_ORIGIN", self.settings.aee_origin),
                ("CHA_V2_AEE_GATEWAY_HOST", self.settings.aee_gateway_host),
                ("CHA_V2_AEE_USERNAME", self.settings.aee_username),
                ("CHA_V2_AEE_PASSWORD", self.settings.aee_password),
            )
            if not value
        ]
        if self.settings.aee_gateway_port <= 0:
            missing.append("CHA_V2_AEE_GATEWAY_PORT")
        if missing:
            raise AEEUpstreamError(
                "AEE_NOT_CONFIGURED",
                "Missing AEE configuration: " + ", ".join(missing),
            )

    def _login(self) -> str:
        timestamp = int(time.time())
        md5_password = hashlib.md5(
            self.settings.aee_password.encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()
        password_hash = hashlib.sha256(
            f"{md5_password}{timestamp}".encode("utf-8")
        ).hexdigest()
        payload = json.dumps(
            {
                "username": self.settings.aee_username,
                "password": password_hash,
                "udef_t": timestamp,
                "udef_v": "v1",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.settings.aee_api_base_url.rstrip("/") + "/api/v1/auth/Token",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": self.settings.aee_origin,
                "Referer": self.settings.aee_origin.rstrip("/") + "/v3/login",
                "User-Agent": "Mozilla/5.0 CHA-Realtime/0.4",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.aee_login_timeout_seconds,
            ) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise AEEUpstreamError(
                "AEE_LOGIN_FAILED",
                f"AEE login HTTP {exc.code}",
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AEEUpstreamError(
                "AEE_LOGIN_UNAVAILABLE",
                "AEE login endpoint is unavailable",
            ) from exc
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AEEUpstreamError(
                "AEE_LOGIN_INVALID_RESPONSE",
                "AEE login returned invalid JSON",
            ) from exc
        token = (
            data.get("content", {}).get("access_token")
            or data.get("Content", {}).get("access_token")
            or data.get("access_token")
        )
        if not isinstance(token, str) or not token:
            raise AEEUpstreamError(
                "AEE_LOGIN_REJECTED",
                "AEE login did not return an access token",
            )
        return token

    async def proxy(
        self,
        kind: str,
        client: WebSocket,
        *,
        proxy_host: str,
    ) -> None:
        if not self._token:
            raise AEEUpstreamError(
                "AEE_SESSION_NOT_PREPARED",
                "The AEE session has not been prepared",
            )
        if kind not in {"gateway", "media"}:
            raise AEEUpstreamError("AEE_PROXY_INVALID", "Invalid proxy kind")
        if kind == "media":
            try:
                await asyncio.wait_for(
                    self._media_ready.wait(),
                    timeout=self.settings.aee_connect_timeout_seconds,
                )
            except TimeoutError as exc:
                raise AEEUpstreamError(
                    "AEE_MEDIA_NOT_RESOLVED",
                    "AEE media server information was not received",
                ) from exc

        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            raise AEEUpstreamError(
                "AEE_PROXY_DEPENDENCY_MISSING",
                "The WebSocket relay dependency is unavailable",
            ) from exc

        url = self._gateway_url() if kind == "gateway" else self._media_url()
        try:
            upstream = await connect(
                url,
                subprotocols=["protoo"],
                origin=self.settings.aee_origin,
                user_agent_header="Mozilla/5.0 CHA-Realtime/0.4",
                open_timeout=self.settings.aee_connect_timeout_seconds,
                close_timeout=3,
                ping_interval=None,
                max_size=None,
            )
        except Exception as exc:
            logger.error(
                "aee_proxy_connect_failed session_id=%s kind=%s error=%s",
                self.session_id,
                kind,
                redact_upstream_error(exc),
            )
            raise AEEUpstreamError(
                f"AEE_{kind.upper()}_CONNECT_FAILED",
                f"AEE {kind} connection failed",
            ) from exc

        async with self._relay_lock:
            previous = self._upstreams.get(kind)
            self._upstreams[kind] = upstream
        if previous is not None:
            await previous.close(code=1000)

        await client.accept(subprotocol="protoo")
        try:
            await self._relay_messages(kind, client, upstream, proxy_host)
        finally:
            async with self._relay_lock:
                if self._upstreams.get(kind) is upstream:
                    self._upstreams.pop(kind, None)
            await upstream.close(code=1000)

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
                message_type = message.get("type")
                if message_type == "websocket.disconnect":
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
                if kind == "gateway" and isinstance(message, str):
                    message = self._capture_and_rewrite_gateway(
                        message,
                        proxy_host,
                    )
                if isinstance(message, str):
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

    def authorize_device(self, device_id: str) -> None:
        self._authorized_devices.add(device_id)

    def clear_authorized_device(self, device_id: str | None = None) -> None:
        if device_id is None:
            self._authorized_devices.clear()
            self._open_monitors.clear()
            return
        self._authorized_devices.discard(device_id)
        self._open_monitors.discard(device_id)

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

        # Protoo responses acknowledge server requests such as newConsumer and
        # must be returned unchanged. Only browser-originated requests need an
        # explicit read-only allowlist.
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
                or device_id not in self._authorized_devices
            ):
                raise AEEUpstreamError(
                    "AEE_VIDEO_REQUEST_FORBIDDEN",
                    "Only the selected live video stream is allowed",
                )
            if method == "mediaMonitor":
                if device_id in self._open_monitors:
                    raise AEEUpstreamError(
                        "AEE_STREAM_ALREADY_OPEN",
                        "The selected live video monitor is already open",
                    )
                self._open_monitors.add(device_id)
            else:
                self._open_monitors.discard(device_id)

    def _capture_and_rewrite_gateway(
        self,
        message: str,
        proxy_host: str,
    ) -> str:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return message
        if payload.get("method") != "ConnecteInfo":
            return message
        data = payload.get("data")
        if not isinstance(data, dict):
            return message
        media_token = data.get("token")
        media_host = data.get("mediaIp")
        media_port = data.get("mediaPort")
        if not media_token or not media_host or not media_port:
            return message

        self._media_info = deepcopy(data)
        self._media_ready.set()

        # Do not forward the complete ConnecteInfo object. Real responses may
        # contain unrelated FTP/OSS credentials and long-lived identifiers
        # that the receive-only browser SDK does not need.
        safe = {
            "token": "cha-realtime-proxy",
            "mediaIp": proxy_host,
            "MediaPrivateIp": proxy_host,
            "mediaDomain": proxy_host,
            "mediaPort": 80,
            "mediaSslPort": 443,
            "mediaHttpProxy": (
                f"/ws/v2/realtime/{self.session_id}/media"
            ),
            "devid": "cha-realtime",
            "userType": data.get("userType", 5),
            "enableTcp": bool(data.get("enableTcp", False)),
            "MultLogin": False,
        }
        payload["data"] = safe
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _gateway_url(self) -> str:
        if not self._token:
            raise AEEUpstreamError("AEE_LOGIN_REQUIRED", "AEE token is missing")
        timestamp = int(time.time())
        md5_password = hashlib.md5(
            self.settings.aee_password.encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()
        password_hash = hashlib.sha256(
            f"{md5_password}{timestamp}".encode("utf-8")
        ).hexdigest()
        scheme = "wss" if self.settings.aee_gateway_ssl else "ws"
        base = f"{scheme}://{self.settings.aee_gateway_host}"
        if self.settings.aee_gateway_http_proxy:
            base += self.settings.aee_gateway_http_proxy
        else:
            base += f":{self.settings.aee_gateway_port}"
        query = urllib.parse.urlencode(
            {
                "uid": self.settings.aee_username,
                "pwd": password_hash,
                "t": timestamp,
                "v": "v2",
                "token": self._token,
                "type": 41,
            }
        )
        return f"{base}?{query}"

    def _media_url(self) -> str:
        info = self._media_info
        if not info:
            raise AEEUpstreamError(
                "AEE_MEDIA_NOT_RESOLVED",
                "AEE media information is missing",
            )
        use_ssl = self.settings.aee_gateway_ssl
        if use_ssl:
            host = info.get("mediaDomain") or info.get("mediaIp")
            port = info.get("mediaSslPort")
            scheme = "wss"
        else:
            host = info.get("mediaIp")
            port = info.get("mediaPort")
            scheme = "ws"
        if not host or not port or not info.get("token"):
            raise AEEUpstreamError(
                "AEE_MEDIA_INVALID_RESPONSE",
                "AEE media information is incomplete",
            )
        base = f"{scheme}://{host}"
        media_proxy = info.get("mediaHttpProxy") if use_ssl else ""
        if media_proxy:
            base += str(media_proxy)
        else:
            base += f":{int(port)}"
        query = urllib.parse.urlencode(
            {
                "token": info["token"],
                "did": info.get("devid") or self.settings.aee_username,
                "rid": "mcs8_admin",
                "t": info.get("userType", 5),
                "ct": 9,
                "gt": 0,
                "o": 0,
            }
        )
        return f"{base}/?{query}"

    async def disconnect(self) -> None:
        self._closed = True
        await self._close_relay("media")
        await self._close_relay("gateway")
        self._token = None
        self._media_info = None
        self._media_ready.clear()
        self.clear_authorized_device()

    async def _close_relay(self, kind: str) -> None:
        async with self._relay_lock:
            upstream = self._upstreams.pop(kind, None)
        if upstream is not None:
            try:
                await upstream.close(code=1000)
            except Exception as exc:
                logger.warning(
                    "aee_proxy_close_failed session_id=%s kind=%s error=%s",
                    self.session_id,
                    kind,
                    redact_upstream_error(exc),
                )
