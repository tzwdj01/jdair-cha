# Current CHA Data Capabilities

Last reviewed: `2026-08-15`

Status: `M4 BASELINE / CODE-AUDITED / DATA FOUNDATION IMPLEMENTED`

## 1. Scope and evidence

This document records the data capabilities that exist in the current Git
repository. It does not treat a field as production-verified merely because a
name appears in code.

Primary evidence:

* `mature-modernization/v2/app/services/dashboard.py`
* `mature-modernization/v2/app/services/legacy.py`
* `mature-modernization/v2/app/services/trend_store.py`
* `mature-modernization/v2/app/realtime/*`
* current Legacy implementation:
  `releases/20260812212342-layout-redesign-phase5/mcs8_web_panel.py`
* existing automated tests under `mature-modernization/v2/tests`
* M3 Production Canary and AEE evidence documents

Status vocabulary:

* `CURRENT`: a current or near-current value can be queried.
* `HISTORY`: historical rows or events can be queried.
* `SAMPLED`: CHA stores bounded observations, not source events.
* `RUNTIME ONLY`: process memory is lost on restart.
* `NOT PERSISTED`: no durable CHA history exists.
* `CODE-AUDITED`: confirmed in repository code but not yet revalidated against
  a live response in M4.

## 2. Current architecture

```text
Browser CHA session
        |
        v
FastAPI V2 DashboardService
        |
        +-- LegacyClient allow-listed HTTP adapter
        |      |
        |      +-- /api/devices
        |      +-- /api/video-stats
        |      +-- /api/records
        |      +-- /api/flights
        |      +-- /api/routine-tasks
        |
        +-- process-local TTL cache
        +-- device-trend.json sampled aggregate snapshots

Realtime browser
        |
        v
RealtimeSessionManager
        |
        +-- process-local sessions and streams
        +-- process-local telemetry counters/durations
        +-- finalized RealtimeViewEvent sink contract
        +-- no durable RealtimeViewEvent repository yet
```

The current V2 Dashboard is predominantly a read-only aggregation layer over
Legacy. It is not yet an independent long-term data asset.

The first M4 deterministic aggregation and read-only transport foundations now
exist under `mature-modernization/v2/app/data`. They are deliberately isolated
from API, scheduler and database concerns and therefore do not yet change
production data flow.

## 3. Authentication and user identity

| Field / capability | Source | Refresh | Current | History | Drill-down | Persisted | Trust | Legacy dependency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| authenticated | `/api/auth/session` | per Dashboard session cache, currently device TTL | yes | no | no | no | high | yes |
| username | `/api/auth/session` | same as above | yes | no | used as `generated_for` | no | high | yes |
| stable user id | not exposed by current V2 adapter | n/a | no | no | no | no | unknown | unknown |
| login time | not exposed | n/a | no | no | no | no | not available | unknown |
| logout time | not exposed | n/a | no | no | no | no | not available | unknown |
| last active | not exposed | n/a | no | no | no | no | not available | unknown |

Realtime derives:

* `owner_name` from the authenticated Legacy session username.
* `owner_key` as a hash of the authenticated session context for ownership
  isolation.

These values currently remain in process memory and are not a usage-history
dataset.

## 4. Device inventory and current status

Legacy `/api/devices` calls `merged_devices()`.

Device sources:

1. MCS8 `/api/GetDevListByGroupId`, currently cached for 30 seconds.
2. Legacy log-derived `DeviceStatus`, `allDevOnline`, GPS and last-seen values
   where available.
3. a bounded local device catalog fallback.
4. location-derived city and local warehouse mapping.

The current implementation filters to maintenance-department devices whose
group is `30000002` and whose device name begins with `JDTY`.

