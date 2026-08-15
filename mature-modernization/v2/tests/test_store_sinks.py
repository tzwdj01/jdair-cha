from __future__ import annotations

import datetime as dt
import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.data.realtime_views import build_realtime_view_event
from app.data.store import (
    MemoryInspectionStore,
    StoreViewEventSink,
)
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


class StoreViewEventSinkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()
        self.sink = StoreViewEventSink(self.store)

    def _event(self, stream_id: str = "stream-1") -> object:
        opened = dt.datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        return build_realtime_view_event(
            username="tester",
            user_id=None,
            device_id="WXB353",
            session_id="session-1",
            stream_id=stream_id,
            opened_at=opened,
            first_frame_at=opened + dt.timedelta(seconds=2),
            closed_at=opened + dt.timedelta(seconds=12),
            error_code=None,
            width=1920,
            height=1080,
            track_state="live",
            close_reason="user_stream_close",
            release_mode="close_media_monitor",
        )

    async def test_sink_persists_finalized_event(self) -> None:
        await self.sink(self._event())
        start = dt.datetime(2026, 8, 15, 9, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 11, tzinfo=UTC)
        rows = await self.store.fetch_realtime_view_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stream_id, "stream-1")
        self.assertEqual(rows[0].result, "played")
        self.assertEqual(rows[0].device_id, "WXB353")

    async def test_retry_is_idempotent_per_stream(self) -> None:
        event = self._event()
        await self.sink(event)
        accepted = await self.store.upsert_realtime_view_events((event,))
        self.assertEqual(accepted, 0)
        start = dt.datetime(2026, 8, 15, 9, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 11, tzinfo=UTC)
        rows = await self.store.fetch_realtime_view_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(rows), 1)


class StoreViewEventSinkManagerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, REALTIME_ENV, clear=False)
        self.env_patch.start()
        self.settings = Settings.from_env()

    def tearDown(self) -> None:
        self.env_patch.stop()

    async def test_full_session_persists_exactly_one_view_row(self) -> None:
        store = MemoryInspectionStore()
        manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
            view_event_sink=StoreViewEventSink(store),
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
        await manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )

        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 16, 0, tzinfo=UTC)
        rows = await store.fetch_realtime_view_events(
            start=start,
            end=end,
            usernames=["tester"],
            device_ids=["WXB353"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].result, "played")
        self.assertEqual(rows[0].close_reason, "user_stream_close")


if __name__ == "__main__":
    unittest.main()
