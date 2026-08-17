from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")

RESTRICTED_TASK_FIELDS = {
    "fxWorker",
    "fxWorkerEmp",
    "wxWorker",
    "wxWorkerEmp",
}


@dataclass(frozen=True, slots=True)
class BusinessFlight:
    source_id: str
    aircraft_no: str | None
    flight_no: str | None
    flight_date: dt.datetime | None
    scheduled_departure_at: dt.datetime | None
    scheduled_arrival_at: dt.datetime | None
    actual_departure_at: dt.datetime | None
    actual_arrival_at: dt.datetime | None
    departure_city: str | None
    arrival_city: str | None
    departure_airport: str | None
    arrival_airport: str | None
    status_label: str | None


@dataclass(frozen=True, slots=True)
class BusinessRoutineTask:
    source_id: str
    aircraft_no: str | None
    task_type: str | None
    task_type_name: str | None
    task_status_code: str | None
    task_status_name: str | None
    bay: str | None
    planned_start_at: dt.datetime | None
    inbound_flight_no: str | None
    inbound_date: dt.datetime | None
    outbound_flight_no: str | None
    outbound_date: dt.datetime | None
    route_city: str | None


@dataclass(frozen=True, slots=True)
class BusinessCandidate:
    source: str
    source_id: str
    aircraft_no: str | None
    flight_no: str | None
    station: str | None
    task_type: str | None
    task_text: str | None
    time_start: dt.datetime | None
    time_end: dt.datetime | None
    source_updated_at: dt.datetime
    association_method: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BusinessCandidateResult:
    candidates: tuple[BusinessCandidate, ...]
    fetched_at: dt.datetime
    requested_aircraft: str | None
    requested_station: str | None


class BusinessDataClient(Protocol):
    """Read-only CHA business data source (flights / routine tasks)."""

    async def fetch_flights(
        self,
        date: dt.date,
    ) -> tuple[BusinessFlight, ...]:
        ...

    async def fetch_routine_tasks(
        self,
        date: dt.date,
    ) -> tuple[BusinessRoutineTask, ...]:
        ...


