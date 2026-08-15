# AEE Capability Matrix

Last reviewed: `2026-08-15`

Status: `INITIAL / PARTIAL LIVE EVIDENCE`

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
| authentication | `/api/v1/auth/Token` access token; AEE data helper sends it in custom `token` header | LIVE page requests + STATIC transport evidence | Class A | M3 server-side login exists; M4 read-only HTTP transport foundation added, not wired | verify token-only server call, lifetime and refresh without exposing credentials |
| permissions | `VIDEOMONITOR` controls device drag/play access | LIVE VERIFIED | Class A | Canary isolation is CHA-owned | catalog required permissions per read-only data capability |
| device tree | device ID/name, online/status, alarm, GPS, network/storage projections | LIVE VERIFIED through `/api/v1/ext/DevTree`, fields partial | Class A | CHA devices expose a subset | build normalized read-only adapter after code-map and refresh semantics are captured |
| device groups | group/tree organization | LIVE VERIFIED through `/api/v1/ext/DevTree`, semantics partial | Class A | CHA exposes maintenance group name/ID | catalog hierarchy and stable identifiers |
| current online state | `online`, `status` | LIVE VERIFIED | Class A | current boolean available | do not treat as historical uptime |
| device online history | `/api/v1/DevOnlineList` transition rows and page-computed duration | LIVE+STATIC PARTIAL | Class A | no durable event history | ingest raw rows; verify ordering/status map/retention and compute range-clipped metrics in CHA |
| device alarm state | raw `alarm` code observed | LIVE VERIFIED, semantics partial | Class A | not normalized in V2 | catalog code, level and lifecycle |
| GPS freshness | `gpsTime` observed in device tree | LIVE VERIFIED | Class A | current GPS time exposed | use as freshness signal, not proof of online transition |
| current location | `gpsLng/gpsLat` and Gateway `getGps` path | LIVE/STATIC PARTIAL + CHA LEGACY VERIFIED | Class A | current location available | verify coordinate system and refresh behavior |
| GPS history | location history capability | CHA LEGACY VERIFIED through MCS8 `GetGpsModelList` | Class A | Legacy endpoint exists | determine whether AEE exposes the same supported interface |
| media/file query | `/api/v1/RecordFileList` with filters/pagination | LIVE VERIFIED, expanded filters STATIC VERIFIED | Class A | Legacy and V2 trend use a different MCS8 interface | create a narrow normalized Adapter; avoid browser/runtime coupling |
| media metadata | ID, device, title, kind, source/import type, size, duration, times, upload status and work/person references | LIVE+STATIC PARTIAL | Class A | partially normalized | confirm stable ID scope and status/storage/channel semantics |
| file statistics | file count, video duration and file size by device/group | LIVE VERIFIED; browser aggregation STATIC VERIFIED | Class A source + Class C CHA aggregation | only partial Legacy aggregates exist | compute server-side from normalized rows with completeness metadata |
| alarms list/history | `/api/v1/AlarmList`, query filters, non-empty rows and handling projection | LIVE+STATIC PARTIAL | Class A | no durable CHA model | complete code maps, lifecycle, retention and privacy rules before persistence |
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
  verified. The page uses `status/time` transition rows, but its current
  client-side algorithm extends an open interval to browser current time.
  CHA must not copy that boundary behavior.
* `WXB358` proved that management online state can coexist with stale GPS and
  Media service rejection. These dimensions must remain separate.
* Media availability must not be inferred from device-tree online state.
* Server file activity and realtime media availability are separate:
  a device may have recent uploaded file records while a realtime monitor
  attempt is unavailable.
* AEE file reports are not separate aggregate APIs; the current page derives
  counts, duration and size from up to 10,000 `RecordFileList` rows. CHA must
  detect truncation and must not silently present partial totals.
* A Dashboard must not generate last-online, duration or alarm-history values
  until a source event or supported history interface is verified.
* AEE page-private state, private routing and page-global media glue remain
  Class D.
* Current static code links `/api/v1/auth/Token` `access_token` directly to the
  custom `token` header used by `/api/v1/*` data requests. This disproves the
  earlier unverified Bearer-header assumption.
* The current browser may also send same-origin session state. Token-only
  sufficiency, access-token lifetime and refresh behavior still require a
  sanitized server-side integration check.

## AEE verification required

For every item below, use an authorized user, the visible product page and
sanitized Network/WebSocket observation:

* exact DevTree refresh cadence and Gateway push/update contract;
* exact group/node code maps and hierarchy lifecycle;
* last-online/offline or startup fields, if any;
* `/api/v1/DevOnlineList` raw sanitized response, non-1 status map, ordering,
  duplicate behavior, pagination and retention;
* media stable-ID uniqueness, units, status/storage/channel code maps;
* alarm lifecycle/code maps, retention, deletion semantics and permissions;
* user activity/session endpoint and privacy restrictions;
* pagination/rate limits and supported server-side integration boundary.
* token-only server-side access to each required read-only path, token
  lifetime, 401 behavior and refresh/login frequency.
