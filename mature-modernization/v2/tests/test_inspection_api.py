from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import sys
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.inspection import create_inspection_router
from app.api.inspection_access import InspectionAccess
from app.config import Settings
from app.data.inspection_records import build_authorized_user
from app.data.normalization import (
    normalize_alarm_events,
    normalize_device_location_events,
    normalize_device_status_events,
    normalize_media_files,
)
from app.data.realtime_views import build_realtime_view_event
from app.data.store import (
    MemoryInspectionRecordStore,
    MemoryInspectionStore,
    PostgresPoolExhaustedError,
)
from app.services.business_candidates import (
    BusinessFlight,
    BusinessRoutineTask,
)
from app.services.inspection import InspectionDataService


UTC = dt.timezone.utc
_DEFAULT_ACCESS = object()


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
        "headers": [(b"host", b"localhost")],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 80),
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


def _dashboard_settings() -> Settings:
    with patch.dict(
        os.environ,
        {
            "CHA_V2_FEATURE_DASHBOARD_V2": "true",
            "CHA_V2_FEATURE_INSPECTION_V2": "true",
        },
        clear=False,
    ):
        return Settings.from_env()


def _postgres_dashboard_settings() -> Settings:
    with patch.dict(
        os.environ,
        {
            "CHA_V2_FEATURE_DASHBOARD_V2": "true",
            "CHA_V2_FEATURE_INSPECTION_V2": "true",
            "CHA_V2_INSPECTION_STORE_PG_ENABLED": "true",
        },
        clear=False,
    ):
        return Settings.from_env()


def _load_main_for_unit_test():
    """Import ``app.main`` with a clean, non-production test baseline.

    Realtime API tests intentionally import the module later under their own
    isolated environment.  Removing this temporary import avoids locking the
    process-wide module settings before those tests set their runtime config.
    """

    sys.modules.pop("app.main", None)
    with patch.dict(
        os.environ,
        {
            "CHA_V2_FEATURE_DASHBOARD_V2": "",
            "CHA_V2_FEATURE_INSPECTION_V2": "",
            "CHA_V2_INSPECTION_STORE_PG_ENABLED": "",
            "CHA_V2_INSPECTION_STORE_MODE": "",
        },
        clear=False,
    ):
        return importlib.import_module("app.main")


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
    access=_DEFAULT_ACCESS,
) -> FastAPI:
    app = FastAPI()
    app.include_router(
        create_inspection_router(
            settings,
            service,
            _envelope,
            manager,
            _AllowAccess() if access is _DEFAULT_ACCESS else access,
        )
    )
    return app


class _AllowAccess:
    """Test-only stand-in for unrelated overview/normalization coverage."""

    async def require_authorized(self, request):
        del request
        return (None, "test-inspector"), None


