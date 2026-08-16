# M4 P3 — Flights / Routine Tasks Field Evidence

Date: `2026-08-16`

Status: `LIVE VERIFIED (authorized CHA session, 2026-08-16) + CODE VERIFIED`

Purpose: confirm which real business objects an `InspectionRecord` can offer
for user selection (candidate + human confirmation). This is **not** an
automatic matcher; no relation is auto-confirmed.

## 1. Endpoint evidence (Legacy allow-list, code-verified)

| Endpoint | Params | Response shape observed in code |
| --- | --- | --- |
| `/api/flights` | `date`, `current=1`, `size=100` | dict with `total` and `records` |
| `/api/routine-tasks` | `date`, `current=1`, `size=100` | dict with `total` and `records` |

The M2 dashboard service consumes `flights.total`, `routine_tasks.total` and
`flights.records[:6]` as a preview. Individual flight row fields are not
consumed by the reviewed V2 code.

## 1.1 Live evidence (2026-08-16, authorized CHA session, read-only)

`/api/flights?date=2026-08-16&current=1&size=3` → HTTP 200,
`total=39`. Envelope: `records/total/size/current/orders/pages`.

`/api/routine-tasks?date=2026-08-16&current=1&size=3` → HTTP 200,
`total=48`. Envelope: same shape.

Personally-identifiable fields (`fxWorker`, `fxWorkerEmp`, `wxWorker`,
`wxWorkerEmp`) were observed in the response and are treated as
`RESTRICTED`; their values are **not** persisted anywhere.

## 1.2 Flight row fields (LIVE VERIFIED)

| Raw field | Example (sanitized) | Meaning | Status |
| --- | --- | --- | --- |
| `flightId` | 487663 | stable flight source id | AVAILABLE |
| `acno` | B-224N | aircraft number | AVAILABLE |
| `flightNo` | JG2646 | flight number | AVAILABLE |
| `flightDate` | 2026-08-16 00:00:00 | flight date | AVAILABLE |
| `sta` | 2026-08-16 08:45:00 | scheduled arrival | AVAILABLE |
| `std` | 2026-08-16 05:45:00 | scheduled departure | AVAILABLE |
| `etd` / `atd` | 05:45:00 / 05:38:57 | estimated / actual departure | AVAILABLE |
| `eta` / `ata` | 08:19:00 / 08:19:30 | estimated / actual arrival | AVAILABLE |
| `dep3code` | 深圳/宝安 | departure city/airport display | AVAILABLE (business location) |
| `arr3code` | 北京/大兴 | arrival city/airport display | AVAILABLE (business location) |
| `departureAirport` / `arrivalAirport` | ZGSZ / ZBAD | airport codes | AVAILABLE |
| `status` | 正常 | flight status label | AVAILABLE (label; code map PARTIAL) |
| `dorI` | D | domestic/international marker | PARTIAL / UNKNOWN |
| `focUser` | null | operator reference | RESTRICTED when populated |
| `dd` / `fc` / `nonWork` | 0 / 17 / null | codes | UNKNOWN / PARTIAL |

## 1.3 Routine-task row fields (LIVE VERIFIED)

| Raw field | Example (sanitized) | Meaning | Status |
| --- | --- | --- | --- |
| `taskid` | TSK-4886281 | stable task source id | AVAILABLE |
| `acno` | B-226S | aircraft number | AVAILABLE |
| `taskType` / `taskTypeName` | AP / 航前 | task type code + label | AVAILABLE |
| `tasksts` / `taskstsName` | 9 / 已交接 | task status code + label | AVAILABLE (code map partial) |
| `bay` | 710 | bay / station | AVAILABLE (station-like) |
| `startPlanDate` | 2026-08-15 23:35:00 | planned start | AVAILABLE |
| `outFlightNo` / `outDate` / `outDateType` | JG2671 / 00:50:37 / 2 | outbound flight + time | AVAILABLE (date-type code map partial) |
| `inFlightNo` / `inDate` / `inDateType` | "" / null / null | inbound flight + time | AVAILABLE (nullable) |
| `outFlight` / `inFlight` | 重庆/江北-芜湖/宣州 / "-" | route city display | AVAILABLE (business location) |
| `acType` / `engType` | B737NG / CFM56-7B | aircraft/engine type | AVAILABLE |
| `flightDate` / `cobt` | 2026-08-16 / 00:38:50 | task flight date / pushback time | AVAILABLE / PARTIAL |
| `workPackage` | 1 | work package | PARTIAL / UNKNOWN |
| `dd` / `fc` / `nonWork` / `doneNonWork` / `repeatWork` | 0 | codes | UNKNOWN / PARTIAL |
| `alarmCount` / `oxygenT` / `oxygenP` / `oxygenPb` / `oxygenY` | null | operational codes | UNKNOWN / PARTIAL |
| `fxWorker` / `fxWorkerEmp` / `wxWorker` / `wxWorkerEmp` | (person) | worker name + employee no | RESTRICTED (not persisted) |