class InspectionBusinessCandidateService:
    """Candidate provider for InspectionRecord business association.

    This is **not** an automatic matcher. It returns candidates derived from
    the live-verified `/api/flights` and `/api/routine-tasks` fields, bounded
    by inspection time/device/optional aircraft/station. First-version
    association methods are `SOURCE_DIRECT` (fields come directly from the
    record) and `USER_CONFIRMED`/`MANUAL_ENTRY` (set by the inspection flow).
    `DERIVED` appears only as auxiliary evidence, never as confirmation.
    """

    def __init__(
        self,
        client: BusinessDataClient,
        source_timezone: dt.tzinfo = SHANGHAI,
        window_minutes: int = 360,
        adjacent_days: int = 1,
    ) -> None:
        self._client = client
        self._source_timezone = source_timezone
        self._window_minutes = max(30, min(window_minutes, 1440))
        self._adjacent_days = max(0, min(adjacent_days, 3))

    async def find_candidates(
        self,
        *,
        inspection_started_at: dt.datetime,
        aircraft_no: str | None = None,
        station: str | None = None,
    ) -> BusinessCandidateResult:
        inspection = _aware_utc(inspection_started_at, "inspection_started_at")
        local = inspection.astimezone(self._source_timezone)
        fetched_at = dt.datetime.now(UTC)
        flights: list[BusinessFlight] = []
        tasks: list[BusinessRoutineTask] = []
        for offset in range(-self._adjacent_days, self._adjacent_days + 1):
            day = (local.date() + dt.timedelta(days=offset))
            flights.extend(
                await self._client.fetch_flights(day)
            )
            tasks.extend(
                await self._client.fetch_routine_tasks(day)
            )

        candidates: list[BusinessCandidate] = []
        for flight in flights:
            if not _matches(
                flight.aircraft_no,
                flight.departure_city,
                flight.arrival_city,
                requested_aircraft=aircraft_no,
                requested_station=station,
            ):
                continue
            window = _flight_window(flight)
            if not _in_window(inspection, window, self._window_minutes):
                continue
            candidates.append(
                BusinessCandidate(
                    source="flight",
                    source_id=flight.source_id,
                    aircraft_no=flight.aircraft_no,
                    flight_no=flight.flight_no,
                    station=_station_label(flight),
                    task_type=None,
                    task_text=(
                        f"{flight.flight_no or ''} "
                        f"{flight.departure_city or ''}→"
                        f"{flight.arrival_city or ''}".strip()
                    ),
                    time_start=(
                        flight.actual_departure_at
                        or flight.scheduled_departure_at
                    ),
                    time_end=(
                        flight.actual_arrival_at
                        or flight.scheduled_arrival_at
                    ),
                    source_updated_at=fetched_at,
                    association_method="SOURCE_DIRECT",
                    evidence=("flight_live_fields", "time_proximity"),
                )
            )

        for task in tasks:
            station_matches = True
            if station:
                station_needle = station.strip().casefold()
                if station_needle:
                    station_matches = bool(
                        (task.bay and station_needle in task.bay.casefold())
                        or (
                            task.route_city
                            and station_needle in task.route_city.casefold()
                        )
                    )
            if not station_matches or not _matches(
                task.aircraft_no,
                task.route_city,
                None,
                requested_aircraft=aircraft_no,
                requested_station=None,
            ):
                continue
            window = _task_window(task)
            if not _in_window(inspection, window, self._window_minutes):
                continue
            candidates.append(
                BusinessCandidate(
                    source="routine_task",
                    source_id=task.source_id,
                    aircraft_no=task.aircraft_no,
                    flight_no=(
                        task.outbound_flight_no or task.inbound_flight_no
                    ),
                    station=task.bay,
                    task_type=(
                        f"{task.task_type or ''} {task.task_type_name or ''}"
                    ).strip() or None,
                    task_text=(
                        f"{task.task_type_name or task.task_type or ''} "
                        f"{task.aircraft_no or ''} "
                        f"{task.route_city or ''}".strip()
                    ),
                    time_start=(
                        task.planned_start_at
                        or task.inbound_date
                        or task.outbound_date
                    ),
                    time_end=(
                        task.outbound_date or task.inbound_date
                    ),
                    source_updated_at=fetched_at,
                    association_method="SOURCE_DIRECT",
                    evidence=("routine_task_live_fields", "time_proximity"),
                )
            )

        # Deduplicate by (source, source_id): adjacent-day fetches may return
        # the same flight/task; keep the first occurrence only.
        unique: dict[tuple[str, str], BusinessCandidate] = {}
        for candidate in candidates:
            unique.setdefault(
                (candidate.source, candidate.source_id),
                candidate,
            )
        candidates = list(unique.values())
        candidates.sort(
            key=lambda item: (
                item.source,
                item.source_id,
            )
        )
        return BusinessCandidateResult(
            candidates=tuple(candidates),
            fetched_at=fetched_at,
            requested_aircraft=aircraft_no,
            requested_station=station,
        )


def normalize_flight_row(
    row: Mapping[str, Any],
    *,
    source_timezone: dt.tzinfo = SHANGHAI,
) -> BusinessFlight | None:
    source_id = _text(row.get("flightId"))
    if not source_id:
        return None
    return BusinessFlight(
        source_id=source_id,
        aircraft_no=_text(row.get("acno")),
        flight_no=_text(row.get("flightNo")),
        flight_date=_source_time(row.get("flightDate"), source_timezone),
        scheduled_departure_at=_source_time(row.get("std"), source_timezone),
        scheduled_arrival_at=_source_time(row.get("sta"), source_timezone),
        actual_departure_at=_source_time(row.get("atd"), source_timezone),
        actual_arrival_at=_source_time(row.get("ata"), source_timezone),
        departure_city=_text(row.get("dep3code")),
        arrival_city=_text(row.get("arr3code")),
        departure_airport=_text(row.get("departureAirport")),
        arrival_airport=_text(row.get("arrivalAirport")),
        status_label=_text(row.get("status")),
    )


def normalize_routine_task_row(
    row: Mapping[str, Any],
    *,
    source_timezone: dt.tzinfo = SHANGHAI,
) -> BusinessRoutineTask | None:
    source_id = _text(row.get("taskid"))
    if not source_id:
        return None
    return BusinessRoutineTask(
        source_id=source_id,
        aircraft_no=_text(row.get("acno")),
        task_type=_text(row.get("taskType")),
        task_type_name=_text(row.get("taskTypeName")),
        task_status_code=_text(row.get("tasksts")),
        task_status_name=_text(row.get("taskstsName")),
        bay=_text(row.get("bay")),
        planned_start_at=_source_time(
            row.get("startPlanDate"),
            source_timezone,
        ),
        inbound_flight_no=_text(row.get("inFlightNo")) or None,
        inbound_date=_source_time(row.get("inDate"), source_timezone),
        outbound_flight_no=_text(row.get("outFlightNo")) or None,
        outbound_date=_source_time(row.get("outDate"), source_timezone),
        route_city=_text(row.get("outFlight")),
    )


