from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import secrets
import time
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

from ..config import Settings
from .aee_adapter import AEEAdapter, redact_upstream_error
from .errors import AEEUpstreamError, RealtimeError
from .models import (
    RealtimeSession,
    RealtimeStream,
    SessionStatus,
    StreamStatus,
    utc_now,
)


logger = logging.getLogger("uvicorn.error.cha.realtime.session")
AdapterFactory = Callable[[str, Settings], AEEAdapter]


class RealtimeSessionManager:
    """Process-local M3.1 session coordinator with deterministic cleanup."""

    def __init__(
        self,
        settings: Settings,
        *,
        adapter_factory: AdapterFactory = AEEAdapter,
    ) -> None:
        self.settings = settings
        self.adapter_factory = adapter_factory
        self._sessions: dict[str, RealtimeSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(
                self._cleanup_loop(),
                name="realtime-session-cleanup",
            )

    async def shutdown(self) -> None:
        task = self._cleanup_task
        self._cleanup_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        for session_id in list(self._sessions):
            try:
                await self.close_session(session_id, owner_key=None, force=True)
            except Exception:
                logger.exception(
                    "realtime_shutdown_cleanup_failed session_id=%s",
                    session_id,
                )

    async def create_session(
        self,
        *,
        owner_key: str,
        owner_name: str,
    ) -> tuple[RealtimeSession, str]:
        now = utc_now()
        session_id = uuid.uuid4().hex
        lease = secrets.token_urlsafe(32)
        session = RealtimeSession(
            session_id=session_id,
            owner_key=owner_key,
            owner_name=owner_name,
            lease_hash=self._hash_secret(lease),
            status=SessionStatus.READY,
            created_at=now,
            last_heartbeat_at=now,
            expires_at=now
            + dt.timedelta(seconds=self.settings.realtime_session_ttl_seconds),
            adapter=self.adapter_factory(session_id, self.settings),
            updated_at=now,
        )
        async with self._lock:
            self._sessions[session_id] = session
        self._log(session, event="session_created", status=session.status.value)
        return session, lease

    async def get_session(
        self,
        session_id: str,
        *,
        owner_key: str | None,
    ) -> RealtimeSession:
        session = await self._lookup(session_id)
        self._assert_owner(session, owner_key)
        return session

    async def heartbeat(
        self,
        session_id: str,
        *,
        owner_key: str,
    ) -> RealtimeSession:
        session = await self.get_session(session_id, owner_key=owner_key)
        if session.status == SessionStatus.CLOSED:
            return session
        now = utc_now()
        session.last_heartbeat_at = now
        session.expires_at = now + dt.timedelta(
            seconds=self.settings.realtime_session_ttl_seconds
        )
        session.updated_at = now
        self._log(session, event="heartbeat", status=session.status.value)
        return session

    async def add_stream(
        self,
        session_id: str,
        *,
        owner_key: str,
        device_id: str,
    ) -> RealtimeStream:
        session = await self.get_session(session_id, owner_key=owner_key)
        async with session.operation_lock:
            if session.status in {SessionStatus.CLOSING, SessionStatus.CLOSED}:
                raise RealtimeError(
                    "session_closed",
                    "The realtime session is already closing or closed.",
                    status_code=409,
                )
            active = [
                stream
                for stream in session.streams.values()
                if stream.status != StreamStatus.CLOSED
            ]
            if active:
                raise RealtimeError(
                    "stream_limit_reached",
                    "M3.1 allows only one video stream per session.",
                    status_code=409,
                )
            session.status = SessionStatus.CREATING
            session.updated_at = utc_now()
            started = time.perf_counter()
            try:
                await session.adapter.prepare()
            except AEEUpstreamError as exc:
                session.status = SessionStatus.FAILED
                session.updated_at = utc_now()
                self._log(
                    session,
                    event="aee_prepare_failed",
                    status=session.status.value,
                    device_id=device_id,
                    error_code=exc.code,
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
                raise RealtimeError(
                    exc.code.lower(),
                    "The upstream realtime service could not be prepared.",
                    status_code=503,
                ) from exc
            authorize_device = getattr(
                session.adapter,
                "authorize_device",
                None,
            )
            if callable(authorize_device):
                authorize_device(device_id)
            now = utc_now()
            stream = RealtimeStream(
                stream_id=uuid.uuid4().hex,
                device_id=device_id,
                status=StreamStatus.CONNECTING,
                created_at=now,
                updated_at=now,
            )
            session.streams[stream.stream_id] = stream
            session.status = SessionStatus.CREATING
            session.updated_at = now
            self._log(
                session,
                stream=stream,
                event="stream_created",
                status=stream.status.value,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return stream

    async def delete_stream(
        self,
        session_id: str,
        stream_id: str,
        *,
        owner_key: str,
    ) -> RealtimeSession:
        session = await self.get_session(session_id, owner_key=owner_key)
        async with session.operation_lock:
            if session.status == SessionStatus.CLOSED:
                return session
            stream = session.streams.get(stream_id)
            if stream is None:
                raise RealtimeError(
                    "stream_not_found",
                    "The realtime video stream does not exist.",
                    status_code=404,
                )
            if stream.status == StreamStatus.CLOSED:
                session.streams.pop(stream_id, None)
                return session
            stream.status = StreamStatus.CLOSING
            stream.updated_at = utc_now()
            started = time.perf_counter()
            acknowledged = await self._send_control_command(
                session,
                "close_stream",
                {
                    "stream_id": stream.stream_id,
                    "device_id": stream.device_id,
                },
            )
            if acknowledged:
                release_mode = "close_media_monitor"
                clear_authorized_device = getattr(
                    session.adapter,
                    "clear_authorized_device",
                    None,
                )
                if callable(clear_authorized_device):
                    clear_authorized_device()
            else:
                await session.adapter.disconnect()
                session.connection_reusable = False
                release_mode = "forced_aee_disconnect"
            stream.status = StreamStatus.CLOSED
            stream.release_mode = release_mode
            stream.updated_at = utc_now()
            session.streams.pop(stream_id, None)
            session.status = SessionStatus.READY
            session.updated_at = utc_now()
            self._log(
                session,
                stream=stream,
                event="stream_released",
                status=stream.status.value,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return session

    async def close_session(
        self,
        session_id: str,
        *,
        owner_key: str | None,
        force: bool = False,
    ) -> RealtimeSession:
        session = await self._lookup(session_id)
        if not force:
            self._assert_owner(session, owner_key)
        async with session.operation_lock:
            if session.status == SessionStatus.CLOSED:
                return session
            session.status = SessionStatus.CLOSING
            session.updated_at = utc_now()
            started = time.perf_counter()
            if not force:
                await self._send_control_command(
                    session,
                    "close_session",
                    {
                        "streams": [
                            {
                                "stream_id": item.stream_id,
                                "device_id": item.device_id,
                            }
                            for item in session.streams.values()
                        ]
                    },
                )
            await session.adapter.disconnect()
            session.connection_reusable = False
            for stream in session.streams.values():
                stream.status = StreamStatus.CLOSED
                stream.release_mode = (
                    stream.release_mode or "session_disconnect"
                )
                stream.updated_at = utc_now()
            session.streams.clear()
            control_socket = session.control_socket
            session.control_socket = None
            self._fail_pending_commands(session, "session_closed")
            now = utc_now()
            session.status = SessionStatus.CLOSED
            session.closed_at = now
            session.updated_at = now
            session.expires_at = now + dt.timedelta(
                seconds=self.settings.realtime_closed_retention_seconds
            )
            self._log(
                session,
                event="session_closed",
                status=session.status.value,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            if control_socket is not None:
                try:
                    await control_socket.close(code=1000)
                except Exception:
                    pass
            return session

    async def validate_lease(self, session_id: str, lease: str | None) -> bool:
        if not lease:
            return False
        try:
            session = await self._lookup(session_id)
        except RealtimeError:
            return False
        return secrets.compare_digest(
            session.lease_hash,
            self._hash_secret(lease),
        )

    async def attach_control(
        self,
        session_id: str,
        socket: WebSocket,
    ) -> RealtimeSession:
        session = await self._lookup(session_id)
        previous = session.control_socket
        session.control_socket = socket
        if previous is not None and previous is not socket:
            try:
                await previous.close(code=4001)
            except Exception:
                pass
        self._log(
            session,
            event="control_connected",
            status=session.status.value,
        )
        return session

    async def detach_control(
        self,
        session_id: str,
        socket: WebSocket,
    ) -> None:
        try:
            session = await self._lookup(session_id)
        except RealtimeError:
            return
        release_required = False
        if session.control_socket is socket:
            session.control_socket = None
            self._fail_pending_commands(session, "control_disconnected")
            if session.status not in {
                SessionStatus.CLOSING,
                SessionStatus.CLOSED,
            }:
                session.status = SessionStatus.DEGRADED
                session.connection_reusable = False
                release_required = True
                for stream in session.streams.values():
                    if stream.status not in {
                        StreamStatus.CLOSING,
                        StreamStatus.CLOSED,
                    }:
                        stream.status = StreamStatus.DEGRADED
                        stream.updated_at = utc_now()
                session.updated_at = utc_now()
            self._log(
                session,
                event="control_disconnected",
                status=session.status.value,
            )
        if release_required:
            await session.adapter.disconnect()
            self._log(
                session,
                event="control_disconnect_release",
                status=session.status.value,
            )

    async def handle_control_message(
        self,
        session_id: str,
        message: dict[str, Any],
    ) -> None:
        session = await self._lookup(session_id)
        message_type = message.get("type")
        if message_type == "ack":
            command_id = str(message.get("command_id") or "")
            future = session.pending_commands.get(command_id)
            if future is not None and not future.done():
                future.set_result(
                    {
                        "ok": bool(message.get("ok")),
                        "error_code": str(message.get("error_code") or ""),
                    }
                )
        elif message_type == "event":
            await self.handle_client_event(
                session_id,
                event=str(message.get("event") or ""),
                stream_id=message.get("stream_id"),
                error_code=message.get("error_code"),
                details=message.get("details") or {},
            )

    async def handle_client_event(
        self,
        session_id: str,
        *,
        event: str,
        stream_id: str | None,
        error_code: str | None,
        details: dict[str, Any],
    ) -> RealtimeSession:
        session = await self._lookup(session_id)
        stream = session.streams.get(stream_id or "")
        now = utc_now()
        if event in {"gateway_connected", "media_resolved", "room_joined"}:
            session.status = SessionStatus.READY
            if stream is not None and event == "room_joined":
                session.connection_reusable = True
                stream.status = StreamStatus.WAITING_FIRST_FRAME
                stream.updated_at = now
        elif event in {"open_video_accepted", "waiting_first_frame"}:
            if stream is not None:
                stream.status = StreamStatus.WAITING_FIRST_FRAME
                stream.updated_at = now
        elif event == "first_frame":
            if stream is not None:
                stream.status = StreamStatus.PLAYING
                stream.first_frame_at = now
                stream.width = self._bounded_int(details.get("width"), 8192)
                stream.height = self._bounded_int(details.get("height"), 8192)
                stream.track_state = str(
                    details.get("track_state") or "live"
                )[:32]
                stream.error_code = None
                stream.updated_at = now
                session.status = SessionStatus.PLAYING
        elif event == "playback_failed":
            if stream is not None:
                stream.status = StreamStatus.FAILED
                stream.error_code = str(
                    error_code or "PLAYBACK_FAILED"
                )[:64]
                stream.updated_at = now
            session.status = SessionStatus.FAILED
            session.connection_reusable = False
        elif event == "browser_disconnected":
            session.status = SessionStatus.DEGRADED
            session.connection_reusable = False
            if stream is not None:
                stream.status = StreamStatus.DEGRADED
                stream.updated_at = now
        session.updated_at = now
        self._log(
            session,
            stream=stream,
            event=event,
            status=(stream.status.value if stream else session.status.value),
            error_code=error_code,
        )
        return session

    async def proxy_websocket(
        self,
        session_id: str,
        *,
        kind: str,
        socket: WebSocket,
        proxy_host: str,
    ) -> None:
        session = await self._lookup(session_id)
        if session.status in {SessionStatus.CLOSING, SessionStatus.CLOSED}:
            raise RealtimeError(
                "session_closed",
                "The realtime session is closed.",
                status_code=409,
            )
        self._log(
            session,
            event=f"{kind}_proxy_connecting",
            status=session.status.value,
        )
        try:
            await session.adapter.proxy(kind, socket, proxy_host=proxy_host)
        except AEEUpstreamError as exc:
            session.status = SessionStatus.DEGRADED
            session.connection_reusable = False
            session.updated_at = utc_now()
            self._log(
                session,
                event=f"{kind}_proxy_failed",
                status=session.status.value,
                error_code=exc.code,
            )
            raise
        except Exception as exc:
            session.status = SessionStatus.DEGRADED
            session.connection_reusable = False
            session.updated_at = utc_now()
            error_code = f"AEE_{kind.upper()}_RELAY_FAILED"
            self._log(
                session,
                event=f"{kind}_proxy_failed",
                status=session.status.value,
                error_code=error_code,
            )
            logger.warning(
                "realtime_proxy_runtime_failed session_id=%s kind=%s "
                "error=%s",
                session.session_id,
                kind,
                redact_upstream_error(exc),
            )
            raise AEEUpstreamError(
                error_code,
                f"AEE {kind} relay failed",
            ) from exc
        finally:
            unexpected_disconnect = session.status not in {
                SessionStatus.CLOSING,
                SessionStatus.CLOSED,
            }
            if unexpected_disconnect:
                session.status = SessionStatus.DEGRADED
                session.connection_reusable = False
                for stream in session.streams.values():
                    if stream.status not in {
                        StreamStatus.CLOSING,
                        StreamStatus.CLOSED,
                    }:
                        stream.status = StreamStatus.DEGRADED
                        stream.updated_at = utc_now()
                session.updated_at = utc_now()
                await session.adapter.disconnect()
            self._log(
                session,
                event=f"{kind}_proxy_disconnected",
                status=session.status.value,
            )

    async def active_count(self) -> int:
        async with self._lock:
            return sum(
                session.status != SessionStatus.CLOSED
                for session in self._sessions.values()
            )

    async def _send_control_command(
        self,
        session: RealtimeSession,
        action: str,
        payload: dict[str, Any],
    ) -> bool:
        socket = session.control_socket
        if socket is None:
            return False
        command_id = uuid.uuid4().hex
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        session.pending_commands[command_id] = future
        try:
            await socket.send_json(
                {
                    "type": "command",
                    "command_id": command_id,
                    "action": action,
                    "payload": payload,
                }
            )
            result = await asyncio.wait_for(
                future,
                timeout=self.settings.realtime_command_timeout_seconds,
            )
            return bool(result.get("ok"))
        except (TimeoutError, RuntimeError):
            return False
        finally:
            session.pending_commands.pop(command_id, None)

    async def _lookup(self, session_id: str) -> RealtimeSession:
        async with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise RealtimeError(
                "session_not_found",
                "The realtime session does not exist.",
                status_code=404,
            )
        return session

    @staticmethod
    def _assert_owner(
        session: RealtimeSession,
        owner_key: str | None,
    ) -> None:
        if owner_key is None or not secrets.compare_digest(
            session.owner_key,
            owner_key,
        ):
            raise RealtimeError(
                "session_forbidden",
                "The realtime session belongs to another login session.",
                status_code=403,
            )

    @staticmethod
    def _hash_secret(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _bounded_int(value: Any, maximum: int) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return max(0, min(parsed, maximum))

    def _fail_pending_commands(
        self,
        session: RealtimeSession,
        error_code: str,
    ) -> None:
        for future in session.pending_commands.values():
            if not future.done():
                future.set_result({"ok": False, "error_code": error_code})
        session.pending_commands.clear()

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.realtime_cleanup_interval_seconds)
            await self.cleanup_expired()

    async def cleanup_expired(self) -> None:
        now = utc_now()
        async with self._lock:
            snapshot = list(self._sessions.values())
        for session in snapshot:
            if session.expires_at > now:
                continue
            if session.status == SessionStatus.CLOSED:
                async with self._lock:
                    self._sessions.pop(session.session_id, None)
                continue
            try:
                await self.close_session(
                    session.session_id,
                    owner_key=None,
                    force=True,
                )
                self._log(
                    session,
                    event="session_expired",
                    status=session.status.value,
                )
            except Exception:
                logger.exception(
                    "realtime_expiry_cleanup_failed session_id=%s",
                    session.session_id,
                )

    def _log(
        self,
        session: RealtimeSession,
        *,
        event: str,
        status: str,
        stream: RealtimeStream | None = None,
        device_id: str | None = None,
        error_code: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        payload = {
            "session_id": session.session_id,
            "stream_id": stream.stream_id if stream else None,
            "device_id": (
                stream.device_id if stream else (device_id or None)
            ),
            "event": event,
            "status": status,
            "duration_ms": (
                round(duration_ms, 2) if duration_ms is not None else None
            ),
            "error_code": error_code,
            "release_mode": stream.release_mode if stream else None,
        }
        logger.info(
            "realtime_event %s",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
