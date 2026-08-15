from __future__ import annotations

import datetime as dt
import unittest

from app.data.normalization import (
    normalize_alarm_events,
    normalize_device_location_events,
    normalize_device_status_events,
    normalize_media_files,
)
from app.data.realtime_views import build_realtime_view_event
from app.data.store import MemoryInspectionStore


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class MemoryInspectionStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()

    def _status(self, rows):
        return normalize_device_status_events(
            rows,
            source_timezone=UTC,
            observed_at=dt.datetime(
                2026,
                8,
                15,
                1,
                tzinfo=UTC,
            ),
            ingested_at=dt.datetime(
                2026,
                8,
                15,
                1,
                0,
                1,
                tzinfo=UTC,
            ),
        ).events

    def _location(self, rows):
        return normalize_device_location_events(
            rows,
            device_id="WX1",
            source_timezone=UTC,
            observed_at=dt.datetime(
                2026,
                8,
                15,
                1,
                tzinfo=UTC,
            ),
            ingested_at=dt.datetime(
                2026,
                8,
                15,
                1,
                0,
                1,
                tzinfo=UTC,
            ),
        ).events

    def _media(self, rows):
        return normalize_media_files(
            rows,
            source_timezone=UTC,
            observed_at=dt.datetime(
                2026,
                8,
                15,
                1,
                tzinfo=UTC,
            ),
            ingested_at=dt.datetime(
                2026,
                8,
                15,
                1,
                0,
                1,
                tzinfo=UTC,
            ),
        ).files

    def _alarm(self, rows):
        return normalize_alarm_events(
            rows,
            source_timezone=UTC,
            observed_at=dt.datetime(
                2026,
                8,
                15,
                1,
                tzinfo=UTC,
            ),
            ingested_at=dt.datetime(
                2026,
                8,
                15,
                1,
                0,
                1,
                tzinfo=UTC,
            ),
        ).events

    def _view(self, **kwargs):
        return build_realtime_view_event(
            username=kwargs.get("username", "alice"),
            user_id=None,
            device_id=kwargs.get("device_id", "WX1"),
            session_id=kwargs.get("session_id", "session-1"),
            stream_id=kwargs.get("stream_id", "stream-1"),
            opened_at=kwargs.get(
                "opened_at",
                dt.datetime(2026, 8, 15, 0, 0, tzinfo=UTC),
            ),
            first_frame_at=kwargs.get(
                "first_frame_at",
                dt.datetime(2026, 8, 15, 0, 0, 2, tzinfo=UTC),
            ),
            closed_at=kwargs.get(
                "closed_at",
                dt.datetime(2026, 8, 15, 0, 1, tzinfo=UTC),
            ),
            error_code=kwargs.get("error_code"),
            width=1920,
            height=1080,
            track_state="live",
            close_reason=kwargs.get("close_reason", "session_close"),
            release_mode="session_disconnect",
        )

    def _window(self):
        return (
            dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
            dt.datetime(2026, 8, 15, 2, tzinfo=UTC),
        )

    async def test_device_status_roundtrip_and_scope(self) -> None:
        events = self._status(
            [
                {
                    "id": "s-1",
                    "devId": "WX1",
                    "status": 1,
                    "time": "2026-08-15 00:10:00+00:00",
                },
                {
                    "id": "s-2",
                    "devId": "WX1",
                    "status": 2,
                    "time": "2026-08-15 00:20:00+00:00",
                },
                {
                    "id": "s-3",
                    "devId": "WX2",
                    "status": 1,
                    "time": "2026-08-15 00:30:00+00:00",
                },
            ]
        )
        accepted = await self.store.upsert_device_status_events(events)
        self.assertEqual(accepted, 3)

        start, end = self._window()
        all_rows = await self.store.fetch_device_status_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(all_rows), 3)
        wx1_rows = await self.store.fetch_device_status_events(
            start=start,
            end=end,
            device_ids=["WX1"],
        )
        self.assertEqual([row.device_id for row in wx1_rows], ["WX1", "WX1"])
        self.assertEqual(
            [row.occurred_at for row in wx1_rows],
            [
                dt.datetime(2026, 8, 15, 0, 10, tzinfo=UTC),
                dt.datetime(2026, 8, 15, 0, 20, tzinfo=UTC),
            ],
        )

    async def test_device_status_latest_observation_wins(self) -> None:
        first = self._status(
            [
                {
                    "id": "s-1",
                    "devId": "WX1",
                    "status": 1,
                    "time": "2026-08-15 00:10:00+00:00",
                }
            ]
        )
        await self.store.upsert_device_status_events(first)
        later = normalize_device_status_events(
            [
                {
                    "id": "s-1",
                    "devId": "WX1",
                    "status": 1,
                    "time": "2026-08-15 00:10:00+00:00",
                }
            ],
            source_timezone=UTC,
            observed_at=dt.datetime(2026, 8, 15, 1, 30, tzinfo=UTC),
            ingested_at=dt.datetime(2026, 8, 15, 1, 30, 1, tzinfo=UTC),
        ).events
        await self.store.upsert_device_status_events(later)

        start, end = self._window()
        rows = await self.store.fetch_device_status_events(
            start=start,
            end=end,
            device_ids=["WX1"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status_code, 1)

    async def test_device_location_deduplicates_by_identity(self) -> None:
        events = self._location(
            [
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 00:10:00+00:00",
                },
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 00:10:00+00:00",
                },
                {
                    "lat": 39.91,
                    "lng": 116.41,
                    "gpsTime": "2026-08-15 00:20:00+00:00",
                },
            ]
        )
        await self.store.upsert_device_location_events(events)
        start, end = self._window()
        rows = await self.store.fetch_device_location_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].latitude, 39.9)
        self.assertEqual(rows[1].latitude, 39.91)

    async def test_media_upsert_and_append_semantics(self) -> None:
        files = self._media(
            [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": "2026-08-15 00:10:00+00:00",
                },
                {
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": "2026-08-15 00:15:00+00:00",
                },
            ]
        )
        await self.store.upsert_media_files(files)

        update = normalize_media_files(
            [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": "2026-08-15 00:10:00+00:00",
                    "fileSize": 4096,
                }
            ],
            source_timezone=UTC,
            observed_at=dt.datetime(2026, 8, 15, 1, 30, tzinfo=UTC),
            ingested_at=dt.datetime(2026, 8, 15, 1, 30, 1, tzinfo=UTC),
        ).files
        await self.store.upsert_media_files(update)

        start, end = self._window()
        rows = await self.store.fetch_media_files(
            start=start,
            end=end,
        )
        self.assertEqual(len(rows), 2)
        by_title = {row.source_record_id: row for row in rows}
        self.assertEqual(by_title["file-1"].file_size_bytes, 4096)
        self.assertIsNone(by_title[None].source_record_id)

    async def test_realtime_view_first_finalization_wins(self) -> None:
        first = self._view()
        accepted_first = await self.store.upsert_realtime_view_events([first])
        self.assertEqual(accepted_first, 1)
        duplicate = await self.store.upsert_realtime_view_events([first])
        self.assertEqual(duplicate, 0)

        start, end = self._window()
        rows = await self.store.fetch_realtime_view_events(
            start=start,
            end=end,
            usernames=["alice"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stream_id, "stream-1")

    async def test_alarm_latest_observation_wins(self) -> None:
        first = self._alarm(
            [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmStatus": 1,
                    "dealStatus": 0,
                    "alarmTime": "2026-08-15 00:10:00+00:00",
                }
            ]
        )
        await self.store.upsert_alarm_events(first)
        updated = normalize_alarm_events(
            [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmStatus": 1,
                    "dealStatus": 2,
                    "alarmTime": "2026-08-15 00:10:00+00:00",
                }
            ],
            source_timezone=UTC,
            observed_at=dt.datetime(2026, 8, 15, 1, 30, tzinfo=UTC),
            ingested_at=dt.datetime(2026, 8, 15, 1, 30, 1, tzinfo=UTC),
        ).events
        await self.store.upsert_alarm_events(updated)

        start, end = self._window()
        rows = await self.store.fetch_alarm_events(
            start=start,
            end=end,
            device_ids=["WX1"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].deal_status_code, 2)

    async def test_window_requires_aware_ordered_times(self) -> None:
        with self.assertRaises(ValueError):
            await self.store.fetch_device_status_events(
                start=dt.datetime(2026, 8, 15, 0),
                end=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
            )
        with self.assertRaises(ValueError):
            await self.store.fetch_device_status_events(
                start=dt.datetime(2026, 8, 15, 2, tzinfo=UTC),
                end=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
            )


if __name__ == "__main__":
    unittest.main()
