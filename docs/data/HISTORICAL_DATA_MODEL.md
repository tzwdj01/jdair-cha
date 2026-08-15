# M4 Historical Data Model

Last reviewed: `2026-08-15`

Status: `DESIGN / NORMALIZATION AND AGGREGATION FOUNDATION IMPLEMENTED`

## 1. Principles

1. Persist only data with a verified source and business value.
2. Do not persist WebRTC transport, consumer, socket or other runtime-only
   objects.
3. Separate:
   * source event time: `occurred_at`;
   * CHA observation time: `observed_at`;
   * database ingestion time: `ingested_at`.
4. Preserve source and quality metadata.
5. Current-state polling does not provide an exact transition timestamp.
6. Derived metrics are reproducible outputs, not source truth.
7. Null/unknown is different from zero/false.

## 1.1 Current implementation boundary

Implemented and covered by unit tests:

* deterministic, report-window-clipped aggregation of AEE-style device status
  transitions;
* deterministic per-device aggregation of `RecordFileList` rows using raw
  seconds and bytes;
* explicit quality flags for missing start state, provisional status mapping,
  conflicting or duplicate events, invalid values and partial/truncated
  result sets;
* a narrow, server-side, read-only AEE HTTP transport using the static-evidenced
  custom `token` header, exact endpoint allowlisting, bounded errors and one
  401-driven token invalidation/retry;
* endpoint-specific DevTree, DevOnlineList and RecordFileList contracts with
  explicit source timezone, range/pagination validation and page
  completeness metadata;
* deterministic multi-page collection with explicit truncation, unknown-total,
  changing-total, empty-page, duplicate-ID and invalid-row quality flags;
* normalized `DeviceStatusEvent` and `MediaFile` application contracts with
  explicit `occurred_at`/source-time, `observed_at` and `ingested_at`
  separation;
* a normalized, immutable `RealtimeViewEvent` finalization contract and an
  opt-in session-manager sink boundary for forward-only CHA viewing evidence.

Normalization safety rules already enforced:

* non-1 DevOnlineList statuses remain `online=null` until the full code map is
  verified;
* upstream media ID scope remains flagged as unverified;
* raw source/upload/deletion codes are preserved without inventing lifecycle
  labels;
* file sizes remain bytes and video durations remain seconds;
* restricted personnel and free-text fields are omitted by default;
* lifecycle timestamps must be timezone-aware and ingestion cannot precede
  observation;
* realtime first-frame time is recorded once, durations are derived from
  timezone-aware CHA timestamps, and finalization is idempotent per
  `stream_id`;
* the event never contains the login-session hash, Cookie, AEE credential,
  WebSocket URL, SDP, ICE or media payload.

The implementation is in:

* `mature-modernization/v2/app/data/metrics.py`;
* `mature-modernization/v2/app/data/aee_http.py`;
* `mature-modernization/v2/app/data/aee_adapter.py`;
* `mature-modernization/v2/app/data/pagination.py`;
* `mature-modernization/v2/app/data/normalization.py`;
* `mature-modernization/v2/app/data/realtime_views.py`;
* `mature-modernization/v2/tests/test_data_metrics.py`.
* `mature-modernization/v2/tests/test_aee_data_http.py`.
* `mature-modernization/v2/tests/test_aee_data_adapter.py`.
* `mature-modernization/v2/tests/test_aee_data_pagination.py`.
* `mature-modernization/v2/tests/test_data_normalization.py`.
* `mature-modernization/v2/tests/test_realtime_view_events.py`.

Not yet implemented:

* AEE login/token owner, token lifetime/refresh policy and a complete
  authenticated data Adapter;
* PostgreSQL tables, repository or migration tooling;
* ingestion checkpoints and retry behavior;
* a durable `RealtimeViewEvent` sink/repository and historical query API;
* M4 data APIs and Dashboard pages.

This boundary is intentional. Static evidence confirms the custom `token`
header, but token-only live sufficiency, lifetime and refresh are still
unverified. Those items and an isolated PostgreSQL migration/backup/restore
environment must be verified before ingestion is enabled.

## 2. Common metadata

Durable event/index tables should use:

| Column | Purpose |
| --- | --- |
| `id` | CHA-generated UUID/identity |
| `source_system` | `cha_legacy`, `mcs8`, `aee`, `cha_realtime`, `amro` |
| `source_record_id` | upstream stable identity when available |
| `occurred_at` | upstream event time, nullable when unavailable |
| `observed_at` | when CHA observed the value |
| `ingested_at` | database insertion time |
| `quality_status` | `valid`, `partial`, `stale`, `invalid`, `unknown` |
| `quality_flags` | bounded JSON array/object of documented flags |
| `raw_fingerprint` | optional hash for idempotency, not raw sensitive payload |

