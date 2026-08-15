# M4 Data Availability Matrix

Last reviewed: `2026-08-15`

Status: `INITIAL / CODE-AUDITED / LIVE VERIFICATION PARTIAL`

Allowed values:

* `AVAILABLE`
* `DERIVABLE`
* `RESTRICTED`
* `NOT_AVAILABLE`
* `UNKNOWN`

`DERIVABLE` means a documented derivation exists or can exist after collecting
the required source events. It does not mean the value already exists.

## 1. Device inventory and status

| Expected field | Status | Current source | CHA today | History today | Required action / caveat |
| --- | --- | --- | --- | --- | --- |
| device ID | AVAILABLE | MCS8 device catalog / Legacy devices | normalized `devId` | no | define stable device dimension |
| device name | AVAILABLE | MCS8 catalog | normalized `name` | no | preserve source name changes as dimension history if needed |
| group | AVAILABLE | MCS8 catalog | `groupName` | no | catalog exact group identifiers |
| department | DERIVABLE | group ID/name mapping | maintenance filter exists | no | create governed department mapping |
| online | AVAILABLE | DeviceStatus/catalog | current boolean | no | store status observations/events |
| status code | AVAILABLE | observed AEE DevTree/DeviceStatus | normalized application contract; not persisted/API wired | no | preserve raw code; non-1 semantics remain unknown |
| alarm code | AVAILABLE | observed AEE DevTree | not normalized in CHA | no | AEE field semantics still require cataloging |
| GPS time | AVAILABLE | GPS/catalog | `gpsTime`; normalized UTC application contract | GPS query available; not persisted | source/observation/ingestion times separated; stale threshold remains unknown |
| latitude | AVAILABLE | GPS/catalog | current `lat`; validated application contract | GPS query available; not persisted | global range and zero sentinel validated; restricted data |
| longitude | AVAILABLE | GPS/catalog | current `lng`; validated application contract | GPS query available; not persisted | global range and zero sentinel validated; restricted data |
| last seen | AVAILABLE | log/GPS/catalog fallback | `lastOnlineTime` proxy | no durable history | rename/normalize; do not call it last online |
| last online at | DERIVABLE | AEE `DevOnlineList` / future CHA status events | not available | upstream query only | verify status map/order, then derive transition |
| last offline at | DERIVABLE | AEE `DevOnlineList` / future CHA status events | not available | upstream query only | verify non-1 status map/order, then derive transition |
| login/startup time | UNKNOWN | AEE/MCS8 investigation required | no | no | identify supported source or mark not available |
| network state | AVAILABLE | GPS history `netWorkType` | raw code normalized with unknown-map flag | raw historical points; not persisted | catalog semantics and freshness |
| battery | AVAILABLE | GPS/AEE observed fields | nullable numeric value with unknown-semantics flag | raw GPS points possible; not persisted | units and alarm relation require verification |
| media availability | DERIVABLE | bounded `mediaMonitor` result | runtime only | no | do not probe frequently; record only real view attempts or supported status source |
| device model | UNKNOWN | catalog may contain raw field | not normalized | no | inspect sanitized catalog sample |
| warehouse | AVAILABLE | local mapping | `warehouse` | no | local operational mapping, not upstream truth |
| city | DERIVABLE | coordinate geocoding | current `city` | derivable from GPS history | persist source coordinates and mapping version |

## 2. Device history metrics

| Metric | Status | Required source | Current state |
| --- | --- | --- | --- |
| today first online time | DERIVABLE | AEE `DevOnlineList` → `DeviceStatusEvent` | upstream transition query exists; not persisted |
| today last offline time | DERIVABLE | AEE `DevOnlineList` → `DeviceStatusEvent` | non-1 status map still partial |
| online duration | DERIVABLE | ordered, range-clipped transition events | AEE page computes it, but CHA has no durable/reproducible metric |
| daily online rate | DERIVABLE | status intervals and day boundaries | raw source exists; sampled snapshot remains insufficient |
| offline count | DERIVABLE | closed online intervals/status transitions | AEE page computes a close count but does not display it |
| longest offline duration | DERIVABLE | complete ordered status intervals | upstream retention/initial-boundary rules require verification |
| 7-day online rate | DERIVABLE | AEE transition rows persisted in CHA | not implemented |
| 30-day online rate | DERIVABLE | AEE transition rows persisted in CHA | not implemented |
| long-time offline list | DERIVABLE | last offline/last seen policy | current page has only current offline/stale candidates |

## 3. Media files

