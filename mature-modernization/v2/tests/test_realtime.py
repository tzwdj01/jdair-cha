from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.realtime.aee_adapter import AEEAdapter, redact_upstream_error
from app.realtime.errors import RealtimeError
from app.realtime.models import SessionStatus, StreamStatus, utc_now
from app.realtime.session_manager import RealtimeSessionManager


REALTIME_ENV = {
    "CHA_V2_FEATURE_REALTIME_READONLY": "true",
    "CHA_V2_REALTIME_SESSION_TTL_SECONDS": "60",
    "CHA_V2_REALTIME_CLEANUP_INTERVAL_SECONDS": "60",
    "CHA_V2_REALTIME_CLOSED_RETENTION_SECONDS": "60",
    "CHA_V2_REALTIME_COMMAND_TIMEOUT_SECONDS": "0.05",
    "CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION": "2",
    "CHA_V2_REALTIME_MAX_SESSIONS_PER_OWNER": "10",
    "CHA_V2_REALTIME_SESSION_CREATE_LIMIT": "500",
    "CHA_V2_REALTIME_SESSION_CREATE_WINDOW_SECONDS": "60",
    "CHA_V2_REALTIME_MAX_RETAINED_SESSIONS": "16",
}


class FakeAdapter:
    instances: list["FakeAdapter"] = []

    def __init__(self, session_id: str, settings: Settings) -> None:
        self.session_id = session_id
        self.settings = settings
        self.prepared = False
        self.authorized_devices: set[str] = set()
        self.disconnect_calls = 0
        self.proxy_calls = 0
        self.fail_disconnect = False
        self.__class__.instances.append(self)

    async def prepare(self) -> None:
        self.prepared = True

    def authorize_device(self, device_id: str) -> None:
        self.authorized_devices.add(device_id)

    def clear_authorized_device(self, device_id: str | None = None) -> None:
        if device_id is None:
            self.authorized_devices.clear()
        else:
            self.authorized_devices.discard(device_id)

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        if self.fail_disconnect:
            raise RuntimeError("upstream close failed")

    async def proxy(self, _kind, _socket, *, proxy_host: str) -> None:
        del proxy_host
        self.proxy_calls += 1


class FakeControlSocket:
    def __init__(self) -> None:
        self.commands: list[dict] = []
        self.close_calls = 0

    async def send_json(self, command: dict) -> None:
        self.commands.append(command)

    async def close(self, code: int = 1000) -> None:
        del code
        self.close_calls += 1


class RealtimeSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeAdapter.instances.clear()
        self.env_patch = patch.dict(os.environ, REALTIME_ENV, clear=False)
        self.env_patch.start()
        self.settings = Settings.from_env()
        self.manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    async def create(self):
        return await self.manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )

    async def ack_next(
        self,
        session_id: str,
        socket: FakeControlSocket,
        task: asyncio.Task,
        *,
        ok: bool,
        manager: RealtimeSessionManager | None = None,
    ):
        while not socket.commands:
            await asyncio.sleep(0)
        command = socket.commands.pop(0)
        await (manager or self.manager).handle_control_message(
            session_id,
            {
                "type": "ack",
                "command_id": command["command_id"],
                "ok": ok,
            },
        )
        return await task

    async def test_create_query_and_heartbeat(self) -> None:
        session, _ = await self.create()
        self.assertEqual(session.status, SessionStatus.READY)
        before = session.last_heartbeat_at
        await asyncio.sleep(0)
        heartbeat = await self.manager.heartbeat(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertGreaterEqual(heartbeat.last_heartbeat_at, before)
        fetched = await self.manager.get_session(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertEqual(fetched.session_id, session.session_id)

    async def test_add_two_streams_reject_duplicate_and_limit(self) -> None:
        session, _ = await self.create()
        first = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        self.assertTrue(FakeAdapter.instances[0].prepared)
        self.assertEqual(first.status, StreamStatus.CONNECTING)
        with self.assertRaises(RealtimeError) as context:
            await self.manager.add_stream(
                session.session_id,
                owner_key="owner-a",
                device_id="WXB339",
            )
        self.assertEqual(context.exception.code, "duplicate_device")
        second = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB337",
        )
        self.assertEqual(second.status, StreamStatus.CONNECTING)
        self.assertEqual(
            FakeAdapter.instances[0].authorized_devices,
            {"WXB339", "WXB337"},
        )
        with self.assertRaises(RealtimeError) as limit:
            await self.manager.add_stream(
                session.session_id,
                owner_key="owner-a",
                device_id="WXB342",
            )
        self.assertEqual(limit.exception.code, "stream_limit_reached")

    async def test_delete_stream_falls_back_to_media_disconnect(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        result = await self.manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )
        self.assertEqual(result.status, SessionStatus.READY)
        self.assertFalse(result.connection_reusable)
        self.assertEqual(stream.status, StreamStatus.CLOSED)
        self.assertIsNotNone(stream.closed_at)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_delete_stream_uses_browser_release_ack(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="room_joined",
            stream_id=stream.stream_id,
            error_code=None,
            details={},
        )
        socket = FakeControlSocket()
        session.control_socket = socket
        task = asyncio.create_task(
            self.manager.delete_stream(
                session.session_id,
                stream.stream_id,
                owner_key="owner-a",
            )
        )
        await self.ack_next(
            session.session_id,
            socket,
            task,
            ok=True,
        )
        self.assertNotIn(
            "WXB339",
            FakeAdapter.instances[0].authorized_devices,
        )
        self.assertTrue(session.connection_reusable)

    async def test_close_one_stream_does_not_stop_survivor(self) -> None:
        session, _ = await self.create()
        first = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        second = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB337",
        )
        for stream in (first, second):
            await self.manager.handle_client_event(
                session.session_id,
                event="first_frame",
                stream_id=stream.stream_id,
                error_code=None,
                details={"track_state": "live"},
            )
        self.assertEqual(session.status, SessionStatus.PLAYING)
        socket = FakeControlSocket()
        session.control_socket = socket
        task = asyncio.create_task(
            self.manager.delete_stream(
                session.session_id,
                first.stream_id,
                owner_key="owner-a",
            )
        )
        await self.ack_next(
            session.session_id,
            socket,
            task,
            ok=True,
        )
        self.assertEqual(first.status, StreamStatus.CLOSED)
        self.assertEqual(second.status, StreamStatus.PLAYING)
        self.assertEqual(session.status, SessionStatus.PLAYING)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 0)

    async def test_partial_release_failure_degrades_only_target(self) -> None:
        session, _ = await self.create()
        first = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        second = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB337",
        )
        for stream in (first, second):
            await self.manager.handle_client_event(
                session.session_id,
                event="first_frame",
                stream_id=stream.stream_id,
                error_code=None,
                details={"track_state": "live"},
            )
        socket = FakeControlSocket()
        session.control_socket = socket
        task = asyncio.create_task(
            self.manager.delete_stream(
                session.session_id,
                first.stream_id,
                owner_key="owner-a",
            )
        )
        with self.assertRaises(RealtimeError) as failed:
            await self.ack_next(
                session.session_id,
                socket,
                task,
                ok=False,
            )
        self.assertEqual(failed.exception.code, "stream_release_failed")
        self.assertEqual(first.status, StreamStatus.FAILED)
        self.assertEqual(second.status, StreamStatus.PLAYING)
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 0)
        snapshot = await self.manager.telemetry_snapshot()
        self.assertEqual(
            snapshot["counters"]["realtime_release_failure_total"],
            1,
        )

        retry = asyncio.create_task(
            self.manager.delete_stream(
                session.session_id,
                first.stream_id,
                owner_key="owner-a",
            )
        )
        await self.ack_next(
            session.session_id,
            socket,
            retry,
            ok=True,
        )
        self.assertEqual(first.status, StreamStatus.CLOSED)
        self.assertEqual(second.status, StreamStatus.PLAYING)
        self.assertEqual(session.status, SessionStatus.PLAYING)

    async def test_failed_stream_can_be_deleted(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="playback_failed",
            stream_id=stream.stream_id,
            error_code="OPEN_VIDEO_FAILED",
            details={},
        )
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        result = await self.manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )
        self.assertEqual(result.status, SessionStatus.READY)
        self.assertEqual(stream.status, StreamStatus.CLOSED)

    async def test_session_close_records_partial_disconnect_failure(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        FakeAdapter.instances[0].fail_disconnect = True
        closed = await self.manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertEqual(closed.status, SessionStatus.CLOSED)
        self.assertEqual(stream.status, StreamStatus.CLOSED)
        self.assertEqual(stream.error_code, "AEE_DISCONNECT_FAILED")
        self.assertEqual(
            stream.release_mode,
            "session_disconnect_unconfirmed",
        )

    async def test_close_is_idempotent(self) -> None:
        session, _ = await self.create()
        first_stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        second_stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB337",
        )
        first = await self.manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )
        second = await self.manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertIs(first, second)
        self.assertEqual(second.status, SessionStatus.CLOSED)
        self.assertEqual(first_stream.status, StreamStatus.CLOSED)
        self.assertEqual(second_stream.status, StreamStatus.CLOSED)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_illegal_session_and_owner_are_rejected(self) -> None:
        with self.assertRaises(RealtimeError) as missing:
            await self.manager.get_session("missing", owner_key="owner-a")
        self.assertEqual(missing.exception.code, "session_not_found")
        session, _ = await self.create()
        with self.assertRaises(RealtimeError) as forbidden:
            await self.manager.get_session(
                session.session_id,
                owner_key="owner-b",
            )
        self.assertEqual(forbidden.exception.code, "session_forbidden")

    async def test_client_first_frame_updates_observable_state(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="room_joined",
            stream_id=stream.stream_id,
            error_code=None,
            details={},
        )
        self.assertTrue(session.connection_reusable)
        await self.manager.handle_client_event(
            session.session_id,
            event="first_frame",
            stream_id=stream.stream_id,
            error_code=None,
            details={
                "width": 1920,
                "height": 1080,
                "track_state": "live",
            },
        )
        self.assertEqual(session.status, SessionStatus.PLAYING)
        self.assertEqual(stream.status, StreamStatus.PLAYING)
        self.assertEqual(stream.width, 1920)
        self.assertEqual(stream.track_state, "live")

    async def test_expired_session_is_force_closed_without_zombie(self) -> None:
        session, _ = await self.create()
        await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        session.expires_at = session.created_at - dt.timedelta(seconds=1)
        await self.manager.cleanup_expired()
        self.assertEqual(session.status, SessionStatus.CLOSED)
        self.assertTrue(
            all(
                item.status == StreamStatus.CLOSED
                for item in session.streams.values()
            )
        )
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)
        snapshot = await self.manager.telemetry_snapshot()
        self.assertEqual(
            snapshot["counters"][
                "realtime_session_timeout_cleanup_total"
            ],
            1,
        )

    async def test_control_disconnect_forces_upstream_release(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        socket = FakeControlSocket()
        session.control_socket = socket
        await self.manager.detach_control(session.session_id, socket)
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertFalse(session.connection_reusable)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_unexpected_media_proxy_close_releases_session(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.proxy_websocket(
            session.session_id,
            kind="media",
            socket=object(),
            proxy_host="cha.example",
        )
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertFalse(session.connection_reusable)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_unexpected_gateway_proxy_close_releases_session(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.proxy_websocket(
            session.session_id,
            kind="gateway",
            socket=object(),
            proxy_host="cha.example",
        )
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertFalse(session.connection_reusable)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_proxy_runtime_error_is_wrapped_and_released(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )

        async def fail_proxy(*_args, **_kwargs) -> None:
            raise RuntimeError("token=must-not-leak")

        session.adapter.proxy = fail_proxy
        with self.assertLogs(
            "uvicorn.error.cha.realtime.session",
            level="WARNING",
        ) as captured:
            with self.assertRaisesRegex(
                RuntimeError,
                "AEE media relay failed",
            ):
                await self.manager.proxy_websocket(
                    session.session_id,
                    kind="media",
                    socket=object(),
                    proxy_host="cha.example",
                )
        logs = "\n".join(captured.output)
        self.assertNotIn("must-not-leak", logs)
        self.assertIn("<redacted>", logs)
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_metrics_snapshot_tracks_lifecycle_and_latency(self) -> None:
        session, _ = await self.create()
        first = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="first_frame",
            stream_id=first.stream_id,
            error_code=None,
            details={"width": 1920, "height": 1080, "track_state": "live"},
        )
        second = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB337",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="playback_failed",
            stream_id=second.stream_id,
            error_code="FIRST_FRAME_TIMEOUT",
            details={},
        )
        snapshot = await self.manager.telemetry_snapshot()
        gauges = snapshot["gauges"]
        counters = snapshot["counters"]
        self.assertEqual(gauges["realtime_active_sessions"], 1)
        self.assertEqual(gauges["realtime_active_streams"], 2)
        self.assertEqual(gauges["realtime_streams_playing"], 1)
        self.assertEqual(gauges["realtime_streams_failed"], 1)
        self.assertEqual(counters["realtime_session_create_total"], 1)
        self.assertEqual(counters["realtime_stream_open_total"], 2)
        self.assertEqual(counters["realtime_first_frame_timeout_total"], 1)
        self.assertEqual(
            snapshot["durations"][
                "open_video_to_first_frame_duration_ms"
            ]["count"],
            1,
        )
        await self.manager.close_session(
            session.session_id,
            owner_key="owner-a",
            force=True,
        )
        closed = await self.manager.telemetry_snapshot()
        self.assertEqual(closed["gauges"]["realtime_active_sessions"], 0)
        self.assertEqual(closed["gauges"]["realtime_active_streams"], 0)
        self.assertEqual(closed["counters"]["realtime_session_close_total"], 1)
        self.assertEqual(closed["counters"]["realtime_stream_close_total"], 2)

    async def test_gateway_and_media_connection_gauges_return_to_zero(
        self,
    ) -> None:
        self.manager.telemetry.adapter_event(
            "gateway_connected",
            duration_ms=12.5,
        )
        self.manager.telemetry.adapter_event(
            "media_connected",
            duration_ms=18.5,
        )
        active = await self.manager.telemetry_snapshot()
        self.assertEqual(
            active["gauges"]["realtime_gateway_connections"],
            1,
        )
        self.assertEqual(
            active["gauges"]["realtime_media_connections"],
            1,
        )
        self.manager.telemetry.adapter_event("media_disconnected")
        self.manager.telemetry.adapter_event("gateway_disconnected")
        released = await self.manager.telemetry_snapshot()
        self.assertEqual(
            released["gauges"]["realtime_gateway_connections"],
            0,
        )
        self.assertEqual(
            released["gauges"]["realtime_media_connections"],
            0,
        )
        self.assertEqual(
            released["durations"]["gateway_connect_duration_ms"]["count"],
            1,
        )
        self.assertEqual(
            released["durations"]["media_connect_duration_ms"]["count"],
            1,
        )

    async def test_lease_expiry_and_closed_session_replay_are_rejected(
        self,
    ) -> None:
        session, lease = await self.create()
        self.assertTrue(
            await self.manager.validate_lease(session.session_id, lease)
        )
        session.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            seconds=1
        )
        self.assertFalse(
            await self.manager.validate_lease(session.session_id, lease)
        )
        fresh, fresh_lease = await self.create()
        await self.manager.close_session(
            fresh.session_id,
            owner_key="owner-a",
            force=True,
        )
        self.assertFalse(
            await self.manager.validate_lease(
                fresh.session_id,
                fresh_lease,
            )
        )

    async def test_owner_session_and_create_rate_limits(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_REALTIME_MAX_SESSIONS_PER_OWNER": "1",
                "CHA_V2_REALTIME_SESSION_CREATE_LIMIT": "2",
            },
            clear=False,
        ):
            manager = RealtimeSessionManager(
                Settings.from_env(),
                adapter_factory=FakeAdapter,
            )
            first, _ = await manager.create_session(
                owner_key="limited-owner",
                owner_name="tester",
            )
            with self.assertRaises(RealtimeError) as active_limit:
                await manager.create_session(
                    owner_key="limited-owner",
                    owner_name="tester",
                )
            self.assertEqual(
                active_limit.exception.code,
                "owner_session_limit_reached",
            )
            await manager.close_session(
                first.session_id,
                owner_key="limited-owner",
                force=True,
            )
            second, _ = await manager.create_session(
                owner_key="limited-owner",
                owner_name="tester",
            )
            await manager.close_session(
                second.session_id,
                owner_key="limited-owner",
                force=True,
            )
            with self.assertRaises(RealtimeError) as rate_limit:
                await manager.create_session(
                    owner_key="limited-owner",
                    owner_name="tester",
                )
            self.assertEqual(
                rate_limit.exception.code,
                "session_create_rate_limited",
            )

    async def test_graceful_shutdown_releases_all_sessions(self) -> None:
        await self.manager.start()
        first, _ = await self.create()
        second, _ = await self.manager.create_session(
            owner_key="owner-b",
            owner_name="tester-b",
        )
        await self.manager.add_stream(
            first.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.add_stream(
            second.session_id,
            owner_key="owner-b",
            device_id="WXB337",
        )
        await self.manager.shutdown()
        snapshot = await self.manager.telemetry_snapshot()
        self.assertFalse(snapshot["cleanup_task_running"])
        self.assertEqual(snapshot["gauges"]["realtime_active_sessions"], 0)
        self.assertEqual(snapshot["gauges"]["realtime_active_streams"], 0)
        self.assertTrue(
            all(item.disconnect_calls == 1 for item in FakeAdapter.instances)
        )

    async def test_abnormal_exit_then_timeout_returns_to_baseline(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        socket = FakeControlSocket()
        session.control_socket = socket
        await self.manager.detach_control(session.session_id, socket)
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        session.expires_at = utc_now() - dt.timedelta(seconds=1)
        await self.manager.cleanup_expired()
        snapshot = await self.manager.telemetry_snapshot()
        self.assertEqual(snapshot["gauges"]["realtime_active_sessions"], 0)
        self.assertEqual(snapshot["gauges"]["realtime_active_streams"], 0)
        self.assertEqual(
            snapshot["gauges"]["realtime_gateway_connections"],
            0,
        )
        self.assertEqual(
            snapshot["gauges"]["realtime_media_connections"],
            0,
        )
        self.assertEqual(
            snapshot["counters"]["realtime_abnormal_disconnect_total"],
            1,
        )
        self.assertEqual(
            snapshot["counters"][
                "realtime_session_timeout_cleanup_total"
            ],
            1,
        )

    async def test_receive_only_audio_is_single_stream_and_released(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_FEATURE_REALTIME_AUDIO": "true",
            },
            clear=False,
        ):
            manager = RealtimeSessionManager(
                Settings.from_env(),
                adapter_factory=FakeAdapter,
            )
            session, _ = await manager.create_session(
                owner_key="audio-owner",
                owner_name="audio",
            )
            first = await manager.add_stream(
                session.session_id,
                owner_key="audio-owner",
                device_id="WXB339",
            )
            second = await manager.add_stream(
                session.session_id,
                owner_key="audio-owner",
                device_id="WXB337",
            )
            await manager.enable_audio(
                session.session_id,
                first.stream_id,
                owner_key="audio-owner",
            )
            self.assertEqual(first.audio_status, "OPENING")
            with self.assertRaises(RealtimeError) as limit:
                await manager.enable_audio(
                    session.session_id,
                    second.stream_id,
                    owner_key="audio-owner",
                )
            self.assertEqual(
                limit.exception.code,
                "audio_stream_limit_reached",
            )
            await manager.handle_client_event(
                session.session_id,
                event="audio_playing",
                stream_id=first.stream_id,
                error_code=None,
                details={
                    "track_state": "live",
                    "codec": "audio/opus",
                },
            )
            self.assertEqual(first.audio_status, "PLAYING")
            self.assertEqual(first.audio_track_state, "live")
            self.assertEqual(first.audio_codec, "audio/opus")
            socket = FakeControlSocket()
            session.control_socket = socket
            task = asyncio.create_task(
                manager.disable_audio(
                    session.session_id,
                    first.stream_id,
                    owner_key="audio-owner",
                )
            )
            await self.ack_next(
                session.session_id,
                socket,
                task,
                ok=True,
                manager=manager,
            )
            self.assertEqual(first.audio_status, "OFF")
            snapshot = await manager.telemetry_snapshot()
            self.assertEqual(
                snapshot["counters"]["realtime_audio_open_total"],
                1,
            )
            self.assertEqual(
                snapshot["counters"]["realtime_audio_close_total"],
                1,
            )
            await manager.close_session(
                session.session_id,
                owner_key="audio-owner",
                force=True,
            )

    async def test_audio_is_rejected_when_feature_flag_is_off(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        with self.assertRaises(RealtimeError) as disabled:
            await self.manager.enable_audio(
                session.session_id,
                stream.stream_id,
                owner_key="owner-a",
            )
        self.assertEqual(disabled.exception.code, "audio_disabled")

    async def test_two_hundred_mixed_session_churn_is_bounded(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION": "6",
                "CHA_V2_REALTIME_MAX_RETAINED_SESSIONS": "16",
                "CHA_V2_REALTIME_SESSION_CREATE_LIMIT": "500",
            },
            clear=False,
        ):
            manager = RealtimeSessionManager(
                Settings.from_env(),
                adapter_factory=FakeAdapter,
            )
            total_streams = 0
            target_sizes = (1, 4, 6)
            for index in range(200):
                session, _ = await manager.create_session(
                    owner_key="churn-owner",
                    owner_name="churn",
                )
                target_size = target_sizes[index % len(target_sizes)]
                total_streams += target_size
                first_stream = None
                for offset in range(target_size):
                    stream = await manager.add_stream(
                        session.session_id,
                        owner_key="churn-owner",
                        device_id=f"WXB{index:03d}-{offset}",
                    )
                    first_stream = first_stream or stream
                    await manager.handle_client_event(
                        session.session_id,
                        event="first_frame",
                        stream_id=stream.stream_id,
                        error_code=None,
                        details={
                            "width": 1920,
                            "height": 1080,
                            "track_state": "live",
                        },
                    )
                if index % 10 == 0 and first_stream is not None:
                    await manager.handle_client_event(
                        session.session_id,
                        event="playback_failed",
                        stream_id=first_stream.stream_id,
                        error_code="FIRST_FRAME_TIMEOUT",
                        details={},
                    )
                    await manager.handle_client_event(
                        session.session_id,
                        event="first_frame",
                        stream_id=first_stream.stream_id,
                        error_code=None,
                        details={
                            "width": 1920,
                            "height": 1080,
                            "track_state": "live",
                        },
                    )
                if index % 25 == 0:
                    await manager.handle_client_event(
                        session.session_id,
                        event="browser_disconnected",
                        stream_id=None,
                        error_code="MEDIA_DISCONNECTED",
                        details={},
                    )
                await manager.close_session(
                    session.session_id,
                    owner_key="churn-owner",
                    force=True,
                )
            snapshot = await manager.telemetry_snapshot()
            self.assertEqual(snapshot["gauges"]["realtime_active_sessions"], 0)
            self.assertEqual(snapshot["gauges"]["realtime_active_streams"], 0)
            self.assertLessEqual(
                snapshot["gauges"]["realtime_retained_sessions"],
                16,
            )
            self.assertEqual(
                snapshot["counters"]["realtime_session_create_total"],
                200,
            )
            self.assertEqual(
                snapshot["counters"]["realtime_session_close_total"],
                200,
            )
            self.assertEqual(
                snapshot["counters"]["realtime_stream_open_total"],
                total_streams,
            )
            self.assertEqual(
                snapshot["counters"]["realtime_stream_close_total"],
                total_streams,
            )
            self.assertEqual(
                snapshot["counters"]["realtime_first_frame_timeout_total"],
                20,
            )

    async def test_structured_log_contains_correlation_fields(self) -> None:
        with self.assertLogs(
            "uvicorn.error.cha.realtime.session",
            level="INFO",
        ) as captured:
            session, _ = await self.create()
            await self.manager.add_stream(
                session.session_id,
                owner_key="owner-a",
                device_id="WXB339",
            )
        line = next(
            item for item in captured.output if "stream_opened" in item
        )
        payload = json.loads(line.split("realtime_event ", 1)[1])
        self.assertEqual(payload["session_id"], session.session_id)
        self.assertTrue(payload["stream_id"])
        self.assertEqual(payload["device_id"], "WXB339")
        self.assertEqual(payload["event"], "stream_opened")
        self.assertEqual(payload["session_status"], "CREATING")
        self.assertEqual(payload["stream_status"], "CONNECTING")
        self.assertIn("duration_ms", payload)
        self.assertIn("error_code", payload)
        self.assertIn("release_mode", payload)


class AEEAdapterTests(unittest.TestCase):
    def test_login_observer_receives_bounded_duration(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CHA_V2_AEE_API_BASE_URL": "https://aee.example",
                "CHA_V2_AEE_ORIGIN": "https://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "test-user",
                "CHA_V2_AEE_PASSWORD": "test-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-observer", Settings.from_env())
        events: list[tuple[str, float | None, str | None]] = []
        adapter.bind_observer(
            lambda event, duration, error: events.append(
                (event, duration, error)
            )
        )
        with patch.object(adapter, "_login", return_value="test-token"):
            asyncio.run(adapter.prepare())
        self.assertEqual(events[0][0], "aee_login_started")
        self.assertEqual(events[-1][0], "aee_login_succeeded")
        self.assertIsNotNone(events[-1][1])
        self.assertGreaterEqual(events[-1][1], 0)

    def test_upstream_urls_are_redacted(self) -> None:
        redacted = redact_upstream_error(
            "ws://host/?token=abc&pwd=def&sessionId=ghi"
        )
        self.assertNotIn("abc", redacted)
        self.assertNotIn("def", redacted)
        self.assertNotIn("ghi", redacted)

    def test_connect_info_is_rewritten_without_real_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_AEE_API_BASE_URL": "http://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "server-user",
                "CHA_V2_AEE_PASSWORD": "server-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-1", Settings.from_env())
        message = adapter._capture_and_rewrite_gateway(
            (
                '{"request":true,"method":"ConnecteInfo","data":{'
                '"mediaIp":"10.0.0.8","mediaPort":7710,'
                '"mediaDomain":"media.example","mediaSslPort":7705,'
                '"token":"real-media-token","devid":"server-user",'
                '"userType":5,"ftp":{"pwd":"ftp-secret"},'
                '"ossServer":{"accessSecret":"oss-secret"}}}'
            ),
            "cha.example",
        )
        self.assertNotIn("real-media-token", message)
        self.assertNotIn("server-user", message)
        self.assertNotIn("ftp-secret", message)
        self.assertNotIn("oss-secret", message)
        self.assertIn("cha-realtime-proxy", message)
        self.assertIn('"devid":"cha-realtime"', message)
        self.assertIn(
            "/ws/v2/realtime/session-1/media",
            message,
        )
        self.assertEqual(adapter._media_info["token"], "real-media-token")

    def test_media_allowlist_accepts_multiple_authorized_videos(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_AEE_API_BASE_URL": "http://aee.example",
                "CHA_V2_AEE_ORIGIN": "http://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "server-user",
                "CHA_V2_AEE_PASSWORD": "server-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-1", Settings.from_env())
        adapter.authorize_device("WXB339")
        adapter.authorize_device("WXB337")
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "createWebRtcTransport",
                    "data": {"producing": False, "consuming": True},
                }
            ),
        )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "mediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB339",
                        "streamType": 2,
                    },
                }
            ),
        )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "mediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB337",
                        "streamType": 2,
                    },
                }
            ),
        )
        self.assertEqual(
            adapter._open_monitors,
            {"video:WXB339", "video:WXB337"},
        )
        with self.assertRaisesRegex(RuntimeError, "already open"):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "mediaMonitor",
                        "data": {
                            "kind": "video",
                            "devId": "WXB339",
                            "streamType": 2,
                        },
                    }
                ),
            )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "closeMediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB339",
                        "streamType": 2,
                    },
                }
            ),
        )
        self.assertEqual(adapter._open_monitors, {"video:WXB337"})
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "join",
                    "data": {
                        "displayName": "browser",
                        "rtpCapabilities": {},
                    },
                }
            ),
        )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "mediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB339",
                        "streamType": 2,
                    },
                }
            ),
        )
        self.assertEqual(
            adapter._open_monitors,
            {"video:WXB339", "video:WXB337"},
        )
        adapter.clear_authorized_device("WXB339")
        self.assertEqual(adapter._authorized_devices, {"WXB337"})
        self.assertEqual(adapter._open_monitors, {"video:WXB337"})
        with self.assertRaisesRegex(
            RuntimeError,
            "authorized receive-only",
        ):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "mediaMonitor",
                        "data": {
                            "kind": "audio",
                            "devId": "WXB339",
                            "streamType": 0,
                        },
                    }
                ),
            )
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "playCtrl",
                        "data": {},
                    }
                ),
            )
        with self.assertRaisesRegex(RuntimeError, "mcs8_admin"):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "getRouterRtpCapabilities",
                        "data": {"roomId": "another-room"},
                    }
                ),
            )

    def test_gateway_allows_only_protoo_responses(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_AEE_API_BASE_URL": "http://aee.example",
                "CHA_V2_AEE_ORIGIN": "http://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "server-user",
                "CHA_V2_AEE_PASSWORD": "server-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-1", Settings.from_env())
        adapter._validate_client_message(
            "gateway",
            json.dumps({"response": True, "id": 1, "ok": True}),
        )
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            adapter._validate_client_message(
                "gateway",
                json.dumps(
                    {"request": True, "method": "deviceControl", "data": {}}
                ),
            )


if __name__ == "__main__":
    unittest.main()