| Exposed field | Source / derivation | Freshness | History | Persisted | Trust / caveat |
| --- | --- | --- | --- | --- | --- |
| `devId` | MCS8 device catalog | catalog TTL 30 s | no | catalog fallback only | high identity value |
| `name` | `deviceName` / `szName` / equivalent | catalog TTL 30 s | no | catalog fallback only | high |
| `roomId` | catalog or constructed group room | catalog TTL 30 s | no | catalog fallback only | medium |
| `groupName` | catalog/group mapping | catalog TTL 30 s | no | catalog fallback only | medium-high |
| `online` | latest status map, else catalog `nOnline/online` | current observation | no | no | current value; no transition semantics |
| `lng`, `lat` | latest GPS, else catalog | latest observed point | GPS history exists separately | no V2 history | valid-coordinate checks exist only in track query |
| `gpsTime` | latest GPS/catalog | source-defined | GPS history exists separately | no V2 history | source time semantics need normalization |
| `lastOnlineTime` | log last-seen, GPS time or catalog GPS time | source-defined | no | no | **not proven to be an online-transition timestamp** |
| `city` | offline geographic lookup from coordinates | follows coordinates | derivable from GPS track | cache only | derived |
| `cityDistanceKm` | geographic lookup result | follows coordinates | no | cache only | derived |
| `recentCities` | recent GPS query, currently 3-day scope | cache TTL 600 s | yes, bounded source query | cache only | current implementation warms asynchronously |
| `warehouse` | local device-name mapping | configuration-defined | no | local mapping | operational mapping, not MCS8 truth |
| `catalog` | raw source metadata | catalog TTL 30 s | no | fallback file | schema is not normalized or guaranteed stable |

Important limitation:

`lastOnlineTime` currently means the latest observed device-related timestamp,
not a verified `last_online_at` event. It must not be used directly for online
duration, offline count or daily online-rate metrics.

## 5. Device location and GPS history

Legacy has `/api/gps-track`, backed by MCS8 `/api/GetGpsModelList`.

Current normalized point fields:

| Field | Current availability | Notes |
| --- | --- | --- |
| `lat`, `lng` | available | invalid/zero coordinates are rejected |
| `time` | available | selected from `gpsTime/dateTime/time` |
| `speed` | available | defaults to 0 when absent |
| `direct` | available | selected from `direct/direction` |
| `accuracy` | available | defaults to 0 |
| `battery` | available raw | semantics and units require AEE/MCS8 verification |
| `gpsType` | available raw | semantics require cataloging |
| `networkType` | available raw | selected from `netWorkType` |

Derived track values:

* source point count;
* sampled point count;
* approximate distance, excluding segments over 20 km;
* maximum speed;
* start and end time.

Current gaps:

* `/api/gps-track` is not allow-listed by the V2 `LegacyClient`.
* no CHA durable `DeviceLocationEvent` table exists.
* V2 now has a pure, unwired `DeviceLocationEvent` normalization contract for
  per-device Legacy GPS-history rows:
  * source, observation and ingestion times are separated and normalized to
    UTC;
  * the queried device ID is an explicit scope boundary, and conflicting row
    device IDs are rejected;
  * global coordinate range and the Legacy zero-coordinate sentinel are
    validated;
  * missing speed, direction, accuracy and battery remain `None` rather than
    being converted to zero;
  * coordinate system, measurement units, battery semantics and GPS/network
    code maps remain explicit quality flags;
  * future source timestamps are retained but marked.
* the contract is not connected to `LegacyClient`, a scheduler, PostgreSQL, an
  API or production configuration.
* no evidence-backed stale/late-arrival threshold, coordinate-system map or
  measurement-unit map exists yet.

## 6. Media files and records

Legacy `/api/records` calls MCS8 `/api/GetRecordFileList`.

Query dimensions currently supported by Legacy:

* start and end time;
* page and page size;
* device ID or device name/group search;
* city, implemented by first resolving matching device IDs;
* platform mode.

Current response behavior:

* returns raw upstream rows under `data`;
* adds normalized `devId` and, where possible, `deviceName`;
* reports `recordsTotal`, pagination, source and partial-query state;
* device-file mode is explicitly reported unsupported.

Fields recognized by current UI/code:

| Logical field | Recognized upstream names | Current normalization |
| --- | --- | --- |
| device | `devId`, `DevId`, `szIDNO` | normalized to `devId` |
| device name | `deviceName`, `devName` | normalized when possible |
| title/name | `fileName`, `name`, `fileTitle` | UI fallback only |
| create/shoot time | `startTime`, `fileTime`, `beginTime`, filename timestamp | partial helper |
| upload/end time | `uploadTime`, `upLoadTime`, `endTime` | UI fallback only |
| size | `fileSize`, `fileLen`, `size` | aggregate/UI conversion only |
| duration | `duration`, `videoTime` | UI conversion only |
| object key | multiple raw row fields, consumed by playback helpers | no stable V2 schema |

Not yet normalized:

* file type;
* media kind;
* upload status;
* storage backend;
* source;
* channel;
* codec;
* checksum;
* stable media-file identity.