| Expected field | Status | Current source | CHA today | Required action / caveat |
| --- | --- | --- | --- | --- |
| stable media ID | AVAILABLE | AEE `RecordFileList.id` / MCS8 record row | normalized as `source_record_id`; scope flagged unverified | verify uniqueness scope before using as a sole database key |
| device ID | AVAILABLE | record row | normalized application contract | dimension FK |
| device name | AVAILABLE | row/catalog | normalized where possible | do not use name as identity |
| upload time | AVAILABLE | `uploadTime/upLoadTime/endTime` | normalized UTC contract; not persisted | verify exact source semantics |
| create/shoot time | AVAILABLE | `startTime/fileTime/beginTime` or filename | verified field aliases normalized; no filename inference in M4 contract | record derivation source if filename fallback is later used |
| duration | AVAILABLE | `duration/videoTime` | normalized as seconds for video only | preserve raw seconds |
| size | AVAILABLE | `fileSize/fileLen/size` | normalized as bytes | no display-unit rounding in storage |
| file type | AVAILABLE | AEE `fType`/`lType` | raw code normalized in application contract | `fType` 1/2/3 maps to image/audio/video and 4 to GPS/device file; exclude code 4 from media counts |
| media kind: image/audio/video | AVAILABLE | AEE `fType` | verified mapping implemented; unknown codes preserved | preserve raw code and catalog version |
| list/import type | AVAILABLE | AEE `lType` | raw code normalized; unknown values flagged | 0=normal, 1=import in current static source |
| upload/status state | AVAILABLE | AEE `source` + `upLoadStatus` | raw codes normalized with partial-map flags | full code map remains unknown |
| storage backend | UNKNOWN | no verified logical storage field | not normalized | never infer from signed URLs or private object paths |
| source | AVAILABLE | AEE `source` / Legacy query-level `platform` | raw code normalized with partial-map flag | platform/device/import semantics require verification |
| channel | UNKNOWN | raw record field | not normalized | verify source field |
| work number | AVAILABLE | AEE `workNo` | normalized application field; not persisted | operational/user-related; define access and retention |
| personnel number | RESTRICTED | AEE `peopleNo` | omitted by default; explicit opt-in only | user-sensitive; only expose for approved need |
| personnel name | RESTRICTED | AEE `peopleName` filter/possible row | omitted by default; explicit opt-in only | live row presence and permission require verification |
| remark/description | RESTRICTED | AEE `des` | omitted by default; explicit opt-in only | free text; minimize collection and display |
| codec/resolution | DERIVABLE | bounded metadata inspection | on-demand video-info only | avoid bulk FFmpeg; use existing metadata when justified |
| checksum | NOT_AVAILABLE | no current source | no | add only if source provides or ingestion computes it |

## 4. Media metrics

| Metric | Status | Current state | Required action |
| --- | --- | --- | --- |
| today upload count | AVAILABLE | `RecordFileList` / Legacy record-count query | create normalized daily metric/API with completeness flag |
| 7/30-day upload trend | AVAILABLE | on-demand daily counts | persist or query with freshness and truncation metadata |
| upload count by device | AVAILABLE | AEE live report/raw records / Legacy stats | build deterministic normalized grouping |
| latest upload time by device | DERIVABLE | ordered media rows | requires media index or bounded query |
| long-time no upload | DERIVABLE | latest upload + policy | define policy and missing-data behavior |
| total video duration | DERIVABLE | verified seconds in video rows | sum only `fType==3`; preserve raw seconds and avoid rounded page minutes |
| total queried file size | DERIVABLE | verified byte `fileLen` | scope is selected query window, not storage capacity |
| storage capacity used | UNKNOWN | CHA only has queried file-size totals; device detail has unverified storage fields | do not label bounded query size as total capacity |
| upload success rate | DERIVABLE | AEE `source/upLoadStatus` after full code map | semantics and denominator still require verification |

## 5. Realtime usage

| Expected field | Status | Current source | Persisted today | Required action |
| --- | --- | --- | --- | --- |
| username | AVAILABLE | authenticated CHA session | no | normalized event contract implemented; durable sink TODO |
| user ID | UNKNOWN | current session exposes username only | no | determine stable identity |
| device ID | AVAILABLE | realtime stream | no | normalized event dimension implemented |
| session ID | AVAILABLE | CHA session manager | no | normalized event correlation implemented |
| stream ID | AVAILABLE | CHA session manager | no | idempotency key implemented |
| opened at | AVAILABLE | stream `created_at` | no | event contract implemented |
| first frame at | AVAILABLE | runtime event | no | first observation is retained exactly once |
| closed at | AVAILABLE | close/disconnect/timeout/shutdown boundary | no | idempotent finalization implemented |
| duration seconds | DERIVABLE | opened/first-frame/closed timestamps | no | connection and post-first-frame semantics implemented |
| result | DERIVABLE | first frame, close reason and bounded error | no | normalized outcome implemented |
| error code | AVAILABLE | runtime stream error | no | safe CHA code preserved in event |
| watching count by user | DERIVABLE | `RealtimeViewEvent` | no | deterministic aggregator implemented; persistence/query scope TODO |
| watching duration by user | DERIVABLE | `RealtimeViewEvent` | no | deterministic timestamp-based aggregator implemented |
| device viewed count/duration | DERIVABLE | `RealtimeViewEvent` | no | deterministic device grouping implemented |
| first-frame success rate | DERIVABLE | persisted view results | process counter only | numerator/latency aggregation implemented; durable scope TODO |
| failure distribution | DERIVABLE | persisted error code | process counter/detail only | result/error aggregation implemented; durable scope TODO |

