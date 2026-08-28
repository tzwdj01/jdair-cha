from __future__ import annotations

import datetime as dt
import unittest

from app.services.business_candidates import (
    InspectionBusinessCandidateService,
    normalize_flight_row,
    normalize_routine_task_row,
    sanitize_task_raw,
)


UTC = dt.timezone.utc
SH = dt.timezone(dt.timedelta(hours=8))


FLIGHT_ROW = {
    "flightId": "487663",
    "acno": "B-224N",
    "flightNo": "JG2646",
    "flightDate": "2026-08-16 00:00:00",
    "std": "2026-08-16 05:45:00",
    "sta": "2026-08-16 08:45:00",
    "atd": "2026-08-16 05:38:57",
    "ata": "2026-08-16 08:19:30",
    "dep3code": "深圳/宝安",
    "arr3code": "北京/大兴",
    "departureAirport": "ZGSZ",
    "arrivalAirport": "ZBAD",
    "status": "正常",
    "dorI": "D",
}

TASK_ROW = {
    "taskid": "TSK-4886281",
    "acno": "B-226S",
    "taskType": "AP",
    "taskTypeName": "航前",
    "tasksts": "9",
    "taskstsName": "已交接",
    "bay": "710",
    "startPlanDate": "2026-08-15 23:35:00",
    "outFlightNo": "JG2671",
    "outDate": "2026-08-16 00:50:37",
    "outDateType": "2",
    "outFlight": "重庆/江北-芜湖/宣州",
    "inFlight": "-",
    "inDate": None,
    "inDateType": None,
    "fxWorker": "worker-a",
    "fxWorkerEmp": "EMP-000001",
    "wxWorker": "worker-b",
    "wxWorkerEmp": "EMP-000002",
}


class _FakeBusinessClient:
    def __init__(
        self,
        flights=None,
        tasks=None,
    ) -> None:
        self.flights = flights or []
        self.tasks = tasks or []

    async def fetch_flights(self, date):
        del date
        return tuple(self.flights)

    async def fetch_routine_tasks(self, date):
        del date
        return tuple(self.tasks)


class BusinessCandidateTests(unittest.IsolatedAsyncioTestCase):
    def test_live_row_normalization(self) -> None:
        flight = normalize_flight_row(FLIGHT_ROW)
        self.assertEqual(flight.source_id, "487663")
        self.assertEqual(flight.aircraft_no, "B-224N")
        self.assertEqual(flight.flight_no, "JG2646")
        self.assertEqual(
            flight.actual_arrival_at,
            dt.datetime(2026, 8, 16, 0, 19, 30, tzinfo=UTC),
        )
        self.assertEqual(flight.departure_city, "深圳/宝安")
        self.assertEqual(flight.arrival_city, "北京/大兴")

        task = normalize_routine_task_row(TASK_ROW)
        self.assertEqual(task.source_id, "TSK-4886281")
        self.assertEqual(task.aircraft_no, "B-226S")
        self.assertEqual(task.task_type_name, "航前")
        self.assertEqual(task.bay, "710")
        self.assertEqual(task.outbound_flight_no, "JG2671")

    def test_sanitize_task_raw_removes_person_fields(self) -> None:
        raw = sanitize_task_raw(TASK_ROW)
        self.assertNotIn("fxWorker", raw)
        self.assertNotIn("fxWorkerEmp", raw)
        self.assertNotIn("wxWorker", raw)
        self.assertNotIn("wxWorkerEmp", raw)
        self.assertIn("taskid", raw)

    async def test_candidates_filter_by_aircraft_and_window(self) -> None:
        flight = normalize_flight_row(FLIGHT_ROW)
        task = normalize_routine_task_row(TASK_ROW)
        client = _FakeBusinessClient(flights=[flight], tasks=[task])
        service = InspectionBusinessCandidateService(client)

        # inspection at 08:30 local on 08-16 near the flight arrival 08:19
        inspection = dt.datetime(2026, 8, 16, 8, 30, tzinfo=SH)
        result = await service.find_candidates(
            inspection_started_at=inspection,
            aircraft_no="B-224N",
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.source, "flight")
        self.assertEqual(candidate.source_id, "487663")
        self.assertEqual(candidate.aircraft_no, "B-224N")
        self.assertEqual(candidate.association_method, "SOURCE_DIRECT")

        # inspection far from any flight/task -> no candidates
        far = await service.find_candidates(
            inspection_started_at=dt.datetime(2026, 8, 16, 20, 0, tzinfo=SH),
        )
        self.assertEqual(len(far.candidates), 0)

    async def test_routine_task_candidate(self) -> None:
        task = normalize_routine_task_row(TASK_ROW)
        client = _FakeBusinessClient(tasks=[task])
        service = InspectionBusinessCandidateService(client)
        inspection = dt.datetime(2026, 8, 16, 0, 30, tzinfo=SH)
        result = await service.find_candidates(
            inspection_started_at=inspection,
            station="710",
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.source, "routine_task")
        self.assertEqual(candidate.source_id, "TSK-4886281")
        self.assertEqual(candidate.station, "710")
        self.assertEqual(candidate.association_method, "SOURCE_DIRECT")


if __name__ == "__main__":
    unittest.main()