### Three-day video statistics

Legacy `/api/video-stats` scans up to 50 pages of records for the preceding
three days and returns per-device:

* `count`;
* `sizeMB`.

V2 cache TTL is 180 seconds.

This is a bounded current aggregate. It is not a durable media index.

### Video trend

`DashboardService._load_video_trend()` queries one record-count result per day
for 1–30 days.

Properties:

* global scope only;
* count only;
* queried on demand;
* V2 cache TTL 300 seconds;
* no durable daily aggregate table.

## 7. Flights

Legacy `/api/flights` is backed by the AMRO flight task API.

Current V2 behavior:

* queries only the current business date in Dashboard;
* page size up to 100;
* cache TTL 60 seconds;
* passes raw `records` and `total`;
* exposes only a six-row preview in the M2 Dashboard response;
* does not persist flight snapshots or normalize a stable flight model.

Legacy supports:

* date;
* keyword;
* domestic/international category;
* departure city;
* arrival city;
* pagination;
* detail lookup.

Fields visibly consumed by the Legacy UI include flight number, aircraft
registration, departure/arrival information, status, domestic/international
flag and operational times. A formal M4 field catalog still needs a sanitized
live response.

## 8. Routine tasks

Legacy `/api/routine-tasks` is backed by the AMRO routine-task APIs.

Current V2 behavior:

* current business date only;
* cache TTL 300 seconds;
* raw `records` and `total`;
* six-row preview only;
* no durable task history or normalized task model.

Legacy query dimensions:

* flight date;
* keyword;
* category;
* task type;
* aircraft type;
* task status;
* site;
* aircraft registration;
* pagination.

Legacy also supports detail and process-step queries. These are not currently
allow-listed by `LegacyClient`.

### Legacy media reference heuristic

The production-baseline Legacy release has an authenticated
`POST /api/record-flight-references` helper used by the records table.

Code audit findings:

* media time comes from source time aliases, then a filename timestamp fallback;
* media coordinates are preferred, otherwise the nearest per-device GPS point
  within plus/minus two hours is used;
* matching is city-level and applies fixed six-hour time windows;
* the active batch path fetches only routine tasks for the previous/current/next
  day;
* the generic ordinary-flight matcher and `flights_near_day` helper are not
  connected to the active endpoint;
* score/certainty thresholds are fixed Legacy heuristics with no recorded
  business validation;
* pagination/source failures are not surfaced as completeness metadata.

Therefore:

* current active media-to-routine-task matching is a
  `HEURISTIC / UNVERIFIED CANDIDATE`;
* current active media-to-flight matching is `NOT AVAILABLE` even though dormant
  generic code exists;
* neither path can provide a verified relation or coverage numerator.

Full evidence and decision:

`docs/data/LEGACY_MEDIA_BUSINESS_REFERENCE_AUDIT.md`

## 9. Realtime session and telemetry data

### Runtime session data

`RealtimeSessionManager` currently has:

* `session_id`;
* `owner_name`;
* owner-isolation key;
* session create/update/heartbeat/expiry/close times;
* session status;
* stream IDs and device IDs;
* stream create/update/first-frame/close times;
* width and height;
* track state;
* result/error code;
* audio runtime state when enabled.

### Process-local telemetry

Current gauges include:

* active/playing/degraded sessions;
* active/playing/failed streams;
* Gateway and Media connections;
* retained session count.

Current counters include:

* session create/close/timeout cleanup;
* stream open/close;
* first-frame timeout;
* abnormal disconnect;
* release failure;
* screenshot success/failure;
* audio open/close/failure.

Current durations include AEE login, Gateway/Media connect, session lifecycle,
stream lifecycle and first-frame timing where observed.

Limitations:

* all telemetry resets on process restart;
* no per-user or per-device historical aggregation exists;
* retained closed sessions are bounded operational diagnostics, not analytics;
* no durable `RealtimeViewEvent` repository exists.

The current runtime now finalizes a normalized `RealtimeViewEvent` through an
opt-in sink boundary. The contract covers first-frame, close, timeout,
disconnect and shutdown paths without storing runtime media objects. Durable
PostgreSQL persistence, replay/outbox behavior and analytics queries remain
unimplemented.

## 10. Existing Dashboard outputs

Current V2 APIs:

