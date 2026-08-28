from __future__ import annotations

import datetime as dt
import json
import unittest

from app.services.business_candidates import (
    BusinessFlight,
    BusinessRoutineTask,
    LegacyBusinessDataClient,
)
from app.services.inspection import InspectionDataService
from app.data.store import MemoryInspectionStore


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class _FakeBusinessClient:
    def __init__(
        self,
        *,
        flights=(),
        tasks=(),
        fail=False,
    ) -> None:
        self.flights = flights
        self.tasks = tasks
        self.fail = fail
        self.cookies: list[str] = []

    def with_cookie(self, cookie: str) -> "_FakeBusinessClient":
        clone = _FakeBusinessClient(
            flights=self.flights,
            tasks=self.tasks,
            fail=self.fail,
        )
        clone.cookies = [cookie]
        return clone

    async def fetch_flights(self, date):
        if self.fail:
            raise RuntimeError("upstream down")
        return tuple(self.flights)

    async def fetch_routine_tasks(self, date):
        if self.fail:
            raise RuntimeError("upstream down")
        return tuple(self.tasks)


class FlightsTasksOverviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()

    async def test_not_wired_returns_explicit_flag(self) -> None:
        service = InspectionDataService(self.store)
        overview = await service.flights_tasks_overview()
        self.assertEqual(overview.quality_flags, ("business_client_not_wired",))
        self.assertEqual(overview.flights, ())
        self.assertEqual(overview.routine_tasks, ())

    async def test_wired_returns_normalized_rows(self) -> None:
        client = _FakeBusinessClient(
            flights=(
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
            ),
            tasks=(
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
            ),
        )
        service = InspectionDataService(self.store, business_client=client)
        overview = await service.flights_tasks_overview()
        self.assertEqual(overview.source_flight_count, 1)
        self.assertEqual(overview.source_task_count, 1)
        self.assertEqual(overview.flights[0][1], "JD5101")
        self.assertEqual(overview.flights[0][3], "PEK→SHA")
        self.assertEqual(overview.routine_tasks[0][2], "航线维修")
        self.assertEqual(overview.quality_flags, ())

    async def test_cookie_is_forwarded(self) -> None:
        class _RecordingClient(_FakeBusinessClient):
            def __init__(self) -> None:
                super().__init__()
                self.seen_cookies: list[str] = []

            def with_cookie(self, cookie: str) -> "_RecordingClient":
                clone = _RecordingClient()
                clone.seen_cookies = self.seen_cookies
                clone.seen_cookies.append(cookie)
                return clone

            async def fetch_flights(self, date):
                return ()

            async def fetch_routine_tasks(self, date):
                return ()

        client = _RecordingClient()
        service = InspectionDataService(self.store, business_client=client)
        await service.flights_tasks_overview(
            business_client_cookie="jdair_mcs8_session=abc123",
        )
        self.assertEqual(
            client.seen_cookies,
            ["jdair_mcs8_session=abc123"],
        )

    async def test_upstream_failure_is_explicit(self) -> None:
        client = _FakeBusinessClient(fail=True)
        service = InspectionDataService(self.store, business_client=client)
        overview = await service.flights_tasks_overview()
        self.assertEqual(
            overview.quality_flags,
            ("business_source_unavailable",),
        )


class LegacyBusinessDataClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_flights_normalizes_rows(self) -> None:
        class _Legacy:
            def __init__(self) -> None:
                self.flights_calls = []

            async def flights(self, cookie: str, date: str):
                self.flights_calls.append((cookie, date))
                return _LegacyResponse(
                    {"data": [{"flightId": "f1", "flightNo": "JD5101",
                               "acno": "B-1234", "dep3code": "PEK",
                               "arr3code": "SHA"}]}
                )

            async def routine_tasks(self, cookie: str, date: str):
                return _LegacyResponse(
                    {"records": [{"taskid": "TSK-1", "taskType": "AP",
                                  "taskTypeName": "航前"}]}
                )

        legacy = _Legacy()
        client = LegacyBusinessDataClient(
            legacy,
            source_timezone=SHANGHAI,
            cookie="sess=1",
        )
        flights = await client.fetch_flights(dt.date(2026, 8, 18))
        self.assertEqual(len(flights), 1)
        self.assertEqual(flights[0].flight_no, "JD5101")
        self.assertEqual(
            legacy.flights_calls,
            [("sess=1", "2026-08-18")],
        )
        tasks = await client.fetch_routine_tasks(dt.date(2026, 8, 18))
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_type_name, "航前")


class _LegacyResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def json(self):
        return self._payload


if __name__ == "__main__":
    unittest.main()
