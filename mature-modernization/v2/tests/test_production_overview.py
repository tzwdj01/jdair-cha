from __future__ import annotations

import asyncio
import datetime as dt
import unittest
from unittest.mock import patch

from app.data.normalization import (
    normalize_alarm_events,
    normalize_device_location_events,
    normalize_media_files,
)
from app.data.realtime_views import build_realtime_view_event
from app.data.store import MemoryInspectionRecordStore, MemoryInspectionStore
from app.services.inspection import InspectionDataService
from app.services.inspection_records import InspectionRecordService
from app.services.production_overview import ProductionOverviewService


UTC = dt.timezone.utc


class ProductionOverviewServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()
        self.inspection_service = InspectionDataService(self.store)
        self.record_store = MemoryInspectionRecordStore()
        self.record_service = InspectionRecordService(self.record_store)
        self.overview_service = ProductionOverviewService(
            self.inspection_service,
            self.record_service,
        )
        self.now = dt.datetime.now(UTC).replace(microsecond=0)
        # window extends a little past "now" so records submitted during
        # seeding (submitted_at == now) stay inside the window
        self.end = self.now + dt.timedelta(minutes=5)
        self.start = self.end - dt.timedelta(days=1)
        await self._seed()

    async def _seed(self) -> None:
        observed = self.end
        t = self.now
        # devices: WX1 online, WX2 offline
        from app.data.normalization import normalize_mcs8_device_snapshot

        snapshot = normalize_mcs8_device_snapshot(
            [
                {"szIDNO": "WX1", "nOnline": 1, "groupId": 1},
                {"szIDNO": "WX2", "nOnline": 0, "groupId": 1},
            ],
            observed_at=observed,
            ingested_at=observed,
        )
        await self.store.upsert_device_status_events(snapshot.events)

        # media: WX1 two video files
        m1_start = t - dt.timedelta(minutes=55)
        media = normalize_media_files(
            [
                {
                    "id": "m-1",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": (m1_start).strftime("%Y-%m-%d %H:%M:%S"),
                    "endTime": (
                        m1_start + dt.timedelta(minutes=5)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "fileSize": 1000,
                },
                {
                    "id": "m-2",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": (
                        t - dt.timedelta(minutes=40)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "endTime": (
                        t - dt.timedelta(minutes=35)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "fileSize": 2000,
                },
            ],
            source_timezone=UTC,
            observed_at=observed,
            ingested_at=observed,
            source_system="mcs8",
        )
        await self.store.upsert_media_files(media.files)

        # realtime: one played + one cancelled
        played = build_realtime_view_event(
            username="u1",
            user_id=None,
            device_id="WX1",
            session_id="sess-1",
            stream_id="strm-1",
            opened_at=t - dt.timedelta(minutes=50),
            first_frame_at=t - dt.timedelta(minutes=50) + dt.timedelta(seconds=2),
            closed_at=t - dt.timedelta(minutes=45),
            error_code=None,
            width=1920,
            height=1080,
            track_state="live",
            close_reason="session_close",
            release_mode="confirmed",
        )
        cancelled = build_realtime_view_event(
            username="u2",
            user_id=None,
            device_id="WX2",
            session_id="sess-2",
            stream_id="strm-2",
            opened_at=t - dt.timedelta(minutes=30),
            first_frame_at=None,
            closed_at=t - dt.timedelta(minutes=29),
            error_code=None,
            width=None,
            height=None,
            track_state=None,
            close_reason="session_timeout",
            release_mode="session_disconnect",
        )
        await self.store.upsert_realtime_view_events((played, cancelled))

        # alarms: WX1 two type-205 alarms
        alarms = normalize_alarm_events(
            [
                {
                    "id": "a-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmTime": (t - dt.timedelta(minutes=45)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                },
                {
                    "id": "a-2",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmTime": (t - dt.timedelta(minutes=30)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                },
            ],
            source_timezone=UTC,
            observed_at=observed,
            ingested_at=observed,
            source_system="mcs8",
        )
        await self.store.upsert_alarm_events(alarms.events)

        # location: WX1 one valid GPS point
        locations = normalize_device_location_events(
            [
                {
                    "devId": "WX1",
                    "lat": 31.2304,
                    "lng": 121.4737,
                    "gpsTime": (t - dt.timedelta(minutes=20)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            ],
            device_id="WX1",
            source_timezone=UTC,
            observed_at=observed,
            ingested_at=observed,
            source_system="mcs8",
        )
        await self.store.upsert_device_location_events(locations.events)

        # inspections: one submitted with issue, one draft
        first = await self.record_service.create_draft(
            inspector_user_id="u-1",
            inspector_username="u1",
            device_id="WX1",
            inspection_started_at=t - dt.timedelta(minutes=50),
            inspection_ended_at=t - dt.timedelta(minutes=45),
            aircraft_no="B-1234",
            flight_no="JD5101",
            station="PEK",
            maintenance_task_text="walkaround",
            has_issue=True,
            issue_type="oil_leak",
            issue_level="medium",
            issue_description="nose wheel bay leak",
        )
        await self.record_service.submit(
            inspection_id=first.record.inspection_id,
            submitter_user_id="u-1",
            submitter_username="u1",
        )
        draft = await self.record_service.create_draft(
            inspector_user_id="u-2",
            inspector_username="u2",
            device_id="WX2",
            inspection_started_at=t - dt.timedelta(minutes=30),
            inspection_ended_at=t - dt.timedelta(minutes=25),
        )
        await self.record_service.submit(
            inspection_id=draft.record.inspection_id,
            submitter_user_id="u-2",
            submitter_username="u2",
        )

    async def test_build_aggregates_all_domains(self) -> None:
        overview = await self.overview_service.build(
            days=1,
            as_of=self.end,
        )
        self.assertEqual(overview["scope"]["days"], 1)

        devices = overview["devices"]
        self.assertTrue(devices["available"])
        self.assertEqual(devices["distinct_devices"], 2)
        self.assertEqual(devices["current_online"], 1)
        self.assertEqual(devices["current_offline"], 1)

        media = overview["media"]
        self.assertTrue(media["available"])
        self.assertEqual(media["files"], 2)
        self.assertEqual(media["video_files"], 2)
        self.assertGreater(media["size_bytes"], 0)
        self.assertEqual(media["uploading_devices"], 1)

        realtime = overview["realtime"]
        self.assertTrue(realtime["available"])
        self.assertEqual(realtime["view_count"], 2)
        self.assertEqual(realtime["played_count"], 1)
        self.assertEqual(realtime["users"], 2)

        inspections = overview["inspections"]
        self.assertTrue(inspections["available"])
        self.assertEqual(inspections["total_count"], 2)
        self.assertEqual(inspections["issue_found_count"], 1)
        self.assertEqual(inspections["aircraft_count"], 1)
        self.assertEqual(inspections["participant_count"], 2)

        alarms = overview["alarms"]
        self.assertTrue(alarms["available"])
        self.assertEqual(alarms["alarm_count"], 2)
        self.assertEqual(alarms["affected_devices"], 1)

        locations = overview["locations"]
        self.assertTrue(locations["available"])
        self.assertEqual(locations["located_devices"], 1)
        self.assertGreaterEqual(locations["event_count"], 1)

        quality = overview["data_quality"]
        self.assertTrue(quality["available"])
        self.assertGreater(quality["total_rows"], 0)
        self.assertTrue(any(t["table"] == "media_files" for t in quality["tables"]))

    async def test_build_without_record_service_marks_unavailable(self) -> None:
        service = ProductionOverviewService(self.inspection_service, None)
        overview = await service.build(days=1, as_of=self.end)
        self.assertFalse(overview["inspections"]["available"])
        self.assertEqual(
            overview["inspections"]["error"],
            "record_service_not_wired",
        )
        # other domains still available
        self.assertTrue(overview["devices"]["available"])

    async def test_one_domain_failure_isolated_from_other_domains(self) -> None:
        with patch.object(
            self.inspection_service,
            "media_overview",
            side_effect=RuntimeError("media source unavailable"),
        ):
            overview = await self.overview_service.build(
                days=1,
                as_of=self.end,
            )
        self.assertFalse(overview["media"]["available"])
        self.assertEqual(overview["media"]["error"], "RuntimeError")
        self.assertTrue(overview["devices"]["available"])
        self.assertTrue(overview["alarms"]["available"])
        self.assertTrue(overview["inspections"]["available"])

    async def test_independent_domains_start_concurrently(self) -> None:
        """Gathered domains must not serially accumulate DB round trips."""

        started = 0
        all_started = asyncio.Event()

        async def domain(*_args, **_kwargs):
            nonlocal started
            started += 1
            if started == 7:
                all_started.set()
            await asyncio.wait_for(all_started.wait(), timeout=0.2)
            return {"available": True}

        with (
            patch.object(self.overview_service, "_devices", side_effect=domain),
            patch.object(self.overview_service, "_media", side_effect=domain),
            patch.object(self.overview_service, "_realtime", side_effect=domain),
            patch.object(
                self.overview_service,
                "_inspections",
                side_effect=domain,
            ),
            patch.object(self.overview_service, "_alarms", side_effect=domain),
            patch.object(
                self.overview_service,
                "_locations",
                side_effect=domain,
            ),
            patch.object(
                self.overview_service,
                "_data_quality",
                side_effect=domain,
            ),
        ):
            overview = await self.overview_service.build(
                days=1,
                as_of=self.end,
            )

        self.assertEqual(started, 7)
        self.assertTrue(all(item["available"] for item in (
            overview["devices"],
            overview["media"],
            overview["realtime"],
            overview["inspections"],
            overview["alarms"],
            overview["locations"],
            overview["data_quality"],
        )))


if __name__ == "__main__":
    unittest.main()