def sanitize_task_raw(row: Mapping[str, Any]) -> dict[str, Any]:
    """Drop RESTRICTED person fields from a raw routine-task row."""

    return {
        key: value
        for key, value in row.items()
        if key not in RESTRICTED_TASK_FIELDS
    }


def _matches(
    candidate_aircraft: str | None,
    candidate_city_a: str | None,
    candidate_city_b: str | None,
    *,
    requested_aircraft: str | None,
    requested_station: str | None,
) -> bool:
    if requested_aircraft:
        needle = requested_aircraft.strip().casefold()
        if not needle:
            pass
        elif not candidate_aircraft or needle not in candidate_aircraft.casefold():
            return False
    if requested_station:
        station = requested_station.strip().casefold()
        if station:
            haystacks = [candidate_city_a, candidate_city_b]
            if not any(
                value and station in value.casefold()
                for value in haystacks
            ):
                return False
    return True


def _flight_window(
    flight: BusinessFlight,
) -> tuple[dt.datetime | None, dt.datetime | None]:
    return (
        flight.actual_departure_at or flight.scheduled_departure_at,
        flight.actual_arrival_at or flight.scheduled_arrival_at,
    )


def _task_window(
    task: BusinessRoutineTask,
) -> tuple[dt.datetime | None, dt.datetime | None]:
    start = (
        task.planned_start_at
        or task.inbound_date
        or task.outbound_date
    )
    end = task.outbound_date or task.inbound_date
    return start, end


def _in_window(
    inspection: dt.datetime,
    window: tuple[dt.datetime | None, dt.datetime | None],
    window_minutes: int,
) -> bool:
    start, end = window
    if start is None and end is None:
        return False
    delta = dt.timedelta(minutes=window_minutes)
    if start is not None:
        start_utc = start.astimezone(UTC)
        if start_utc - delta <= inspection <= start_utc + delta:
            return True
    if end is not None:
        end_utc = end.astimezone(UTC)
        if end_utc - delta <= inspection <= end_utc + delta:
            return True
    return False


def _station_label(flight: BusinessFlight) -> str | None:
    if flight.arrival_city:
        return flight.arrival_city
    if flight.departure_city:
        return flight.departure_city
    return flight.arrival_airport or flight.departure_airport


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_time(
    value: Any,
    source_timezone: dt.tzinfo,
) -> dt.datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = dt.datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=source_timezone)
    return parsed.astimezone(UTC)


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


class LegacyBusinessDataClient:
    """``BusinessDataClient`` backed by the existing CHA Legacy service.

    Reads flights and routine tasks through the allow-listed LegacyClient
    (which forwards the current browser's CHA session cookie). This is a
    read-only reference source for the operational dashboard; it never
    associates anything automatically.
    """

    def __init__(
        self,
        legacy_client: Any,
        *,
        source_timezone: dt.tzinfo = SHANGHAI,
        cookie: str = "",
    ) -> None:
        self._legacy = legacy_client
        self._source_timezone = source_timezone
        self._cookie = cookie

    def with_cookie(self, cookie: str) -> "LegacyBusinessDataClient":
        return LegacyBusinessDataClient(
            self._legacy,
            source_timezone=self._source_timezone,
            cookie=cookie,
        )

    async def fetch_flights(
        self,
        date: dt.date,
    ) -> tuple[BusinessFlight, ...]:
        response = await self._legacy.flights(
            self._cookie,
            date.isoformat(),
        )
        payload = response.json()
        rows = _payload_rows(payload)
        return tuple(
            flight
            for row in rows
            if (flight := normalize_flight_row(
                row,
                source_timezone=self._source_timezone,
            )) is not None
        )

    async def fetch_routine_tasks(
        self,
        date: dt.date,
    ) -> tuple[BusinessRoutineTask, ...]:
        response = await self._legacy.routine_tasks(
            self._cookie,
            date.isoformat(),
        )
        payload = response.json()
        rows = _payload_rows(payload)
        return tuple(
            task
            for row in rows
            if (task := normalize_routine_task_row(
                row,
                source_timezone=self._source_timezone,
            )) is not None
        )


def _payload_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, dict):
        for key in ("records", "data", "rows", "list", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    return []