Raw authenticated responses, Cookies, tokens, signed URLs and Authorization
values must not be stored.

## 3. Device dimension

Proposed table: `devices`

| Column | Type | Notes |
| --- | --- | --- |
| `device_id` | text PK | stable MCS8/AEE identity |
| `device_name` | text | latest normalized name |
| `group_id` | text nullable | upstream group |
| `group_name` | text nullable | upstream group name |
| `department_code` | text nullable | governed CHA mapping |
| `department_name` | text nullable | governed CHA mapping |
| `warehouse` | text nullable | local operational mapping |
| `device_model` | text nullable | only after source verification |
| `first_seen_at` | timestamptz | first CHA observation |
| `last_seen_at` | timestamptz | latest CHA observation |
| `active` | boolean | inventory membership, not online status |
| `source_updated_at` | timestamptz nullable | upstream catalog time if provided |
| `updated_at` | timestamptz | CHA update time |

Name/group changes may later require a type-2 history table. Do not add that
complexity until a real reporting requirement exists.

## 4. DeviceStatusEvent

Proposed table: `device_status_events`

Initial verified upstream candidate:

`AEE /api/v1/DevOnlineList`

The current AEE page uses `devId`, `groupId`, `status` and `time` transition
rows. `status==1` is treated as online; the complete status map, ordering,
duplicates, retention and boundary behavior still require ingestion tests.

Minimum fields:

| Column | Notes |
| --- | --- |
| `device_id` | FK to device |
| `online` | nullable boolean if source only provides status code |
| `status_code` | raw normalized string/integer representation |
| `alarm_code` | nullable raw current alarm code |
| `gps_time` | nullable latest source GPS timestamp |
| `occurred_at` | exact source transition time only when supplied |
| `observed_at` | polling/push observation time |
| `source_system` | source |
| `transition_kind` | `initial`, `online`, `offline`, `status_changed`, `observation` |
| `transition_precision` | `exact`, `bounded`, `observation_only` |
| `quality_status/flags` | stale GPS, conflicting source, missing timestamp, etc. |

### Observation and transition rules

If CHA polls:

```text
10:00 observed online
10:05 observed offline
```

the exact offline time is unknown. Store:

* `observed_at=10:05`;
* `transition_kind=offline`;
* `transition_precision=bounded`;
* quality flag with previous observation time.

Do not report “offline at 10:05 exactly” unless the source provides an exact
event timestamp.

For AEE transition rows, preserve the source `time` as `occurred_at`, but do
not trust response order. Sort by device/time, define duplicate handling, seed
the status at the start boundary, and clip open intervals to the requested
report end. Do not extend historical intervals to ingestion/browser current
time.

### Derived metrics

After sufficient events exist:

* `last_online_at`;
* `last_offline_at`;
* `online_duration`;
* `daily_online_rate`;
* `offline_count`;
* `longest_offline_duration`;
* 7-day and 30-day online rate.

Every metric must expose data coverage and transition precision.

## 5. DeviceLocationEvent

Proposed table: `device_location_events`

| Column | Notes |
| --- | --- |
| `device_id` | FK |
| `latitude`, `longitude` | validated coordinates |
| `gps_occurred_at` | source GPS time |
| `observed_at` | CHA retrieval time |
| `speed` | nullable, unit documented |
| `direction` | nullable |
| `accuracy` | nullable |
| `battery` | nullable raw/normalized value |
| `gps_type` | nullable source code |
| `network_type` | nullable source code |
| `city_code/name` | derived using a versioned mapping |
| `location_source` | live GPS, historical GPS, record coordinate, etc. |
| `quality_status/flags` | invalid, stale, impossible jump, missing accuracy |

Deduplication candidate:

`device_id + gps_occurred_at + rounded coordinate + source_system`

Retention and sampling must be decided after measuring source volume.

## 6. MediaFile

Proposed table: `media_files`

This is a metadata index, not media storage.

| Column | Notes |
| --- | --- |
| `media_id` | CHA stable ID |
| `source_record_id` | verified upstream ID/key |
| `device_id` | FK |
| `device_name_at_capture` | source display value |
| `media_kind` | `video`, `audio`, `image`, `unknown` |
| `file_type` | normalized source type |
| `title` | sanitized display title |
| `created_at_source` | capture/create time |
| `uploaded_at_source` | upload time |
| `duration_seconds` | nullable |
| `size_bytes` | nullable |
| `status` | normalized only after source catalog |
| `storage_source` | logical backend, no credential or signed URL |
| `channel` | nullable |
| `source_system` | AEE/MCS8/Legacy |
| `first_indexed_at`, `last_seen_at` | index lifecycle |
| `quality_status/flags` | missing time, derived filename time, duplicate candidate |