class _Identity:
    def __init__(self, username: str | None) -> None:
        self.username = username

    async def __call__(self, request):
        del request
        if self.username is None:
            raise RuntimeError("not logged in")
        return None, self.username


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
    async def test_system_version_exposes_non_secret_runtime_identity(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="test-runtime-identity")
        )
        main_module = _load_main_for_unit_test()
        try:
            with patch.object(
                main_module,
                "release_identity",
                return_value={
                    "running_release": "phase6-candidate",
                    "running_commit": "0123456789abcdef",
                    "package_hash": "package-test-hash",
                },
            ):
                response = await main_module.version(request)
        finally:
            sys.modules.pop("app.main", None)

        payload = json.loads(response.body)
        self.assertEqual(
            payload["data"]["running_release"],
            "phase6-candidate",
        )
        self.assertEqual(
            payload["data"]["running_commit"],
            "0123456789abcdef",
        )
        self.assertEqual(payload["data"]["package_hash"], "package-test-hash")

    async def test_pool_busy_inspection_route_returns_safe_503(self) -> None:
        class _BusyService:
            async def realtime_overview(self, **_kwargs):
                raise PostgresPoolExhaustedError("driver detail must not leak")

        main_module = _load_main_for_unit_test()
        try:
            self.assertIs(
                main_module.app.exception_handlers[
                    PostgresPoolExhaustedError
                ],
                main_module.postgresql_pool_exhausted,
            )
            app = FastAPI()
            app.add_exception_handler(
                PostgresPoolExhaustedError,
                main_module.postgresql_pool_exhausted,
            )
            app.include_router(
                create_inspection_router(
                    _settings(True),
                    _BusyService(),
                    _envelope,
                    access=_AllowAccess(),
                )
            )
            response = await _request(
                app,
                "/api/v2/inspection/realtime?days=1",
            )
        finally:
            sys.modules.pop("app.main", None)

        payload = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["data"]["code"], "database_busy")
        self.assertNotIn("driver detail", response.text)

    async def test_readiness_reports_inspection_pg_degraded_without_failing_legacy(
        self,
    ) -> None:
        class _HealthResult:
            status_code = 200
            latency_ms = 1.25

        class _Legacy:
            async def health(self):
                return _HealthResult()

        class _Realtime:
            async def telemetry_snapshot(self):
                return {"cleanup_task_running": True}

        class _UnavailableStore:
            async def health_check(self):
                return False

        request = SimpleNamespace(
            state=SimpleNamespace(request_id="test-ready")
        )
        main_module = _load_main_for_unit_test()
        try:
            with (
                patch.object(
                    main_module,
                    "settings",
                    _postgres_dashboard_settings(),
                ),
                patch.object(main_module, "legacy_client", _Legacy()),
                patch.object(main_module, "realtime_manager", _Realtime()),
                patch.object(
                    main_module,
                    "inspection_store",
                    _UnavailableStore(),
                ),
                patch.object(
                    main_module,
                    "inspection_record_store",
                    _UnavailableStore(),
                ),
            ):
                response = await main_module.readiness(request)
        finally:
            sys.modules.pop("app.main", None)

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["status"], "degraded")
        self.assertEqual(
            payload["data"]["dependencies"]["legacy_service"]["status"],
            "ok",
        )
        self.assertEqual(
            payload["data"]["dependencies"]["postgresql"]["status"],
            "unavailable",
        )

    async def test_main_dashboard_routes_share_authorized_user_boundary(
        self,
    ) -> None:
        class _ProductionOverview:
            async def build(self, *, days: int):
                return {"available": True, "days": days}

        main_module = _load_main_for_unit_test()
        try:
            async def build_access(username: str | None) -> InspectionAccess:
                record_store = MemoryInspectionRecordStore()
                for account_id, account_name, enabled, role in (
                    ("admin-id", "admin-a", True, "admin"),
                    ("inspector-id", "inspector-a", True, None),
                    ("disabled-id", "disabled-a", False, None),
                ):
                    await record_store.upsert_authorized_user(
                        build_authorized_user(
                            aee_account_id=account_id,
                            username=account_name,
                            enabled=enabled,
                            role=role,
                        )
                    )
                return InspectionAccess(
                    record_store,
                    _Identity(username),
                    main_module.envelope,
                )

            async def assert_access(
                username: str | None,
                expected: int,
            ) -> None:
                with (
                    patch.object(
                        main_module,
                        "settings",
                        _dashboard_settings(),
                    ),
                    patch.object(
                        main_module,
                        "inspection_access",
                        await build_access(username),
                    ),
                    patch.object(
                        main_module,
                        "production_overview_service",
                        _ProductionOverview(),
                    ),
                ):
                    page = await _request(
                        main_module.app,
                        "/api/v2/dashboard",
                    )
                    data = await _request(
                        main_module.app,
                        "/api/v2/dashboard/production-overview",
                    )
                self.assertEqual(page.status_code, expected, username)
                self.assertEqual(data.status_code, expected, username)

            await assert_access(None, 401)
            await assert_access("ordinary-a", 403)
            await assert_access("disabled-a", 403)
            await assert_access("inspector-a", 200)
            await assert_access("admin-a", 200)
        finally:
            sys.modules.pop("app.main", None)

    async def test_dashboard_and_data_routes_share_authorized_user_boundary(
        self,
    ) -> None:
        service = await _seeded_service()

        async def build_access(username: str | None):
            record_store = MemoryInspectionRecordStore()
            for account_id, account_name, enabled, role in (
                ("admin-id", "admin-a", True, "admin"),
                ("inspector-id", "inspector-a", True, None),
                ("disabled-id", "disabled-a", False, None),
            ):
                await record_store.upsert_authorized_user(
                    build_authorized_user(
                        aee_account_id=account_id,
                        username=account_name,
                        enabled=enabled,
                        role=role,
                    )
                )
            return InspectionAccess(
                record_store,
                _Identity(username),
                _envelope,
            )

        pages = (
            "/api/v2/dashboard/overview-page",
            "/api/v2/dashboard/workbench",
            "/api/v2/dashboard/devices",
            "/api/v2/dashboard/media",
            "/api/v2/dashboard/realtime",
            "/api/v2/dashboard/inspections",
            "/api/v2/dashboard/alarms",
            "/api/v2/dashboard/tasks",
            "/api/v2/dashboard/map",
            "/api/v2/dashboard/data-quality",
        )
        data_apis = (
            "/api/v2/inspection/workbench/sources",
            "/api/v2/inspection/devices",
            "/api/v2/inspection/media",
            "/api/v2/inspection/realtime",
            "/api/v2/inspection/alarms",
            "/api/v2/inspection/locations",
            "/api/v2/inspection/data-quality",
            "/api/v2/inspection/flights-tasks",
            "/api/v2/inspection/devices/WX1/timeline",
        )

        anonymous_app = _app(
            _settings(feature=True),
            service,
            access=await build_access(None),
        )
        for path in pages + data_apis:
            response = await _request(anonymous_app, path)
            self.assertEqual(response.status_code, 401, path)

        for username in ("ordinary-a", "disabled-a"):
            app = _app(
                _settings(feature=True),
                service,
                access=await build_access(username),
            )
            response = await _request(app, "/api/v2/inspection/devices")
            self.assertEqual(response.status_code, 403, username)

        for username in ("inspector-a", "admin-a"):
            app = _app(
                _settings(feature=True),
                service,
                access=await build_access(username),
            )
            self.assertEqual(
                (await _request(app, "/api/v2/dashboard/devices")).status_code,
                200,
                username,
            )
            self.assertEqual(
                (await _request(app, "/api/v2/dashboard/workbench")).status_code,
                200,
                username,
            )
            self.assertEqual(
                (await _request(app, "/api/v2/inspection/workbench/sources")).status_code,
                200,
                username,
            )
            self.assertEqual(
                (
                    await _request(
                        app,
                        (
                            "/api/v2/inspection/devices"
                            "?start=2026-08-15T00:00:00%2B00:00"
                            "&end=2026-08-15T01:00:00%2B00:00"
                        ),
                    )
                ).status_code,
                200,
                username,
            )

    async def test_enabled_feature_fails_closed_without_access_adapter(
        self,
    ) -> None:
        app = _app(
            _settings(feature=True),
            await _seeded_service(),
            access=None,
        )
        response = await _request(app, "/api/v2/inspection/devices")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["data"]["code"],
            "inspection_access_not_configured",
        )

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

    async def test_workbench_page_and_sources_are_safe_and_bounded(
        self,
    ) -> None:
        app = _app(_settings(feature=True), await _seeded_service())
        page = await _request(app, "/api/v2/dashboard/workbench")
        self.assertEqual(page.status_code, 200)
        self.assertIn("视频监察工作台", page.text)
        self.assertIn("/api/v2/inspections/candidates", page.text)
        self.assertIn("AEE VERIFICATION REQUIRED", page.text)

        response = await _request(
            app,
            "/api/v2/inspection/workbench/sources?days=30&media_limit=1",
        )
        self.assertEqual(response.status_code, 200)
        sources = response.json()["data"]["sources"]
        self.assertEqual(sources["uploaded_video_playback_status"], "AEE_VERIFICATION_REQUIRED")
        self.assertEqual(len(sources["media_files"]), 1)
        media = sources["media_files"][0]
        self.assertFalse(media["playback_available"])
        self.assertEqual(media["playback_status"], "AEE_VERIFICATION_REQUIRED")
        for restricted_key in (
            "path",
            "web_url",
            "oss_bucket",
            "oss_object_name",
            "people_no",
            "work_no",
        ):
            self.assertNotIn(restricted_key, media)
        self.assertTrue(sources["devices"])

    async def test_workbench_feature_disabled_returns_404(self) -> None:
        app = _app(_settings(feature=False), None)
        response = await _request(app, "/api/v2/dashboard/workbench")
        self.assertEqual(response.status_code, 404)

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

    async def test_phase6_overview_and_alias_pages_render(self) -> None:
        app = _app(_settings(feature=True), None)
        cases = (
            ("/api/v2/dashboard/overview-page", "overview"),
            ("/api/v2/dashboard/tasks", "flights_tasks"),
            ("/api/v2/dashboard/map", "locations"),
            ("/api/v2/dashboard/data-quality", "data_quality"),
        )
        for path, active in cases:
            response = await _request(app, path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("监察数据中心", response.text)
            self.assertIn(f'const ACTIVE = "{active}";', response.text)


if __name__ == "__main__":
    unittest.main()