## 6. User activity outside Realtime

| Expected field | Status | Evidence |
| --- | --- | --- |
| login time | UNKNOWN | current CHA session response does not expose it |
| logout time | UNKNOWN | no current source |
| session history | UNKNOWN | no current source |
| last active | UNKNOWN | no current source |
| accessed devices | DERIVABLE | only after CHA records explicit view/search actions |
| AEE realtime-view history | UNKNOWN | AEE investigation required |
| AEE watching duration | UNKNOWN | AEE investigation required |

If AEE does not provide these values, CHA must not invent historical activity.
CHA can begin collecting its own explicitly scoped events prospectively.

## 7. Alarms and exceptions

| Expected field | Status | Current source | Required action |
| --- | --- | --- | --- |
| alarm ID | AVAILABLE | AEE static AlarmList `id` | normalized with source-ID-scope flag; verify live uniqueness/retention |
| device ID | AVAILABLE | AEE AlarmList/device alarm context | normalized event dimension |
| alarm type/code | AVAILABLE | AEE `alarmType` / current device `alarm` | raw event code normalized; current projection remains separate |
| level | UNKNOWN | not cataloged | verify |
| created at | AVAILABLE | AEE `alarmTime` | timezone-aware normalization implemented; event semantics still partial |
| status | AVAILABLE | AEE query `alarmStatus` / push `status` | raw code normalized; alias and lifecycle uncertainty flagged |
| handled | DERIVABLE | AEE `dealStatus` | remains null until the complete map is verified |
| handled at | AVAILABLE | AEE `dealTime` | omitted by default; restricted opt-in only |
| handler | RESTRICTED | AEE `dealUser` | omitted by default; require business need and authorization |
| deal type | AVAILABLE | AEE `dealType` | raw code normalized; labels remain partial |
| description | RESTRICTED | AEE `dealDesc` | omitted by default; free-text retention policy required |
| alarm counts by device/type | DERIVABLE | normalized `AlarmEvent` | deterministic raw-code aggregation implemented; persistence scope TODO |
| alarm status/deal status distribution | DERIVABLE | normalized raw codes | deterministic aggregation implemented; labels remain unverified |
| current offline exception | AVAILABLE | current device status | not an alarm-history substitute |
| stale location exception | DERIVABLE | current GPS age | define threshold and missing-data policy |
| long-time no upload | DERIVABLE | media latest-upload time | requires media index |

## 8. Flights and routine tasks

| Capability | Status | Current source | CHA today | Required action |
| --- | --- | --- | --- | --- |
| flight list by day | AVAILABLE | AMRO via Legacy | current-day Dashboard count/preview | normalize field catalog |
| flight detail | AVAILABLE | Legacy detail endpoint | not allow-listed in V2 | add read-only adapter only when needed |
| routine task list by day | AVAILABLE | AMRO via Legacy | current-day Dashboard count/preview | normalize field catalog |
| routine task detail/process | AVAILABLE | Legacy detail endpoints | not allow-listed in V2 | add read-only adapter only when needed |
| flight-to-device relation | UNKNOWN | no governed mapping | no | define evidence-based mapping |
| task-to-device relation | UNKNOWN | no governed mapping | no | define evidence-based mapping |
| media-to-flight candidate | DERIVABLE | media time/location + flight schedule | Legacy has heuristic helpers | audit accuracy before reuse |
| media-to-task candidate | DERIVABLE | media time/location + task schedule | Legacy has heuristic helpers | audit accuracy before reuse |
| flight video coverage rate | DERIVABLE | normalized relations | current Dashboard returns `None` | define numerator/denominator |
| task video coverage rate | DERIVABLE | normalized relations | current Dashboard returns `None` | define numerator/denominator |

## 9. Data availability decisions

1. Current online state is `AVAILABLE`. AEE online transition rows are also an
   `AVAILABLE` source; CHA historical uptime metrics remain `DERIVABLE` and
   are not yet persisted.
2. Current device GPS and raw GPS history are `AVAILABLE`; a conservative,
   restricted `DeviceLocationEvent` application contract is implemented and
   tested, but durable CHA location history, ingestion and API wiring are not.
3. Media records are queryable, but their schema is only partially normalized.
4. Realtime usage history is `DERIVABLE` from current runtime events but is not
   persisted.
5. AEE alarm query capability, endpoint contract and raw-code normalization are
   now available, but code maps, lifecycle/deletion semantics, retention and
   durable persistence remain partially unverified. AEE user activity remains
   `UNKNOWN`.
6. Missing values remain unknown/null. They must not be converted to zero for
   visual convenience.