The AEE Server Files source exposes `id`, but its uniqueness scope and
retention behavior still require live verification. Until that is confirmed,
use a composite uniqueness rule that also includes `source_system`, and do not
claim cross-source identity equivalence.

## 7. RealtimeViewEvent

Proposed table: `realtime_view_events`

Application contract status:

`IMPLEMENTED / NOT YET PERSISTED`

The Realtime manager now accepts an opt-in sink and emits one immutable event
after a stream reaches a terminal viewing boundary. With no sink configured,
existing Realtime behavior is unchanged. A sink failure cannot block media
release and remains retryable on an idempotent repeated close. The future
PostgreSQL sink must be a fast enqueue/upsert boundary rather than a slow query
inside the media lifecycle.

Minimum fields required by M4:

| Column | Source |
| --- | --- |
| `view_event_id` | CHA |
| `username` | authenticated CHA user |
| `user_id` | nullable until stable identity exists |
| `device_id` | realtime stream |
| `session_id` | CHA session |
| `stream_id` | CHA stream |
| `opened_at` | stream create/open request |
| `first_frame_at` | browser first-frame event |
| `closed_at` | final close/failure |
| `connection_duration_seconds` | `closed_at - opened_at` |
| `view_duration_seconds` | `closed_at - first_frame_at`, nullable without first frame |
| `result` | `played`, `failed`, `cancelled`, `timeout`, `abnormal_disconnect` |
| `error_code` | normalized CHA code |
| `width`, `height` | last observed resolution |
| `track_state` | final bounded state |
| `close_reason` | user close, session close, timeout, disconnect, shutdown |
| `source_system` | `cha_realtime` |

### Lifecycle rules

* track the accepted stream as pending in the existing process-local runtime;
* update first-frame time exactly once while allowing bounded status/resolution
  updates;
* emit a durable candidate exactly once on explicit close, terminal
  disconnect, timeout cleanup or shutdown;
* use an idempotency constraint on `stream_id`;
* do not store AEE tokens, WebSocket URLs, SDP, ICE or media payload;
* browser/control/proxy disconnect and process shutdown finalize with explicit
  reason;
* a failed first frame has connection duration but no view duration.

### Derived metrics

* views and viewing time by user;
* views and viewing time by device;
* first-frame success rate;
* first-frame latency distribution;
* failure-reason distribution;
* current active sessions remain a runtime gauge, not a database query.

## 8. AlarmEvent

Proposed table: `alarm_events`

The read-only AEE interface `/api/v1/AlarmList`, its core fields and non-empty
paginated rows are verified. Persistence remains data-gated until code maps,
lifecycle/deletion semantics, retention and privacy rules are verified.

Candidate fields:

* source alarm ID;
* device ID;
* type/code;
* level;
* occurred/observed time;
* status;
* handled flag/time;
* handler identity, only if authorized and required;
* deal type/status;
* description/code-map version;
* source and quality metadata.

Do not infer alarm history from a current device `alarm` code.

## 9. Flight/task dimensions and relationships

Candidate source tables:

* `flight_snapshots` or a latest flight dimension;
* `routine_task_snapshots` or a latest task dimension.

Candidate relation table:

`media_business_references`

| Column | Notes |
| --- | --- |
| `media_id` | media metadata index |
| `reference_type` | flight / routine task |
| `reference_id` | source business ID |
| `relation_kind` | explicit / candidate |
| `score` | nullable documented score |
| `reason_codes` | time/location/device evidence |
| `matched_at` | derivation time |
| `matcher_version` | reproducibility |
| `confirmed` | explicit human/system confirmation |

Existing Legacy matching helpers are heuristic. They must be audited against
real examples before migration into an M4 service.

## 10. Aggregates

Daily/hourly aggregates should be derived from durable source rows:

* `device_daily_uptime`;
* `media_daily_stats`;
* `realtime_daily_stats`;
* `alarm_daily_stats`;
* `coverage_daily_stats`.

First implementation should prefer SQL views or deterministic query services.
Materialized aggregates are justified only after measuring query cost.

## 11. PostgreSQL migration sequence

No production migration is authorized by this design.

Current local constraint:

* no Docker/PostgreSQL runtime, `psql`, `pg_dump` or `pg_restore` is available
  on the current development workstation;
* therefore no forward/downgrade/backup/restore rehearsal is currently
  complete;
* do not substitute SQLite or an unexecuted SQL review for PostgreSQL
  verification.

Required sequence:

1. add database configuration with feature flag/default disabled;
2. add migration tooling and an empty-database test;
3. create local/isolated PostgreSQL;
4. migrate forward;
5. load synthetic non-sensitive fixtures;
6. verify constraints/idempotency;
7. test downgrade or documented compensating rollback;
8. create backup and restore rehearsal;
9. verify application runs with DB disabled and enabled;
10. request explicit approval before production DB change.

Redis is not required by the current model.