* `GET /api/v2/dashboard/overview`
* `GET /api/v2/dashboard/device-trend`
* `GET /api/v2/dashboard/video-trend`
* `GET /api/v2/dashboard/geography`
* `GET /api/v2/dashboard/coverage`
* `GET /api/v2/dashboard/exceptions`
* `GET /api/v2/dashboard/freshness`

Current metrics:

* total/online/offline devices and online rate;
* city count and city device distribution;
* three-day file count and size;
* devices/cities with recent files;
* on-demand 1–30 day file-count trend;
* today flight count;
* today routine-task count;
* offline, no-recent-file and stale-location exception candidates;
* per-source cache freshness and latency.

Current coverage limitations:

* flight-to-video coverage is not implemented; the active Legacy reference
  endpoint does not load ordinary flight rows;
* routine-task-to-video coverage is not implemented; Legacy has only an
  unverified candidate heuristic;
* device online trend is aggregate sampled snapshots only;
* city filtering does not apply to the global video trend;
* no durable historical metric store exists;
* the current page is a single M2 overview rather than the M4 multi-page data
  center.

## 11. M4 deterministic aggregation foundation

Implemented pure functions:

* `aggregate_device_uptime`
  * accepts AEE-style `devId/groupId/id/status/time` rows;
  * requires an explicit timezone-aware reporting window;
  * sorts and deduplicates status transitions;
  * uses the latest pre-window event to seed the initial state;
  * clips an open online interval to the requested `window_end`, never to the
    browser or ingestion current time;
  * exposes missing initial state, conflicting same-time statuses, invalid
    rows, duplicate removal and the provisional non-1 status rule as quality
    flags.
* `aggregate_media_files`
  * groups `RecordFileList` rows by device;
  * keeps video duration in source seconds and file size in source bytes;
  * counts image/audio/video/device-file types without UI rounding;
  * exposes invalid values, unknown types and query-limit/pagination
    truncation as quality flags.
* `aggregate_device_locations`
  * accepts only normalized `DeviceLocationEvent` rows and an explicit
    timezone-aware reporting window;
  * exposes per-device event count, distinct-coordinate count, source span,
    latest-event age and optional-measurement presence counts;
  * does not expose coordinates in its aggregate projection;
  * does not classify freshness or invent sampling coverage without a governed
    threshold/cadence;
  * removes exact duplicates, collapses same-position updates to the latest
    observation and excludes same-source/time coordinate conflicts.

Verification:

* eight focused unit tests cover sorting, deduplication, report-window
  clipping, pre-window state, missing state, conflicts, raw units and partial
  results;
* six focused transport tests cover the exact GET allowlist, custom `token`
  header, query encoding, bounded 401 retry, 403 handling, token redaction,
  response validation and base-URL hardening;
* six endpoint-contract tests cover timezone conversion, exact query
  parameters, pagination/`has_more`, invalid-row handling, unknown totals,
  range validation and bounded upstream errors;
* nine collection tests cover known/unknown totals, short-page completion,
  max-page/max-record limits, empty pages, changing totals, duplicate source
  IDs and invalid source rows;
* sixteen normalization tests cover source/observation/ingestion time
  separation, restricted location scope and coordinates,
  non-1 status uncertainty, field aliases, raw units, partial code maps,
  restricted-field minimization and malformed values;
* ten Realtime-view tests cover outcome/duration semantics, first-frame
  idempotency, normal close, timeout, session close, abnormal disconnect and
  sink failure isolation/retry;
* two AlarmList Adapter tests cover exact evidenced query fields and required
  unverified-selector values;
* six Alarm normalization tests cover required identity/time, raw codes,
  restricted-field minimization, push-status aliasing and malformed values;
* twelve event-metric tests cover location coverage/age values, location
  duplicate/update/conflict/range handling, Realtime user/device totals,
  duration recalculation, Alarm update collapse and unknown raw-status
  preservation;
* the current complete V2 backend suite passes `149 tests`.

Implemented read-only transport boundary:

* `AEEDataHTTPClient` accepts only the evidenced Class A GET paths;
* login/token ownership is injected and remains server-side;
* a 401 can invalidate an in-memory token and retry once;
* 403 and transport/JSON failures are mapped to bounded CHA-owned errors;
* no username, password, Cookie, token value or browser storage is read by the
  transport.
* `AEEReadOnlyDataAdapter` currently supports only:
  * `/api/v1/ext/DevTree`;
  * `/api/v1/DevOnlineList`;
  * `/api/v1/RecordFileList`;
  * `/api/v1/AlarmList`.