## 2. Routine-task row fields (STATIC / CODE-VERIFIED)

## 2. Routine-task row fields (STATIC / CODE-VERIFIED)

From `docs/data/LEGACY_MEDIA_BUSINESS_REFERENCE_AUDIT.md` and the Legacy
batch matcher code:

| Raw field | Meaning (code-evidenced) | Status |
| --- | --- | --- |
| `taskid` | routine task identity | AVAILABLE (stable dedup candidate) |
| `id` | record id | AVAILABLE |
| `inFlight` | inbound route (city list) | AVAILABLE |
| `outFlight` | outbound route (city list) | AVAILABLE |
| `outDate` | outbound planned/actual date | DERIVABLE (candidate time) |
| `inDate` | inbound planned/actual date | DERIVABLE (candidate time) |
| `startPlanDate` | plan-start date | DERIVABLE (candidate time) |
| time-type code | `1`=planned, `2`=actual, `3`=estimated (code map) | PARTIAL / UNKNOWN beyond 1/2/3 |

Route-city candidate rules (code-evidenced, `DERIVED` only):

* outbound: media city == first city of `outFlight`, media time in
  `[outDate-360m, outDate]`;
* inbound: media city == last city of `inFlight`, media time in
  `[inDate, inDate+360m]`;
* plan-start: matched route city + `|media_time - startPlanDate| <= 360m`.

## 3. Target InspectionRecord business fields

InspectionRecord needs: `aircraft_no`, `flight_no`, `station`,
`flight_source_id`, `routine_task_source_id`, `maintenance_task_text`,
planned/actual times, department/team, task type/name/status.

| Field | Status (today) | Evidence needed |
| --- | --- | --- |
| `aircraft_no` | UNKNOWN (structured) | real sanitized flight/task sample |
| `flight_no` | UNKNOWN | real sanitized flight sample |
| `station`/`airport`/`city` | DERIVABLE via route-city match | coordinate/city-map validation before use |
| `routine_task_source_id` (`taskid`) | AVAILABLE (code-verified) | confirm stable across windows |
| `maintenance_task_text` | UNKNOWN | real sample; manual fallback allowed |
| `task_type`/`task_name`/`task_status` | UNKNOWN | real sample |
| `planned_start`/`planned_end`/`actual_*` | PARTIAL (`outDate`/`inDate`/`startPlanDate` + time-type) | map exact source fields |
| `department`/`team` | UNKNOWN | real sample |

## 4. Decision

* P3 first release uses `routine_task_source_id` / `aircraft_no` /
  `flight_no` / `station` / `maintenance_task_text` as **user-confirmed or
  manually-entered** values; `association_method` is recorded.
* Until a real sanitized `/api/flights` and `/api/routine-tasks` response is
  captured and field-verified, structured flight/task fields stay
  `UNKNOWN`/`DERIVABLE` and are never auto-filled as source truth.
  (LIVE capture 2026-08-16 completed: flight/task core fields are
  `AVAILABLE`; worker names/emps remain `RESTRICTED` and are never persisted.)
* No automatic matcher; candidate queries are bounded by inspection
  time/device and returned for human confirmation only.
