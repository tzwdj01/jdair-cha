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
from .telemetry import RealtimeTelemetry


logger = logging.getLogger("uvicorn.error.cha.realtime.session")
AdapterFactory = Callable[[str, Settings], AEEAdapter]


class RealtimeSessionManager:
    """Process-local realtime coordinator with isolated stream cleanup."""

    def __init__(
        self,
        settings: Settings,
        *,
        adapter_factory: AdapterFactory = AEEAdapter,
        telemetry: RealtimeTelemetry | None = None,
    ) -> None:
        self.settings = settings
        self.adapter_factory = adapter_factory
        self.telemetry = telemetry or RealtimeTelemetry()
        self._sessions: dict[str, RealtimeSession] = {}
        self._owner_create_history: dict[str, list[float]] = {}
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
        async with self._lock:
            self._sessions.clear()
            self._owner_create_history.clear()

    async def create_session(
        self,
        *,
        owner_key: str,
        owner_name: str,
    ) -> tuple[RealtimeSession, str]:
        started = time.perf_counter()
        now = utc_now()
        session_id = uuid.uuid4().hex
        lease = secrets.token_urlsafe(32)
        adapter = self.adapter_factory(session_id, self.settings)
        bind_observer = getattr(adapter, "bind_observer", None)
        if callable(bind_observer):
            bind_observer(
                lambda event, duration_ms, error_code: (
                    self._adapter_event(
                        session_id,
                        event,
                        duration_ms=duration_ms,
                        error_code=error_code,
                    )
                )
            )
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
            adapter=adapter,
            updated_at=now,
        )
        async with self._lock:
            self._prune_closed_sessions_locked()
            active_for_owner = sum(
                item.owner_key == owner_key
                and item.status != SessionStatus.CLOSED
                for item in self._sessions.values()
            )
            if active_for_owner >= self.settings.realtime_max_sessions_per_owner:
                raise RealtimeError(
                    "owner_session_limit_reached",
                    "The login session has reached its realtime session limit.",
                    status_code=429,
                )
            monotonic_now = time.monotonic()
            cutoff = (
                monotonic_now
                - self.settings.realtime_session_create_window_seconds
            )
            history = [
                item
                for item in self._owner_create_history.get(owner_key, [])
                if item >= cutoff
            ]
            if len(history) >= self.settings.realtime_session_create_limit:
                self._owner_create_history[owner_key] = history
                raise RealtimeError(
                    "session_create_rate_limited",
                    "Realtime sessions are being created too frequently.",
                    status_code=429,
                )
            history.append(monotonic_now)
            self._owner_create_history[owner_key] = history
            self._sessions[session_id] = session
        duration_ms = (time.perf_counter() - started) * 1000
        self.telemetry.increment("realtime_session_create_total")
        self.telemetry.observe("session_create_duration_ms", duration_ms)
        self._log(
            session,
            event="session_created",
            duration_ms=duration_ms,
        )
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
            active = self._active_streams(session)
            if any(item.device_id == device_id for item in active):
                raise RealtimeError(
                    "duplicate_device",
                    "The selected device already has an active video stream.",
                    status_code=409,
                )
            if (
                len(active)
                >= self.settings.realtime_max_streams_per_session
            ):
                raise RealtimeError(
                    "stream_limit_reached",
                    "The realtime session has reached its video stream limit.",
                    status_code=409,
                )
            session.status = SessionStatus.CREATING
            session.updated_at = utc_now()
            started = time.perf_counter()
            self._log(
                session,
                event="stream_open_requested",
                device_id=device_id,
            )
            try:
                await session.adapter.prepare()
            except AEEUpstreamError as exc:
                session.status = (
                    SessionStatus.DEGRADED
                    if active
                    else SessionStatus.FAILED
                )
                session.updated_at = utc_now()
                self._log(
                    session,
                    event="aee_prepare_failed",
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
                runtime_state="AUTHORIZED",
            )
            session.streams[stream.stream_id] = stream
            self._prune_closed_streams(session)
            session.status = SessionStatus.CREATING
            session.updated_at = now
            self.telemetry.increment("realtime_stream_open_total")
            self._log(
                session,
                stream=stream,
                event="stream_opened",
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
                return session
            stream.status = StreamStatus.CLOSING
            stream.runtime_state = "RELEASING"
            stream.updated_at = utc_now()
            started = time.perf_counter()
            self._log(
                session,
                stream=stream,
                event="stream_close_requested",
            )
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
                    clear_authorized_device(stream.device_id)
            else:
                survivors = [
                    item
                    for item in self._active_streams(session)
                    if item.stream_id != stream.stream_id
                ]
                if survivors:
                    stream.status = StreamStatus.FAILED
                    stream.error_code = "STREAM_RELEASE_UNCONFIRMED"
                    stream.runtime_state = "RELEASE_FAILED"
                    stream.updated_at = utc_now()
                    session.status = SessionStatus.DEGRADED
                    session.updated_at = utc_now()
                    self._log(
                        session,
                        stream=stream,
                        event="stream_release_failed",
                        error_code=stream.error_code,
                        duration_ms=(
                            time.perf_counter() - started
                        )
                        * 1000,
                    )
                    self.telemetry.increment("realtime_release_failure_total")
                    raise RealtimeError(
                        "stream_release_failed",
                        (
                            "The selected video stream could not be "
                            "released without affecting other streams."
                        ),
                        status_code=502,
                    )
                disconnect_ok = await self._disconnect_adapter(
                    session,
                    event="stream_forced_disconnect_failed",
                )
                session.connection_reusable = False
                if not disconnect_ok:
                    stream.status = StreamStatus.FAILED
                    stream.error_code = "AEE_DISCONNECT_FAILED"
                    stream.runtime_state = "RELEASE_FAILED"
                    stream.updated_at = utc_now()
                    session.status = SessionStatus.DEGRADED
                    session.updated_at = utc_now()
                    self.telemetry.increment("realtime_release_failure_total")
                    raise RealtimeError(
                        "stream_release_failed",
                        "The video stream release could not be confirmed.",
                        status_code=502,
                    )
                release_mode = "forced_aee_disconnect"
            stream.status = StreamStatus.CLOSED
            stream.release_mode = release_mode
            stream.runtime_state = "RELEASED"
            stream.error_code = None
            now = utc_now()
            stream.closed_at = now
            stream.updated_at = now
            self._recompute_session_status(session)
            session.updated_at = now
            duration_ms = (time.perf_counter() - started) * 1000
            self.telemetry.increment("realtime_stream_close_total")
            self.telemetry.observe("close_video_duration_ms", duration_ms)
            self._log(
                session,
                stream=stream,
                event="stream_released",
                duration_ms=duration_ms,
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
            self._log(session, event="session_close_requested")
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
                            for item in self._active_streams(session)
                        ]
                    },
                )
            disconnect_ok = await self._disconnect_adapter(
                session,
                event="session_disconnect_failed",
            )
            session.connection_reusable = False
            active_before_close = sum(
                stream.status != StreamStatus.CLOSED
                for stream in session.streams.values()
            )
            for stream in session.streams.values():
                stream.status = StreamStatus.CLOSED
                stream.release_mode = (
                    stream.release_mode
                    or (
                        "session_disconnect"
                        if disconnect_ok
                        else "session_disconnect_unconfirmed"
                    )
                )
                stream.runtime_state = "RELEASED"
                if not disconnect_ok and stream.error_code is None:
                    stream.error_code = "AEE_DISCONNECT_FAILED"
                stream.closed_at = stream.closed_at or utc_now()
                stream.updated_at = utc_now()
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
            duration_ms = (time.perf_counter() - started) * 1000
            self.telemetry.increment("realtime_session_close_total")
            self.telemetry.increment(
                "realtime_stream_close_total",
                active_before_close,
            )
            self.telemetry.observe("session_shutdown_duration_ms", duration_ms)
            self._log(
                session,
                event="session_closed",
                duration_ms=duration_ms,
            )
            async with self._lock:
                self._prune_closed_sessions_locked()
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
        if (
            session.status == SessionStatus.CLOSED
            or session.expires_at <= utc_now()
        ):
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
                        stream.runtime_state = "CONNECTION_LOST"
                        stream.updated_at = utc_now()
                session.updated_at = utc_now()
            self._log(
                session,
                event="control_disconnected",
            )
            if session.status == SessionStatus.DEGRADED:
                self._log(
                    session,
                    event="session_degraded",
                    error_code="CONTROL_DISCONNECTED",
                )
            self.telemetry.increment("realtime_abnormal_disconnect_total")
        if release_required:
            await self._disconnect_adapter(
                session,
                event="control_disconnect_release_failed",
            )
            self._log(
                session,
                event="control_disconnect_release",
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
            if stream is not None and event == "room_joined":
                session.connection_reusable = True
                stream.status = StreamStatus.WAITING_FIRST_FRAME
                stream.runtime_state = "MONITORING"
                stream.updated_at = now
        elif event in {"open_video_accepted", "waiting_first_frame"}:
            if stream is not None:
                stream.status = StreamStatus.WAITING_FIRST_FRAME
                stream.runtime_state = "MONITORING"
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
                stream.runtime_state = "PLAYING"
                stream.updated_at = now
                duration_ms = (
                    now - stream.created_at
                ).total_seconds() * 1000
                self.telemetry.observe(
                    "open_video_to_first_frame_duration_ms",
                    duration_ms,
                )
        elif event == "playback_failed":
            if stream is not None:
                stream.status = StreamStatus.FAILED
                stream.error_code = str(
                    error_code or "PLAYBACK_FAILED"
                )[:64]
                stream.runtime_state = "FAILED"
                stream.updated_at = now
            session.status = SessionStatus.DEGRADED
            self._log(
                session,
                stream=stream,
                event="session_degraded",
                error_code=error_code or "PLAYBACK_FAILED",
            )
            if str(error_code or "").upper() == "FIRST_FRAME_TIMEOUT":
                self.telemetry.increment(
                    "realtime_first_frame_timeout_total"
                )
        elif event == "browser_disconnected":
            session.status = SessionStatus.DEGRADED
            session.connection_reusable = False
            targets = [stream] if stream is not None else self._active_streams(
                session
            )
            for target in targets:
                target.status = StreamStatus.DEGRADED
                target.runtime_state = "CONNECTION_LOST"
                target.updated_at = now
        if event != "browser_disconnected":
            self._recompute_session_status(session)
        session.updated_at = now
        self._log(
            session,
            stream=stream,
            event=(
                "first_frame_received"
                if event == "first_frame"
                else (
                    "first_frame_timeout"
                    if event == "playback_failed"
                    and str(error_code or "").upper()
                    == "FIRST_FRAME_TIMEOUT"
                    else event
                )
            ),
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
                self.telemetry.increment(
                    "realtime_abnormal_disconnect_total"
                )
                session.status = SessionStatus.DEGRADED
                session.connection_reusable = False
                for stream in session.streams.values():
                    if stream.status not in {
                        StreamStatus.CLOSING,
                        StreamStatus.CLOSED,
                    }:
                        stream.status = StreamStatus.DEGRADED
                        stream.runtime_state = "CONNECTION_LOST"
                        stream.updated_at = utc_now()
                session.updated_at = utc_now()
                await self._disconnect_adapter(
                    session,
                    event=f"{kind}_proxy_release_failed",
                )
                self._log(
                    session,
                    event="session_degraded",
                    error_code=f"{kind.upper()}_DISCONNECTED",
                )
            self._log(
                session,
                event=f"{kind}_proxy_disconnected",
            )

    async def active_count(self) -> int:
        async with self._lock:
            return sum(
                session.status != SessionStatus.CLOSED
                for session in self._sessions.values()
            )

    async def telemetry_snapshot(self) -> dict[str, object]:
        async with self._lock:
            sessions = list(self._sessions.values())
        return self.telemetry.snapshot(
            sessions,
            cleanup_task_running=(
                self._cleanup_task is not None
                and not self._cleanup_task.done()
            ),
        )

    @staticmethod
    def _active_streams(
        session: RealtimeSession,
    ) -> list[RealtimeStream]:
        return [
            stream
            for stream in session.streams.values()
            if stream.status != StreamStatus.CLOSED
        ]

    def _recompute_session_status(self, session: RealtimeSession) -> None:
        if session.status in {
            SessionStatus.CLOSING,
            SessionStatus.CLOSED,
        }:
            return
        active = self._active_streams(session)
        if not active:
            session.status = SessionStatus.READY
        elif any(
            stream.status in {StreamStatus.FAILED, StreamStatus.DEGRADED}
            for stream in active
        ):
            session.status = SessionStatus.DEGRADED
        elif all(stream.status == StreamStatus.PLAYING for stream in active):
            session.status = SessionStatus.PLAYING
        else:
            session.status = SessionStatus.CREATING

    def _prune_closed_streams(self, session: RealtimeSession) -> None:
        history_limit = max(
            8,
            self.settings.realtime_max_streams_per_session * 2,
        )
        closed = sorted(
            (
                stream
                for stream in session.streams.values()
                if stream.status == StreamStatus.CLOSED
            ),
            key=lambda item: item.closed_at or item.updated_at,
        )
        for stream in closed[:-history_limit]:
            session.streams.pop(stream.stream_id, None)

    def _prune_closed_sessions_locked(self) -> None:
        limit = self.settings.realtime_max_retained_sessions
        closed = sorted(
            (
                session
                for session in self._sessions.values()
                if session.status == SessionStatus.CLOSED
            ),
            key=lambda item: item.closed_at or item.updated_at,
        )
        excess = max(0, len(self._sessions) - limit)
        for session in closed[:excess]:
            self._sessions.pop(session.session_id, None)

    def _adapter_event(
        self,
        session_id: str,
        event: str,
        *,
        duration_ms: float | None,
        error_code: str | None,
    ) -> None:
        self.telemetry.adapter_event(event, duration_ms=duration_ms)
        session = self._sessions.get(session_id)
        if session is not None:
            self._log(
                session,
                event=event,
                duration_ms=duration_ms,
                error_code=error_code,
            )

    async def _disconnect_adapter(
        self,
        session: RealtimeSession,
        *,
        event: str,
    ) -> bool:
        try:
            await session.adapter.disconnect()
            return True
        except Exception as exc:
            logger.warning(
                "realtime_adapter_disconnect_failed session_id=%s error=%s",
                session.session_id,
                redact_upstream_error(exc),
            )
            self._log(
                session,
                event=event,
                error_code="AEE_DISCONNECT_FAILED",
            )
            self.telemetry.increment("realtime_release_failure_total")
            return False

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
        cutoff = (
            time.monotonic()
            - self.settings.realtime_session_create_window_seconds
        )
        async with self._lock:
            snapshot = list(self._sessions.values())
            self._owner_create_history = {
                owner: [stamp for stamp in stamps if stamp >= cutoff]
                for owner, stamps in self._owner_create_history.items()
                if any(stamp >= cutoff for stamp in stamps)
            }
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
                    event="session_timeout_cleanup",
                )
                self.telemetry.increment(
                    "realtime_session_timeout_cleanup_total"
                )
            except Exception:
                self.telemetry.increment("realtime_release_failure_total")
                logger.exception(
                    "realtime_expiry_cleanup_failed session_id=%s",
                    session.session_id,
                )

    def _log(
        self,
        session: RealtimeSession,
        *,
        event: str,
        status: str | None = None,
        stream: RealtimeStream | None = None,
        device_id: str | None = None,
        error_code: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        del status
        payload = {
            "session_id": session.session_id,
            "stream_id": stream.stream_id if stream else None,
            "device_id": (
                stream.device_id if stream else (device_id or None)
            ),
            "event": event,
            "session_status": session.status.value,
            "stream_status": stream.status.value if stream else None,
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
