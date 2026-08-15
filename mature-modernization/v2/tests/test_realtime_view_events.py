from __future__ import annotations

import asyncio
import datetime as dt
import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.data.realtime_views import build_realtime_view_event
from app.realtime.session_manager import RealtimeSessionManager


UTC = dt.timezone.utc
REALTIME_ENV = {
    "CHA_V2_FEATURE_REALTIME_READONLY": "true",
    "CHA_V2_REALTIME_SESSION_TTL_SECONDS": "60",
    "CHA_V2_REALTIME_CLEANUP_INTERVAL_SECONDS": "60",
    "CHA_V2_REALTIME_CLOSED_RETENTION_SECONDS": "60",
    "CHA_V2_REALTIME_COMMAND_TIMEOUT_SECONDS": "0.01",
    "CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION": "4",
    "CHA_V2_REALTIME_MAX_SESSIONS_PER_OWNER": "10",
    "CHA_V2_REALTIME_SESSION_CREATE_LIMIT": "100",
    "CHA_V2_REALTIME_SESSION_CREATE_WINDOW_SECONDS": "60",
    "CHA_V2_REALTIME_MAX_RETAINED_SESSIONS": "16",
}


class FakeAdapter:
    def __init__(self, _session_id: str, settings: Settings) -> None:
        self.settings = settings

    async def prepare(self) -> None:
        return None

    def authorize_device(self, _device_id: str) -> None:
        return None

    def clear_authorized_device(self, _device_id: str | None = None) -> None:
        return None

    async def disconnect(self) -> None:
        return None


class RealtimeViewEventContractTests(unittest.TestCase):
    def test_played_event_uses_first_frame_view_duration(self) -> None:
        opened = dt.datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        first_frame = opened + dt.timedelta(seconds=2)
        closed = opened + dt.timedelta(seconds=12)

        event = build_realtime_view_event(
            username="tester",
            user_id=None,
            device_id="WXB353",
            session_id="session-1",
            stream_id="stream-1",
            opened_at=opened,
            first_frame_at=first_frame,
            closed_at=closed,
            error_code=None,
            width=1920,
            height=1080,
            track_state="live",
            close_reason="user_stream_close",
            release_mode="close_media_monitor",
        )

        self.assertEqual(event.view_event_id, "rtv_stream-1")
        self.assertEqual(event.source_system, "cha_realtime")
        self.assertEqual(event.result, "played")
        self.assertEqual(event.connection_duration_seconds, 12)
        self.assertEqual(event.view_duration_seconds, 10)
        self.assertEqual(event.width, 1920)
        self.assertEqual(event.height, 1080)

    def test_timeout_has_connection_duration_but_no_view_duration(self) -> None:
        opened = dt.datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        event = build_realtime_view_event(
            username="tester",
            user_id=None,
            device_id="WXB358",
            session_id="session-1",
            stream_id="stream-1",
            opened_at=opened,
            first_frame_at=None,
            closed_at=opened + dt.timedelta(seconds=20),
            error_code="FIRST_FRAME_TIMEOUT",
            width=None,
            height=None,
            track_state=None,
            close_reason="first_frame_timeout",
            release_mode="session_disconnect",
        )

        self.assertEqual(event.result, "timeout")
        self.assertEqual(event.connection_duration_seconds, 20)
        self.assertIsNone(event.view_duration_seconds)

    def test_abnormal_disconnect_wins_after_successful_playback(self) -> None:
        opened = dt.datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        event = build_realtime_view_event(
            username="tester",
            user_id=None,
            device_id="WXB353",
            session_id="session-1",
            stream_id="stream-1",
            opened_at=opened,
            first_frame_at=opened + dt.timedelta(seconds=1),
            closed_at=opened + dt.timedelta(seconds=5),
            error_code=None,
            width=1920,
            height=1080,
            track_state="ended",
            close_reason="abnormal_disconnect",
            release_mode="session_disconnect",
        )

        self.assertEqual(event.result, "abnormal_disconnect")
        self.assertEqual(event.view_duration_seconds, 4)

    def test_invalid_first_frame_is_ignored_with_quality_flag(self) -> None:
        opened = dt.datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        event = build_realtime_view_event(
            username="",
            user_id=None,
            device_id="WXB353",
            session_id="session-1",
            stream_id="stream-1",
            opened_at=opened,
            first_frame_at=opened - dt.timedelta(seconds=1),
            closed_at=opened + dt.timedelta(seconds=5),
            error_code=None,
            width=0,
            height=9000,
            track_state=None,
            close_reason="session_close",
            release_mode=None,
        )

        self.assertEqual(event.username, "unknown")
        self.assertEqual(event.result, "cancelled")
        self.assertIsNone(event.first_frame_at)
        self.assertIsNone(event.width)
        self.assertIsNone(event.height)
        self.assertIn("username_missing", event.quality_flags)
        self.assertIn(
            "first_frame_before_open_ignored",
            event.quality_flags,
        )

    def test_timestamps_must_be_aware_and_ordered(self) -> None:
        opened = dt.datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        arguments = {
            "username": "tester",
            "user_id": None,
            "device_id": "WXB353",
            "session_id": "session-1",
            "stream_id": "stream-1",
            "opened_at": opened,
            "first_frame_at": None,
            "closed_at": opened,
            "error_code": None,
            "width": None,
            "height": None,
            "track_state": None,
            "close_reason": "session_close",
            "release_mode": None,
        }

        with self.assertRaises(ValueError):
            build_realtime_view_event(
                **{
                    **arguments,
                    "opened_at": dt.datetime(2026, 8, 15, 10, 0),
                }
            )
        with self.assertRaises(ValueError):
            build_realtime_view_event(
                **{
                    **arguments,
                    "closed_at": opened - dt.timedelta(seconds=1),
                }
            )


class RealtimeViewEventManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, REALTIME_ENV, clear=False)
        self.env_patch.start()
        self.settings = Settings.from_env()

    def tearDown(self) -> None:
        self.env_patch.stop()

    async def test_stream_close_emits_one_played_event(self) -> None:
        events = []
        manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
            view_event_sink=events.append,
        )
        session, _ = await manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )
        stream = await manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB353",
        )
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
        first_frame_at = stream.first_frame_at
        await asyncio.sleep(0)
        await manager.handle_client_event(
            session.session_id,
            event="first_frame",
            stream_id=stream.stream_id,
            error_code=None,
            details={
                "width": 1280,
                "height": 720,
                "track_state": "live",
            },
        )
        await manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )
        await manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].username, "tester")
        self.assertEqual(events[0].device_id, "WXB353")
        self.assertEqual(events[0].result, "played")
        self.assertEqual(events[0].close_reason, "user_stream_close")
        self.assertEqual(events[0].width, 1280)
        self.assertEqual(stream.first_frame_at, first_frame_at)

    async def test_timeout_then_close_emits_timeout_event(self) -> None:
        events = []
        manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
            view_event_sink=events.append,
        )
        session, _ = await manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )
        stream = await manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB358",
        )
        await manager.handle_client_event(
            session.session_id,
            event="playback_failed",
            stream_id=stream.stream_id,
            error_code="FIRST_FRAME_TIMEOUT",
            details={},
        )
        await manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].result, "timeout")
        self.assertEqual(events[0].error_code, "FIRST_FRAME_TIMEOUT")
        self.assertEqual(events[0].close_reason, "first_frame_timeout")
        self.assertIsNone(events[0].view_duration_seconds)

    async def test_session_close_finalizes_each_stream_once(self) -> None:
        events = []
        manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
            view_event_sink=events.append,
        )
        session, _ = await manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )
        for device_id in ("WXB353", "WXB364"):
            await manager.add_stream(
                session.session_id,
                owner_key="owner-a",
                device_id=device_id,
            )

        await manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )
        await manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )

        self.assertEqual(len(events), 2)
        self.assertEqual(
            {event.device_id for event in events},
            {"WXB353", "WXB364"},
        )
        self.assertTrue(
            all(event.result == "cancelled" for event in events)
        )

    async def test_abnormal_disconnect_finalizes_at_disconnect(self) -> None:
        events = []
        manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
            view_event_sink=events.append,
        )
        session, _ = await manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )
        stream = await manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB353",
        )
        await manager.handle_client_event(
            session.session_id,
            event="first_frame",
            stream_id=stream.stream_id,
            error_code=None,
            details={"track_state": "live"},
        )
        await manager.handle_client_event(
            session.session_id,
            event="browser_disconnected",
            stream_id=stream.stream_id,
            error_code="MEDIA_DISCONNECTED",
            details={},
        )
        await manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].result, "abnormal_disconnect")
        self.assertEqual(events[0].close_reason, "abnormal_disconnect")

    async def test_sink_failure_does_not_block_close_and_can_retry(self) -> None:
        events = []
        attempts = 0

        async def flaky_sink(event) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary sink failure")
            events.append(event)

        manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
            view_event_sink=flaky_sink,
        )
        session, _ = await manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )
        stream = await manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB353",
        )

        with self.assertLogs(
            "uvicorn.error.cha.realtime.session",
            level="ERROR",
        ):
            await manager.delete_stream(
                session.session_id,
                stream.stream_id,
                owner_key="owner-a",
            )
        await manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )
        snapshot = await manager.telemetry_snapshot()

        self.assertEqual(attempts, 2)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            snapshot["counters"][
                "realtime_view_event_sink_failure_total"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