* ranged queries require explicit source timezone, required enterprise scope
  and bounded pagination;
* page envelopes expose `records_total`, `has_more`, invalid-row count and
  quality flags.
* `collect_aee_pages` follows page contracts with explicit operational limits
  and never converts a truncated or unstable result set into a complete one.
* duplicate upstream `id` values are reported but preserved until uniqueness
  scope is verified.

Implemented normalized historical contracts:

* `DeviceStatusEvent`
  * preserves source ID, device/group/type and raw status code;
  * normalizes source event time, observation time and ingestion time to UTC;
  * maps only verified `status==1` to `online=true`;
  * leaves non-1 status online state unknown until the status map is verified.
* `DeviceLocationEvent`
  * binds rows to an explicit queried device scope;
  * validates global coordinate bounds and the Legacy zero sentinel;
  * separates GPS source time, observation time and ingestion time;
  * keeps absent measurements null and preserves GPS/network source codes;
  * marks coordinates restricted and all unverified units/code maps as
    quality flags.
* `MediaFile`
  * normalizes verified device/title/time/size/duration/type aliases;
  * preserves raw list/source/upload/deletion codes with quality flags;
  * keeps file size in bytes and video duration in seconds;
  * omits personnel number/name and free-text description by default;
  * records the unverified upstream ID scope rather than claiming global
    uniqueness.
* `RealtimeViewEvent`
  * uses authenticated CHA username but never the login-session hash;
  * records stream/session/device correlation, first frame, resolution,
    bounded error and release outcome;
  * derives connection and actual post-first-frame viewing duration;
  * distinguishes played, timeout, failed, cancelled and abnormal disconnect;
  * finalizes idempotently through an optional sink on stream/session close,
    disconnect, TTL cleanup and server shutdown;
  * isolates sink failure from media cleanup and permits an idempotent retry.
* `AlarmEvent`
  * requires source alarm ID, device ID, raw alarm type and source alarm time;
  * preserves alarm/status/deal raw codes with partial-map flags;
  * leaves handled state and level unknown rather than inventing labels;
  * omits handler, handling time and free-text deal description by default;
  * exposes source-ID, lifecycle and deletion uncertainty explicitly.

Implemented deterministic event metrics:

* Realtime:
  * exact supplied-scope totals and user/device groupings;
  * connection/view duration and first-frame latency recalculated from event
    timestamps;
  * played/result/error distributions;
  * duplicate removal, conflicting-stream exclusion and incomplete-scope
    flags.
* Alarms:
  * unique alarm counts by device and raw alarm type;
  * raw alarm-status and deal-status distributions;
  * mutable alarm rows collapsed to the latest observation;
  * duplicate/conflict/missing-status and incomplete-scope flags.
* Device location:
  * per-device event count, distinct-coordinate count and source time span;
  * raw latest-location age relative to the requested window end;
  * optional speed/direction/accuracy/battery/GPS/network field coverage;
  * duplicate removal, latest-observation collapse, conflicting coordinate
    exclusion and explicit incomplete-scope flags;
  * no stale/fresh label, coordinate-system inference or sampling-rate claim.

Implemented durable store seam:

* `InspectionStore` repository abstraction over normalized event contracts;
* deterministic in-memory implementation for tests/local development;
* versioned PostgreSQL migration draft for the five historical tables;
* idempotent upsert semantics: latest observation wins for status/location/
  alarm, media source-ID rows upsert, realtime view first-finalization wins;
* `StoreViewEventSink` bridges the realtime session manager's finalization
  event to the store: a full open → first frame → close session now persists
  exactly one `RealtimeViewEvent` row, and a retry of the same finalization is
  idempotent per `stream_id`;
* `InspectionDataService` is a read-only page-oriented service over the store:
  device overview (current state, latest online/offline, uptime), media
  overview (counts, duration, size, latest upload, daily trend), realtime
  usage, alarm and location overviews; every value comes from durable store
  rows and deterministic aggregation, and threshold classifications
  (long-time offline/upload, stale location) remain explicitly un-produced
  until a governed threshold exists;
* read-only inspection API (`app/api/inspection.py`) exposes the service:
  `/api/v2/inspection/{devices,media,realtime,alarms,locations}` with honest
  availability states (feature flag off → 404, no store → 503, store present →
  computed metrics), JSON-safe serialization and explicit scope handling;
