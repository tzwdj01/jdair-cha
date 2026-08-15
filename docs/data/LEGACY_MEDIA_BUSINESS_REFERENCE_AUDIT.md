# Legacy Media-to-Flight/Task Reference Audit

Last reviewed: `2026-08-15`

Status: `CODE-AUDITED / HEURISTIC / NOT BUSINESS-VERIFIED`

Source reviewed:

`releases/20260812212342-layout-redesign-phase5/mcs8_web_panel.py`

This audit describes the existing Legacy “reference information” feature. It
does not approve the heuristic as M4 source truth and does not add a production
data path.

## 1. Active request path

The records page sends, for at most 100 displayed media rows:

* device ID;
* title;
* start/file/begin time;
* latitude and longitude when present.

Authenticated Legacy endpoint:

`POST /api/record-flight-references`

The endpoint calls `match_record_flight_references`.

Important finding:

* the batch matcher fetches `routine_tasks_for_reference_day`;
* it does **not** call `flights_near_day`;
* `flights_near_day` has no active call site in the reviewed release;
* therefore the active endpoint currently generates routine-task candidates,
  not ordinary flight-dynamics candidates, despite generic flight-matching code
  and flight-oriented names/UI labels.

## 2. Media time evidence

`record_shoot_datetime` selects the first parseable value from:

1. `startTime`;
2. `fileTime`;
3. `beginTime`;
4. `shootTime`;
5. filename/title pattern `_YYYYMMDD_HHMMSS`.

Risks:

* parsed values are naive local datetimes;
* source timezone is not explicit;
* filename-derived time is not separately labeled as derived;
* no source-time confidence or correction metadata is retained.

M4 decision:

* normalized media source time must be preferred;
* filename parsing, if later retained, must be a separate derivation source and
  quality flag;
* no relation can be marked verified when media time is missing or ambiguous.

## 3. Position and city evidence

Position selection:

1. use coordinates carried by the media row;
2. otherwise query MCS8 `/api/GetGpsModelList` for the same device from two
   hours before to two hours after the media time;
3. inspect only page 1 with `pagesize=5000`;
4. choose the nearest valid GPS point;
5. accept it only when the absolute time difference is at most 7,200 seconds.

The coordinate is converted to a city using the local offline geocoder and a
hard-coded city/airport alias map.

Risks:

* no pagination completeness check beyond the first 5,000 rows;
* no GPS accuracy, source type, coordinate system or sampling cadence check;
* a point nearly two hours away can be treated as the media location;
* city-level equality is the only spatial relation;
* the alias map is code-local and unversioned;
* GPS/geocoder failures are swallowed and appear as no position.

M4 decision:

* position source, GPS time delta, geocoder/mapping version and data-quality
  flags must be explicit relation evidence;
* no city match alone can create a confirmed relation;
* coordinates remain restricted and must not be copied into summary metrics.

## 4. Reference-data scope

For every media shooting date, the active batch path queries routine tasks for:

* previous day;
* same day;
* next day.

Each day reads up to ten pages of 100 rows. Rows are deduplicated by:

1. `taskid`;
2. `id`;
3. fallback aircraft/flight/date composite.

The matcher recognizes a row as a routine task when `taskid`, `inFlight` or
`outFlight` is present.

Risks:

* page 10 is a silent upper boundary;
* source-total completeness is not returned to the caller;
* fallback identity is not proven stable;
* query failures become empty day results;
* the output does not expose which days/pages were incomplete.

## 5. Active routine-task candidate rules

Outbound candidate:

* media city equals the first city in `outFlight`;
* media time is from zero to 360 minutes before `outDate`.

Inbound candidate:

* media city equals the last city in `inFlight`;
* media time is from zero to 360 minutes after `inDate`.

Plan-start candidate:

* at least one inbound/outbound route city already matched;
* absolute difference from `startPlanDate` is at most 360 minutes.

Time-type labels currently map:

* `2` to actual departure/arrival;
* `1` to planned departure/arrival;
* `3` to estimated;
* other populated values to generic inbound/outbound.

Direction preference:

* task type `AF` prefers inbound;
* task type `AP` prefers outbound;
* otherwise outbound is preferred when available.

These code maps and task-type meanings are `AMRO VERIFICATION REQUIRED`.

## 6. Legacy score and certainty

The current score is a fixed heuristic based mainly on absolute time distance:

| Time difference | Base score |
| --- | --- |
| up to 30 minutes | 96 |
| up to 60 minutes | 90 |
| up to 120 minutes | 78 |
| up to 240 minutes | 62 |
| otherwise | 45 |

Adjustments:

* actual time: `+2`;
* planned time: `-3`;
* routine `startPlanDate` candidate: additional `+5`.

The result is labeled relatively clear when:

* top score is at least 90; and
* there is no second candidate, or the score gap is at least 12.

Otherwise one to three candidates are shown.

Risks:

* score weights have no recorded business validation;
* city and time can produce a high score without aircraft, work order, device
  assignment or visual confirmation;
* “较明确” is not equivalent to confirmed;
* coverage numerator/denominator cannot use this label as ground truth.

M4 decision:

* do not migrate the numeric score or certainty labels as verified semantics;
* all generated relations remain `candidate`;
* `confirmed` can become true only through an explicit governed source or
  human confirmation;
* matcher version and individual reason codes must be retained.

## 7. Dormant ordinary-flight path

The generic single-row matcher contains ordinary flight rules:

* departure city match and media within six hours before departure;
* arrival city match and media within six hours after arrival;
* actual time preferred over estimated, then planned;
* cancelled flights excluded unless an actual event time exists.

However, the active batch endpoint does not supply ordinary flight rows.

Classification:

`REFERENCE CODE ONLY / NOT ACTIVE CAPABILITY`

It must not be represented in the M4 availability matrix as an implemented
media-to-flight relation.

## 8. Capability classification

* AMRO flight/routine list queries: `Class A`.
* GPS/media/AMRO evidence normalization: `Class C`.
* candidate generation and confirmation workflow: `Class C`.
* Legacy UI labels, score glue and flight-oriented naming: `Class D`.

## 9. M4 implementation gate

Before implementing a production relation matcher, obtain sanitized evidence
for:

1. stable flight and routine-task identity fields;
2. timezone and correction semantics for every reference time;
3. task type and date-type code maps;
4. source pagination/retention completeness;
5. real media examples with independently confirmed flight/task outcomes;
6. acceptable false-positive/false-negative criteria;
7. aircraft/device/work-order relationship availability;
8. confirmation and audit workflow.

Until then:

* normalized dimensions may be designed;
* a candidate contract may be documented;
* no automatic confirmed relation or coverage rate may be produced;
* the existing Legacy heuristic remains a user aid, not M4 source truth.
