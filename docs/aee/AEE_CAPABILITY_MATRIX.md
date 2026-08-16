# AEE Capability Matrix

Last reviewed: `2026-08-16`

Status: `LIVE VERIFIED (2026-08-16) / PARTIAL`

This matrix follows:

`docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`

AEE is a reference implementation and upstream capability source. It is not a
CHA UI template or production runtime dependency.

## Evidence levels

* `LIVE VERIFIED`: observed in an authorized AEE session.
* `STATIC VERIFIED`: observed in current AEE static assets or current MCS8 SDK.
* `CHA LEGACY VERIFIED`: current CHA Legacy calls an MCS8 interface, but AEE
  page usage has not yet been recaptured.
* `AEE VERIFICATION REQUIRED`: no lawful current evidence is recorded.

## Capability matrix

| Domain | AEE capability | Evidence | Classification | CHA status | M4 recommendation |
| --- | --- | --- | --- | --- | --- |
| authentication | `/api/v1/auth/Token` access token; AEE data helper sends it in custom `token` header | TOKEN-ONLY LIVE VERIFIED (2026-08-16): token header + `credentials:'omit'` returns `error=200` on DevOnlineList/RecordFileList; no header returns `error=333` | Class A | M3 server-side login exists; M4 read-only HTTP transport foundation added, not wired | verify token lifetime/refresh and server-side token provider without exposing credentials |
| permissions | `VIDEOMONITOR` controls device drag/play access | LIVE VERIFIED | Class A | Canary isolation is CHA-owned | catalog required permissions per read-only data capability |
| device tree | device ID/name, online/status, alarm, GPS, network/storage projections | LIVE VERIFIED through `/api/v1/ext/DevTree`, fields partial | Class A | CHA devices expose a subset | build normalized read-only adapter after code-map and refresh semantics are captured |
| device groups | group/tree organization | LIVE VERIFIED through `/api/v1/ext/DevTree`, semantics partial | Class A | CHA exposes maintenance group name/ID | catalog hierarchy and stable identifiers |
| current online state | `online`, `status` | LIVE VERIFIED | Class A | current boolean available | do not treat as historical uptime |
| device online history | `/api/v1/DevOnlineList` transition rows and page-computed duration | LIVE VERIFIED (1696 rows, 3-day window, error=200 envelope, transition rows with status 0/1) | Class A | no durable event history | ingest raw rows; status 0=offline and 1=online live-confirmed; compute range-clipped metrics in CHA |
| device alarm state | raw `alarm` code observed | LIVE VERIFIED, semantics partial | Class A | not normalized in V2 | catalog code, level and lifecycle |
| GPS freshness | `gpsTime` observed in device tree | LIVE VERIFIED | Class A | current GPS time exposed | use as freshness signal, not proof of online transition |
| current location | `gpsLng/gpsLat` and Gateway `getGps` path | LIVE/STATIC PARTIAL + CHA LEGACY VERIFIED | Class A | current location available | verify coordinate system and refresh behavior |
| GPS history | location history capability | CHA LEGACY VERIFIED through MCS8 `GetGpsModelList` | Class A | Legacy endpoint exists | determine whether AEE exposes the same supported interface |
| media/file query | `/api/v1/RecordFileList` with filters/pagination | LIVE VERIFIED (711 rows, 3-day window, page=1/pagesize=1000, full row schema captured) | Class A | Legacy and V2 trend use a different MCS8 interface | create a narrow normalized Adapter; avoid browser/runtime coupling |
| media metadata | ID, device, title, kind, source/import type, size, duration, times, upload status and work/person references | LIVE VERIFIED (fType 1=image/2=audio/3=video, fileLen=bytes, duration=seconds, global-unique id, non-null times) | Class A | partially normalized | stable ID scope verified as globally unique within window; status/storage/channel semantics remain partial |
| file statistics | file count, video duration and file size by device/group | LIVE VERIFIED; browser aggregation STATIC VERIFIED | Class A source + Class C CHA aggregation | only partial Legacy aggregates exist | compute server-side from normalized rows with completeness metadata |
| alarms list/history | `/api/v1/AlarmList`, query filters, non-empty rows and handling projection | LIVE VERIFIED (41 rows, alarmType 205/206 observed, `status` field carries alarm status, dealStatus=0) | Class A | read-only Adapter and raw-code `AlarmEvent` normalization implemented; not persisted | complete code maps, lifecycle, retention and privacy rules before persistence |
| alarm push | `AlarmUpload` updates current device alarm/GPS state | STATIC VERIFIED | Class A event source candidate | no durable CHA model | verify live lifecycle/delivery guarantees before ingestion |
| alarm handling | `/api/v1/AlarmUpdateDeal` | STATIC VERIFIED | restricted write capability | not implemented | outside current read-only M4 scope |
| task list | `/api/v1/TaskList` | STATIC VERIFIED | potential Class A | CHA already has AMRO routine tasks | compare source semantics before duplication |
| record job/track relation | `/api/v1/JobLineByRecordId` | STATIC VERIFIED | potential Class A | Legacy has heuristic relations | investigate only if required by drill-down |
| user login/session history | login/logout/last-active | AEE VERIFICATION REQUIRED | Class A / Restricted | unavailable in CHA | record `NOT_AVAILABLE` if AEE does not expose legally |
| user viewing history | watched devices and durations | AEE VERIFICATION REQUIRED | Class A / Restricted | no durable CHA history | CHA should collect prospective `RealtimeViewEvent` |
| realtime media open | `mediaMonitor streamType=2` | LIVE VERIFIED | Class B | M3 implemented | supporting drill-down only |
| realtime media close | `closeMediaMonitor` | LIVE VERIFIED | Class B | M3 explicit cleanup implemented | retain current lifecycle |
| media availability | open success or `devices is offline` | LIVE VERIFIED as operation result | Class A/B boundary | runtime errors normalized | do not poll solely for a dashboard |
| video consumer | H.264 `newConsumer`, RTP and MediaStream | LIVE VERIFIED | Class B | M3 implemented | not an M4 data priority |
| H.265 page fallback | `/mediaStream` + WASM/Canvas page glue | STATIC VERIFIED | Class D | not implemented | no workaround or runtime coupling |
| Dashboard/UI layout | AEE page presentation | observed | Class D | CHA has own UI | do not clone |

