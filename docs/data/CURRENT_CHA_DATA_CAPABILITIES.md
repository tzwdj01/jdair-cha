# Current CHA Data Capabilities

Last reviewed: `2026-08-15`

Status: `M4 BASELINE / CODE-AUDITED / AGGREGATION FOUNDATION IMPLEMENTED`

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
        +-- no durable RealtimeViewEvent history
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
* no normalized timezone, accuracy-quality or late-arrival policy exists.

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
* no durable `RealtimeViewEvent` exists.

The current runtime fields are sufficient to derive a future
`RealtimeViewEvent`, but persistence and event finalization must be implemented
explicitly.

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

* flight-to-video coverage is not implemented;
* routine-task-to-video coverage is not implemented;
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
* the current complete V2 backend suite passes `94 tests`.

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
  * `/api/v1/RecordFileList`.
* ranged queries require explicit source timezone, required enterprise scope
  and bounded pagination;
* page envelopes expose `records_total`, `has_more`, invalid-row count and
  quality flags.

Not implemented by this foundation:

* login ownership, token lifetime/refresh or a complete production AEE data
  Adapter;
* PostgreSQL schema, migrations or repository;
* ingestion scheduling or checkpoints;
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
3. No durable Realtime viewing history.
4. No normalized alarm history.
5. No flight/task-to-device/media coverage model.
6. Initial AEE interface/field catalogs now exist, but integration contracts
   and remaining semantics are not yet stable.
7. No production-ready PostgreSQL migrations or repository.
8. Multi-page M4 Dashboard information architecture is documented, but the
   APIs and pages are not implemented.
9. The custom `token` request header is static-evidenced and implemented as an
   injected server-side transport boundary, but token-only live sufficiency,
   token lifetime and refresh behavior remain unverified.
