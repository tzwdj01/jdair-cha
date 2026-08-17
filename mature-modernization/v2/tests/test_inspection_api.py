from __future__ import annotations

import datetime as dt
import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.inspection import create_inspection_router
from app.config import Settings
from app.data.normalization import (
    normalize_alarm_events,
    normalize_device_location_events,
    normalize_device_status_events,
    normalize_media_files,
)
from app.data.realtime_views import build_realtime_view_event
from app.data.store import MemoryInspectionStore
from app.services.business_candidates import (
    BusinessFlight,
    BusinessRoutineTask,
)
from app.services.inspection import InspectionDataService


UTC = dt.timezone.utc


class _ASGIResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.body = body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def json(self) -> dict[str, Any]:
        return json.loads(self.body)


async def _request(app, path: str) -> _ASGIResponse:
    path_without_query = path.split("?")[0]
    query = path.split("?", 1)[1] if "?" in path else ""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path_without_query,
        "raw_path": path_without_query.encode("ascii"),
        "query_string": query.encode("ascii"),
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    sent = False
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return _ASGIResponse(status_code=start["status"], body=body)


def _settings(feature: bool) -> Settings:
    with patch.dict(
        os.environ,
        {
            "CHA_V2_FEATURE_INSPECTION_V2": (
                "true" if feature else ""
            )
        },
        clear=False,
    ):
        return Settings.from_env()


def _envelope(
    request,
    data,
    *,
    ok: bool = True,
    status_code: int = 200,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": ok,
            "data": data,
            "meta": {
                "request_id": "test-1",
                "generated_at": "2026-08-15T00:00:00Z",
            },
        },
    )


