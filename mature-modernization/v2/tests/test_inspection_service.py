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
from app.services.inspection import InspectionDataService


UTC = dt.timezone.utc


class InspectionDataServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()
        self.service = InspectionDataService(self.store)
        self.start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        self.end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)

    async def test_device_overview_computes_state_and_uptime(self) -> None:
        await self.store.upsert_device_status_events(
            normalize_device_status_events(
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
                        "devId": "WX1",
                        "status": 1,
                        "time": "2026-08-15 00:30:00+00:00",
                    },
                    {
                        "id": "s-4",
                        "devId": "WX2",
                        "status": 2,
                        "time": "2026-08-15 00:40:00+00:00",
                    },
                ],
                source_timezone=UTC,
                observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
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
        )

        overview = await self.service.device_overview(
            start=self.start,
            end=self.end,
        )

        self.assertEqual(overview.current_online_count, 1)
        self.assertEqual(overview.current_offline_count, 0)
        self.assertEqual(overview.current_unknown_count, 1)
        metrics = {
            item.device_id: item
            for item in overview.uptime.devices
        }
        wx1 = metrics["WX1"]
        self.assertEqual(wx1.online_seconds, 2400)
        self.assertEqual(wx1.offline_transition_count, 1)
        self.assertEqual(
            wx1.first_online_at,
            dt.datetime(2026, 8, 15, 0, 10, tzinfo=UTC),
        )
        self.assertEqual(
            wx1.last_offline_at,
            dt.datetime(2026, 8, 15, 0, 20, tzinfo=UTC),
        )
        latest = {
            item.device_id: item
            for item in overview.latest_by_device
        }
        self.assertTrue(latest["WX1"].latest_online)
        self.assertEqual(
            latest["WX1"].last_online_at,
            dt.datetime(2026, 8, 15, 0, 30, tzinfo=UTC),
        )
        self.assertEqual(
            latest["WX1"].last_offline_at,
            dt.datetime(2026, 8, 15, 0, 20, tzinfo=UTC),
        )
        self.assertIsNone(latest["WX2"].latest_online)
        self.assertIn(
            "online_state_unknown",
            latest["WX2"].quality_flags,
        )

    async def test_media_overview_computes_counts_and_trends(self) -> None:
        await self.store.upsert_media_files(
            normalize_media_files(
                [
                    {
                        "id": "file-1",
                        "devId": "WX1",
                        "fType": 3,
                        "fileSize": 4096,
                        "duration": 125,
                        "startTime": "2026-08-15 00:10:00+00:00",
                        "uploadTime": "2026-08-15 00:15:00+00:00",
                    },
                    {
                        "id": "file-2",
                        "devId": "WX1",
                        "fType": 1,
                        "fileSize": 1024,
                        "startTime": "2026-08-15 00:20:00+00:00",
                    },
                ],
                source_timezone=UTC,
                observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
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
        )

        overview = await self.service.media_overview(
            start=self.start,
            end=self.end,
        )

        self.assertEqual(overview.media.fetched_count, 2)
        self.assertEqual(overview.media.devices[0].video_count, 1)
        self.assertEqual(overview.media.devices[0].image_count, 1)
        self.assertEqual(
            overview.media.devices[0].video_duration_seconds,
            125,
        )
        self.assertEqual(
            overview.media.devices[0].file_size_bytes,
            5120,
        )
        self.assertEqual(
            overview.latest_uploaded_at,
            dt.datetime(2026, 8, 15, 0, 15, tzinfo=UTC),
        )
        self.assertEqual(
            overview.latest_created_at,
            dt.datetime(2026, 8, 15, 0, 20, tzinfo=UTC),
        )
        self.assertEqual(dict(overview.daily_counts), {"2026-08-15": 2})

    async def test_realtime_overview_reports_usage_history(self) -> None:
        await self.store.upsert_realtime_view_events(
            (
                build_realtime_view_event(
                    username="alice",
                    user_id=None,
                    device_id="WX1",
                    session_id="session-1",
                    stream_id="stream-1",
                    opened_at=dt.datetime(
                        2026,
                        8,
                        15,
                        0,
                        0,
                        tzinfo=UTC,
                    ),
                    first_frame_at=dt.datetime(
                        2026,
                        8,
                        15,
                        0,
                        0,
                        2,
                        tzinfo=UTC,
                    ),
                    closed_at=dt.datetime(
                        2026,
                        8,
                        15,
                        0,
                        1,
                        tzinfo=UTC,
                    ),
                    error_code=None,
                    width=1920,
                    height=1080,
                    track_state="live",
                    close_reason="session_close",
                    release_mode="session_disconnect",
                ),
                build_realtime_view_event(
                    username="bob",
                    user_id=None,
                    device_id="WX2",
                    session_id="session-2",
                    stream_id="stream-2",
                    opened_at=dt.datetime(
                        2026,
                        8,
                        15,
                        0,
                        10,
                        tzinfo=UTC,
                    ),
                    first_frame_at=None,
                    closed_at=dt.datetime(
                        2026,
                        8,
                        15,
                        0,
                        11,
                        tzinfo=UTC,
                    ),
                    error_code="FIRST_FRAME_TIMEOUT",
                    width=None,
                    height=None,
                    track_state=None,
                    close_reason="first_frame_timeout",
                    release_mode="session_disconnect",
                ),
            )
        )

        overview = await self.service.realtime_overview(
            start=self.start,
            end=self.end,
        )

        self.assertEqual(overview.aggregation.event_count, 2)
        self.assertEqual(overview.aggregation.played_count, 1)
        self.assertEqual(
            overview.aggregation.result_counts,
            (("played", 1), ("timeout", 1)),
        )
        users = {
            item.dimension_id: item
            for item in overview.aggregation.users
        }
        self.assertEqual(users["alice"].view_count, 1)
        self.assertEqual(users["alice"].view_duration_seconds, 58)
        self.assertEqual(users["bob"].view_duration_seconds, 0)

    async def test_alarm_and_location_overviews(self) -> None:
        await self.store.upsert_alarm_events(
            normalize_alarm_events(
                [
                    {
                        "id": "alarm-1",
                        "devId": "WX1",
                        "alarmType": 205,
                        "alarmStatus": 1,
                        "alarmTime": "2026-08-15 00:10:00+00:00",
                    }
                ],
                source_timezone=UTC,
                observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
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
        )
        await self.store.upsert_device_location_events(
            normalize_device_location_events(
                [
                    {
                        "lat": 39.9,
                        "lng": 116.4,
                        "gpsTime": "2026-08-15 00:10:00+00:00",
                    },
                    {
                        "lat": 39.91,
                        "lng": 116.41,
                        "gpsTime": "2026-08-15 00:30:00+00:00",
                    },
                ],
                device_id="WX1",
                source_timezone=UTC,
                observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
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
        )

        alarm = await self.service.alarm_overview(
            start=self.start,
            end=self.end,
        )
        location = await self.service.location_overview(
            start=self.start,
            end=self.end,
        )

        self.assertEqual(alarm.aggregation.alarm_count, 1)
        self.assertEqual(
            dict(alarm.aggregation.alarm_type_counts),
            {205: 1},
        )
        self.assertEqual(location.aggregation.included_event_count, 2)
        self.assertEqual(
            location.aggregation.devices[0].event_count,
            2,
        )

    async def test_scope_times_must_be_aware(self) -> None:
        with self.assertRaises(ValueError):
            await self.service.device_overview(
                start=dt.datetime(2026, 8, 15, 0),
                end=self.end,
            )

    async def test_device_timeline_returns_scoped_events(self) -> None:
        await self.store.upsert_device_status_events(
            normalize_device_status_events(
                [
                    {
                        "id": "s-1",
                        "devId": "WX1",
                        "status": 1,
                        "time": "2026-08-15 00:10:00+00:00",
                    }
                ],
                source_timezone=UTC,
                observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
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
        )
        await self.store.upsert_device_location_events(
            normalize_device_location_events(
                [
                    {
                        "lat": 39.9,
                        "lng": 116.4,
                        "gpsTime": "2026-08-15 00:20:00+00:00",
                    }
                ],
                device_id="WX1",
                source_timezone=UTC,
                observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
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
        )

        timeline = await self.service.device_timeline(
            device_id="WX1",
            start=self.start,
            end=self.end,
        )

        self.assertEqual(timeline.status_event_count, 1)
        self.assertEqual(timeline.location_point_count, 1)
        self.assertTrue(timeline.coordinates_restricted)
        self.assertEqual(
            timeline.location_points[0].gps_occurred_at,
            dt.datetime(2026, 8, 15, 0, 20, tzinfo=UTC),
        )
        self.assertFalse(
            hasattr(timeline.location_points[0], "latitude")
        )

    async def test_device_timeline_requires_device_id(self) -> None:
        with self.assertRaises(ValueError):
            await self.service.device_timeline(
                device_id=" ",
                start=self.start,
                end=self.end,
            )


if __name__ == "__main__":
    unittest.main()