* first-batch inspection pages are wired:
  `GET /api/v2/dashboard/{devices,media,realtime,alarms}` render a four-tab page
  that consumes only the inspection API and shows honest
  “数据源未接入/待验证” states when the store is unavailable or empty;
  the alarms tab shows raw alarm/status/deal code distributions and per-device
  counts, with an explicit note that code maps are not yet verified;
* device timeline drill-down is wired:
  `GET /api/v2/inspection/devices/{device_id}/timeline` returns scoped status,
  media and location coverage for one device; coordinates are restricted and
  never returned, and the devices page renders the timeline inline;
* the realtime endpoint also returns the current runtime snapshot (active
  sessions/streams, Gateway/Media connections) when a realtime session manager
  is wired; runtime state is kept separate from store history and is `null`
  when no manager is provided;
* twenty-eight repository/sink/service/API/page tests cover roundtrip, scope
  filtering,
  latest-wins, media append/upsert, first-wins behavior, the
  manager-to-store write path, page-oriented overviews, the HTTP API and page
  rendering, device timeline drill-down, realtime runtime snapshots and the
  alarms endpoint/page.

Not implemented by this foundation:

* no PostgreSQL driver or connection pool is wired;
* no migration/backup/restore/rollback rehearsal has been executed;
* no production ingestion scheduler or checkpoints exist;
* the realtime view sink is only active when a store is explicitly provided;
  production release behavior is unchanged;
* the first-batch pages exist but the feature flag defaults to off; page data
  shows explicit unavailable states until a durable store (or an approved
  development store) is configured and history accumulates.

Not implemented by this foundation:

* login ownership, token lifetime/refresh or a complete production AEE data
  Adapter;
* PostgreSQL schema, migrations or repository;
* ingestion scheduling or checkpoints;
* durable DeviceLocation, Realtime-view or Alarm event
  repository/outbox/historical API;
* API routes or Dashboard pages;
* production configuration changes.

## 12. Persistence inventory

| Store | Data | Durability | Suitable for M4 history |
| --- | --- | --- | --- |
| process-local TTL cache | source responses | restart resets | no |
| `device-trend.json` | aggregate device counts, max 288 points | local file | temporary baseline only |
| Legacy device catalog file | raw current catalog fallback | local file | no event semantics |
| Legacy inspection JSON | manually saved inspection records | local file | requires separate audit/migration decision |
| Realtime in-memory sessions | runtime state | restart resets | no |
| Realtime telemetry memory | counters/durations | restart resets | no |
| PostgreSQL | configured as optional/not enabled in current V2 | none yet | intended M4 durable store |
| Redis | not enabled | none | use only if a real requirement appears |

Local development limitation:

* the current workstation has no Docker/PostgreSQL runtime, `psql`,
  `pg_dump` or `pg_restore`;
* no PostgreSQL migration, backup or restore rehearsal is currently claimed;
* SQLite or unexecuted SQL must not be presented as PostgreSQL verification.

## 13. Reliability and data-quality rules

Existing strengths:

* allow-listed Legacy adapter;
* per-source TTL and stale fallback;
* source freshness metadata;
* bounded caches and runtime retention;
* city/location validity checks in GPS-track queries;
* no AEE long-term credentials exposed to the browser.

Required M4 improvements:

* distinguish source event time, observation time and ingestion time;
* distinguish current status from status-transition history;
* formalize raw-to-normalized field mapping;
* capture source and data-quality flags per durable row;
* define late-arrival, duplicate and correction behavior;
* stop using raw field-name fallbacks at Dashboard rendering time;
* preserve `UNKNOWN` instead of converting missing values to misleading zeroes.

## 14. Priority gaps

1. No durable per-device online/offline history.
2. No durable media-file metadata index.
3. No durable Realtime viewing repository or historical API; the final event
   contract and session-manager sink boundary now exist.
4. No durable alarm history; the read-only Adapter and conservative
   `AlarmEvent` contract now exist.
5. No flight/task-to-device/media coverage model.
6. Initial AEE interface/field catalogs now exist, but integration contracts
   and remaining semantics are not yet stable.
7. No production-ready PostgreSQL migrations or repository.
8. Multi-page M4 Dashboard information architecture is documented, but the
   APIs and pages are not implemented.
9. The custom `token` request header is static-evidenced and implemented as an
   injected server-side transport boundary, but token-only live sufficiency,
   token lifetime and refresh behavior remain unverified.