def _app(
    settings: Settings,
    service: InspectionDataService | None,
    manager=None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(
        create_inspection_router(
            settings,
            service,
            _envelope,
            manager,
        )
    )
    return app


class _FakeRealtimeManager:
    def __init__(self) -> None:
        self._snapshot = {
            "gauges": {
                "realtime_active_sessions": 2,
                "realtime_active_streams": 3,
                "realtime_sessions_playing": 1,
                "realtime_streams_playing": 2,
                "realtime_gateway_connections": 1,
                "realtime_media_connections": 1,
            }
        }

    async def telemetry_snapshot(self):
        return self._snapshot


async def _seeded_service() -> InspectionDataService:
    store = MemoryInspectionStore()
    await store.upsert_device_status_events(
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
                    "devId": "WX2",
                    "status": 2,
                    "time": "2026-08-15 00:20:00+00:00",
                },
            ],
            source_timezone=UTC,
            observed_at=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
            ingested_at=dt.datetime(2026, 8, 15, 1, 0, 1, tzinfo=UTC),
        ).events
    )
    await store.upsert_media_files(
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
        ).files
    )
    await store.upsert_device_location_events(
        normalize_device_location_events(
            [
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 00:10:00+00:00",
                    "speed": 12.5,
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
    await store.upsert_realtime_view_events(
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
        )
    )
    await store.upsert_alarm_events(
        normalize_alarm_events(
            [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmStatus": 1,
                    "dealStatus": 0,
                    "alarmTime": "2026-08-15 00:05:00+00:00",
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
    return InspectionDataService(store)


class InspectionAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_feature_disabled_returns_404(self) -> None:
        app = _app(_settings(feature=False), None)
        response = await _request(app, "/api/v2/inspection/devices")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["data"]["code"],
            "feature_disabled",
        )

    async def test_no_store_returns_503(self) -> None:
        app = _app(_settings(feature=True), None)
        response = await _request(app, "/api/v2/inspection/devices")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["data"]["code"],
            "store_not_configured",
        )

    async def test_device_endpoint_returns_computed_overview(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        response = await _request(
            app,
            (
                "/api/v2/inspection/devices"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00&days=1"
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["data"]["store_configured"])
        meta = payload["data"]["meta"]
        self.assertIsNotNone(meta["generated_at"])
        self.assertIsNotNone(
            meta["freshness"]["latest_occurred_at"]
        )
        self.assertIn("complete", meta["quality"])
        self.assertIn(
            "quality_flags",
            meta["quality"],
        )
        self.assertEqual(
            meta["coverage"]["requested_window_days"],
            1,
        )
        self.assertGreaterEqual(
            meta["coverage"]["available_coverage_days"],
            1,
        )
        overview = payload["data"]["overview"]
        self.assertEqual(overview["current_online_count"], 1)
        self.assertEqual(overview["current_unknown_count"], 1)
        self.assertEqual(
            overview["uptime"]["devices"][0]["device_id"],
            "WX1",
        )

    async def test_media_and_realtime_endpoints(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        media = await _request(
            app,
            (
                "/api/v2/inspection/media"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(media.status_code, 200)
        media_meta = media.json()["data"]["meta"]
        self.assertIsNotNone(
            media_meta["freshness"]["latest_uploaded_at"]
        )
        self.assertIsNotNone(
            media_meta["freshness"]["latest_created_at"]
        )
        self.assertFalse(media_meta["quality"]["partial"])
        media_overview = media.json()["data"]["overview"]["media"]
        self.assertEqual(media_overview["devices"][0]["video_count"], 1)
        self.assertEqual(
            media_overview["devices"][0]["video_duration_seconds"],
            125,
        )
        media_data = media.json()["data"]["overview"]
        self.assertFalse(media_data["long_no_upload_governed"])
        self.assertEqual(media_data["long_no_upload_devices"], [])

        realtime = await _request(
            app,
            (
                "/api/v2/inspection/realtime"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(realtime.status_code, 200)
        realtime_meta = realtime.json()["data"]["meta"]
        self.assertIsNotNone(
            realtime_meta["freshness"]["latest_closed_at"]
        )
        self.assertEqual(
            realtime_meta["quality"]["event_count"],
            1,
        )
        aggregation = realtime.json()["data"]["overview"]["aggregation"]
        self.assertEqual(aggregation["event_count"], 1)
        self.assertEqual(aggregation["played_count"], 1)

    async def test_alarms_endpoint(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        response = await _request(
            app,
            (
                "/api/v2/inspection/alarms"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(response.status_code, 200)
        alarm_meta = response.json()["data"]["meta"]
        self.assertEqual(alarm_meta["quality"]["alarm_count"], 1)
        aggregation = response.json()["data"]["overview"]["aggregation"]
        self.assertEqual(aggregation["alarm_count"], 1)
        self.assertEqual(
            dict(aggregation["alarm_type_counts"]),
            {205: 1},
        )

    async def test_historical_coverage_is_partial_for_longer_request(
        self,
    ) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        response = await _request(
            app,
            "/api/v2/inspection/devices?days=7",
        )
        self.assertEqual(response.status_code, 200)
        coverage = response.json()["data"]["meta"]["coverage"]
        self.assertEqual(coverage["requested_window_days"], 7)
        self.assertLessEqual(
            coverage["available_coverage_days"],
            7,
        )
        self.assertIn(
            coverage["completeness"],
            {"FULL", "PARTIAL", "EMPTY"},
        )

    async def test_data_quality_endpoint(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        response = await _request(
            app,
            (
                "/api/v2/inspection/data-quality"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(response.status_code, 200)
        overview = response.json()["data"]["overview"]
        self.assertEqual(overview["total_rows"], 6)
        tables = {
            item["table"]: item
            for item in overview["tables"]
        }
        self.assertEqual(
            tables["device_status_events"]["row_count"],
            2,
        )

    async def test_flights_tasks_endpoint_with_client(self) -> None:
        class _FakeBusinessClient:
            async def fetch_flights(self, date):
                return (
                    BusinessFlight(
                        source_id="f1",
                        aircraft_no="B-1234",
                        flight_no="JD5101",
                        flight_date=None,
                        scheduled_departure_at=None,
                        scheduled_arrival_at=None,
                        actual_departure_at=None,
                        actual_arrival_at=None,
                        departure_city="PEK",
                        arrival_city="SHA",
                        departure_airport=None,
                        arrival_airport=None,
                        status_label="计划",
                    ),
                )

            async def fetch_routine_tasks(self, date):
                return (
                    BusinessRoutineTask(
                        source_id="t1",
                        aircraft_no="B-5678",
                        task_type="W",
                        task_type_name="航线维修",
                        task_status_code=None,
                        task_status_name=None,
                        bay="201",
                        planned_start_at=None,
                        inbound_flight_no=None,
                        inbound_date=None,
                        outbound_flight_no=None,
                        outbound_date=None,
                        route_city="PEK",
                    ),
                )

        service = InspectionDataService(
            MemoryInspectionStore(),
            business_client=_FakeBusinessClient(),
        )
        app = _app(_settings(feature=True), service)
        response = await _request(
            app,
            "/api/v2/inspection/flights-tasks?date=2026-08-18",
        )
        self.assertEqual(response.status_code, 200)
        overview = response.json()["data"]["overview"]
        self.assertEqual(overview["source_flight_count"], 1)
        self.assertEqual(overview["source_task_count"], 1)
        self.assertEqual(overview["flights"][0][1], "JD5101")

    async def test_flights_tasks_endpoint_not_wired(self) -> None:
        service = InspectionDataService(MemoryInspectionStore())
        app = _app(_settings(feature=True), service)
        response = await _request(
            app,
            "/api/v2/inspection/flights-tasks?date=2026-08-18",
        )
        self.assertEqual(response.status_code, 200)
        overview = response.json()["data"]["overview"]
        self.assertIn(
            "business_client_not_wired",
            overview["quality_flags"],
        )

    async def test_flights_tasks_invalid_date(self) -> None:
        service = InspectionDataService(MemoryInspectionStore())
        app = _app(_settings(feature=True), service)
        response = await _request(
            app,
            "/api/v2/inspection/flights-tasks?date=bad-date",
        )
        self.assertEqual(response.status_code, 400)

    async def test_realtime_runtime_snapshot_when_manager_provided(self) -> None:
        app = _app(
            _settings(feature=True),
            await _seeded_service(),
            _FakeRealtimeManager(),
        )
        response = await _request(
            app,
            (
                "/api/v2/inspection/realtime"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(response.status_code, 200)
        runtime = response.json()["data"]["runtime"]
        self.assertEqual(runtime["active_sessions"], 2)
        self.assertEqual(runtime["active_streams"], 3)
        self.assertEqual(runtime["gateway_connections"], 1)
        self.assertEqual(runtime["media_connections"], 1)

    async def test_realtime_runtime_null_without_manager(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        response = await _request(
            app,
            (
                "/api/v2/inspection/realtime"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["runtime"])

    async def test_device_timeline_endpoint(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        response = await _request(
            app,
            (
                "/api/v2/inspection/devices/WX1/timeline"
                "?start=2026-08-15T00:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(response.status_code, 200)
        timeline = response.json()["data"]["timeline"]
        self.assertEqual(timeline["device_id"], "WX1")
        self.assertEqual(timeline["status_event_count"], 1)
        self.assertEqual(timeline["media_file_count"], 1)
        self.assertEqual(timeline["location_point_count"], 1)
        self.assertTrue(timeline["coordinates_restricted"])
        self.assertNotIn("latitude", timeline["location_points"][0])
        self.assertNotIn("longitude", timeline["location_points"][0])
        self.assertEqual(
            timeline["location_points"][0]["speed_value"],
            12.5,
        )
        self.assertIn(
            "source_event_quality_flags_present",
            timeline["quality_flags"],
        )

    async def test_device_timeline_feature_disabled(self) -> None:
        app = _app(_settings(feature=False), None)
        response = await _request(
            app,
            "/api/v2/inspection/devices/WX1/timeline",
        )
        self.assertEqual(response.status_code, 404)

    async def test_invalid_scope_returns_400(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        bad_time = await _request(
            app,
            "/api/v2/inspection/devices?start=not-a-date",
        )
        self.assertEqual(bad_time.status_code, 400)
        self.assertEqual(bad_time.json()["data"]["code"], "invalid_scope")

        reversed_scope = await _request(
            app,
            (
                "/api/v2/inspection/devices"
                "?start=2026-08-15T02:00:00%2B00:00"
                "&end=2026-08-15T01:00:00%2B00:00"
            ),
        )
        self.assertEqual(reversed_scope.status_code, 400)

    async def test_pages_render_for_each_active_tab(self) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        for page, endpoint in (
            ("devices", "/api/v2/inspection/devices"),
            ("media", "/api/v2/inspection/media"),
            ("realtime", "/api/v2/inspection/realtime"),
            ("alarms", "/api/v2/inspection/alarms"),
            ("data_quality", "/api/v2/inspection/data-quality"),
        ):
            response = await _request(
                app,
                f"/api/v2/dashboard/{page}",
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("监察数据中心", response.text)
            self.assertIn(f'const ACTIVE = "{page}";', response.text)
            self.assertIn(endpoint, response.text)

    async def test_page_feature_disabled_returns_404(self) -> None:
        app = _app(_settings(feature=False), None)
        response = await _request(app, "/api/v2/dashboard/devices")
        self.assertEqual(response.status_code, 404)
        self.assertIn("尚未启用", response.text)


if __name__ == "__main__":
    unittest.main()
