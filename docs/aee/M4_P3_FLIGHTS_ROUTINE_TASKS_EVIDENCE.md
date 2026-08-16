# M4 P3 — Flights / Routine Tasks Field Evidence

Date: `2026-08-16`

Status: `CODE/STATIC VERIFIED (Legacy) — LIVE SAMPLE REQUIRED for full schema`

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
* No automatic matcher; candidate queries are bounded by inspection
  time/device and returned for human confirmation only.