## P0 investigation order

1. Device inventory, group hierarchy, online/status/alarm/GPS freshness.
2. Media/file query scope and complete row schema.
3. Alarm list/history and handling fields.
4. User activity, sessions and view history, subject to permission and privacy.
5. Flight/task relations only if AEE actually provides them.

## Current decisions

* AEE device-tree `online/status` is a current management view, not sufficient
  uptime history.
* `/api/v1/DevOnlineList` and a non-empty online-duration page are live
  verified. The page uses `status/time` transition rows. Live verification on
  `2026-08-16` (authorized account, Statistics/Online page, 3-day window,
  `error=200` envelope) returned `recordsTotal=1696`, `pageCount=1`,
  `length=10000` with per-row fields `id, enterId, enterName, groupId,
  groupName, devId, devType, devName, status, time, lat, lng, addr, remarks,
  storeType, network, battery, totalSize, useSize, version, hardware`. `id`
  was unique across all 1696 rows, `time` was non-null business-local time,
  and both `status=1` (849) and `status=0` (847) were observed. The same
  device can produce both codes in the same window (transition rows), e.g.
  `WXB312` at `status=0/1` and `WXB301` with `1 → 0 → 1` transitions. Its
  current client-side algorithm extends an open interval to browser current
  time. CHA must not copy that boundary behavior.
* The page-computed "online duration" (`Hour`/`Min` display) did not exactly
  match a naive range-clipped interval sum for one device
  (`WXB310`: ~32h computed vs 12Hour displayed). The page algorithm for that
  column is therefore recorded as a display projection with unverified
  day-boundary semantics; CHA must compute its own deterministic,
  range-clipped intervals from raw transition rows.
* `WXB358` proved that management online state can coexist with stale GPS and
  Media service rejection. These dimensions must remain separate.
* Media availability must not be inferred from device-tree online state.
* Server file activity and realtime media availability are separate:
  a device may have recent uploaded file records while a realtime monitor
  attempt is unavailable.
* AEE file reports are not separate aggregate APIs; the current page derives
  counts, duration and size from up to 10,000 `RecordFileList` rows. Live
  verification on `2026-08-16` (Server Files page, 3-day window,
  `error=200`) returned `recordsTotal=711`, `pageCount=1`, `length=1000`
  with a 55-field row schema. `fType` was live-confirmed as
  `1=image (16)`, `2=audio (6)`, `3=video (689)`; `fileLen` is bytes and
  `duration` is seconds; `id` was globally unique across 711 rows; capture,
  end, file and upload times were all non-null. Within this window no
  cross-page truncation was observed (711 < 1000 page size), but CHA must
  still detect truncation and must not silently present partial totals.
* `AlarmList` was live-verified on `2026-08-16` (Alarm page, 3-day window,
  `error=200`, `recordsTotal=41`). The row schema is `id, enterId, groupId,
  devId, alarmTime, alarmType, status, alarmDesc, dealType, dealStatus,
  dealUser, dealTime, dealDesc, gpsModel, code, ex, keywords, peopleNo,
  workNo`. There is **no** `alarmStatus` field in `AlarmList` rows; the alarm
  status is carried by `status` (observed `null` in the sanitized sample,
  present in the push/query contract). `alarmType=205 (40)` and
  `alarmType=206 (1)` were observed. The existing `AlarmEvent` normalizer
  already accepts `status` as an alias for `alarmStatus`.
* A Dashboard must not generate last-online, duration or alarm-history values
  until a source event or supported history interface is verified.
* AEE page-private state, private routing and page-global media glue remain
  Class D.
* Current static code links `/api/v1/auth/Token` `access_token` directly to the
  custom `token` header used by `/api/v1/*` data requests. This disproves the
  earlier unverified Bearer-header assumption.
* The current browser may also send same-origin session state. A direct
  same-origin `fetch` without the page-injected `token` header returned
  `error=333` (HTTP 200, no data) — confirming **TOKEN_REQUIRED**: the data
  API depends on the custom `token` header and does not accept the Cookie
  alone. **TOKEN-ONLY LIVE VERIFIED (2026-08-16)**: a page-context `fetch`
  with only the `token` header and `credentials:'omit'` (no Cookie sent)
  returned `error=200` on `/api/v1/DevOnlineList` (716 rows) and
  `/api/v1/RecordFileList` (347 rows), proving the server-style token-only
  request works without a browser Cookie. Access-token lifetime, refresh and
  the server-side token provider still require a sanitized integration check.

## AEE verification required

For every item below, use an authorized user, the visible product page and
sanitized Network/WebSocket observation:

* exact DevTree refresh cadence and Gateway push/update contract;
* exact group/node code maps and hierarchy lifecycle;
* last-online/offline or startup fields, if any;
* `/api/v1/DevOnlineList` full non-0/non-1 status map (only 0/1 observed in
  the live window), long-range ordering, retention boundary and
  query-boundary behavior;
* media `source`/`upLoadStatus`/`lType` full code maps, storage/channel
  semantics and retention;
* alarm lifecycle/code maps (only 205/206 observed live), deletion
  semantics, retention and permissions;
* user activity/session endpoint and privacy restrictions;
* pagination/rate limits and supported server-side integration boundary.
* token-only server-side access to each required read-only path is
  **LIVE VERIFIED** (token header without Cookie returns `error=200`); token
  lifetime, 401 behavior, refresh/login frequency and the server-side token
  provider remain to be validated.
