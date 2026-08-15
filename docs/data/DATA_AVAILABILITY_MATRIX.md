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
| status code | AVAILABLE | observed AEE DevTree/DeviceStatus | not normalized in V2 | no | catalog values and semantics |
| alarm code | AVAILABLE | observed AEE DevTree | not normalized in CHA | no | AEE field semantics still require cataloging |
| GPS time | AVAILABLE | GPS/catalog | `gpsTime` | GPS query available | normalize timezone and event-time semantics |
| latitude | AVAILABLE | GPS/catalog | current `lat` | GPS query available | store only valid coordinates |
| longitude | AVAILABLE | GPS/catalog | current `lng` | GPS query available | store only valid coordinates |
| last seen | AVAILABLE | log/GPS/catalog fallback | `lastOnlineTime` proxy | no durable history | rename/normalize; do not call it last online |
| last online at | DERIVABLE | AEE `DevOnlineList` / future CHA status events | not available | upstream query only | verify status map/order, then derive transition |
| last offline at | DERIVABLE | AEE `DevOnlineList` / future CHA status events | not available | upstream query only | verify non-1 status map/order, then derive transition |
| login/startup time | UNKNOWN | AEE/MCS8 investigation required | no | no | identify supported source or mark not available |
| network state | AVAILABLE | GPS history `netWorkType` | not exposed by V2 | raw historical points | catalog semantics and freshness |
| battery | AVAILABLE | GPS/AEE observed fields | not exposed by V2 | raw GPS points possible | units and alarm relation require verification |
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
| stable media ID | AVAILABLE | AEE `RecordFileList.id` / MCS8 record row | raw row only | verify uniqueness scope before using as a sole database key |
| device ID | AVAILABLE | record row | normalized `devId` | dimension FK |
| device name | AVAILABLE | row/catalog | normalized where possible | do not use name as identity |
| upload time | AVAILABLE | `uploadTime/upLoadTime/endTime` | raw/UI fallback | verify semantics |
| create/shoot time | AVAILABLE | `startTime/fileTime/beginTime` or filename | partial helper | record derivation source |
| duration | AVAILABLE | `duration/videoTime` | UI only | normalize unit |
| size | AVAILABLE | `fileSize/fileLen/size` | aggregate/UI only | normalize bytes |
| file type | AVAILABLE | AEE `fType`/`lType` | not normalized | `fType` 1/2/3 maps to image/audio/video and 4 to GPS/device file; exclude code 4 from media counts |
| media kind: image/audio/video | AVAILABLE | AEE `fType` | not normalized | preserve raw code and catalog version |
| list/import type | AVAILABLE | AEE `lType` | not normalized | 0=normal, 1=import in current static source |
| upload/status state | AVAILABLE | AEE `source` + `upLoadStatus` | not normalized | partial semantics only; full code map remains unknown |
| storage backend | UNKNOWN | no verified logical storage field | not normalized | never infer from signed URLs or private object paths |
| source | AVAILABLE | AEE `source` / Legacy query-level `platform` | query-level or raw only | raw code and platform/device/import semantics require normalization |
| channel | UNKNOWN | raw record field | not normalized | verify source field |
| work number | AVAILABLE | AEE `workNo` | not normalized | operational/user-related; define access and retention |
| personnel number | RESTRICTED | AEE `peopleNo` | not normalized | user-sensitive; only expose for approved need |
| personnel name | RESTRICTED | AEE `peopleName` filter/possible row | not normalized | live row presence and permission require verification |
| remark/description | RESTRICTED | AEE `des` | not normalized | free text; minimize collection and display |
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
| username | AVAILABLE | authenticated CHA session | no | `RealtimeViewEvent.username` |
| user ID | UNKNOWN | current session exposes username only | no | determine stable identity |
| device ID | AVAILABLE | realtime stream | no | event dimension |
| session ID | AVAILABLE | CHA session manager | no | event correlation |
| stream ID | AVAILABLE | CHA session manager | no | event correlation |
| opened at | AVAILABLE | stream `created_at` | no | persist event start |
| first frame at | AVAILABLE | runtime event | no | persist when observed |
| closed at | AVAILABLE | stream `closed_at` | no | finalize idempotently |
| duration seconds | DERIVABLE | opened/first-frame/closed timestamps | no | define viewing-duration semantics |
| result | DERIVABLE | final stream/session status | no | normalized outcome enum |
| error code | AVAILABLE | runtime stream error | no | normalized safe code |
| watching count by user | DERIVABLE | `RealtimeViewEvent` | no | aggregate after persistence |
| watching duration by user | DERIVABLE | `RealtimeViewEvent` | no | aggregate after persistence |
| device viewed count/duration | DERIVABLE | `RealtimeViewEvent` | no | aggregate after persistence |
| first-frame success rate | DERIVABLE | persisted view results | process counter only | durable numerator/denominator |
| failure distribution | DERIVABLE | persisted error code | process counter/detail only | durable aggregation |

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
| alarm ID | AVAILABLE | AEE static AlarmList `id` | verify live uniqueness/retention |
| device ID | AVAILABLE | AEE AlarmList/device alarm context | normalize |
| alarm type/code | AVAILABLE | AEE `alarmType` / current device `alarm` | map semantics and distinguish event/current projection |
| level | UNKNOWN | not cataloged | verify |
| created at | AVAILABLE | AEE `alarmTime` | verify timezone and event semantics |
| status | AVAILABLE | AEE query `alarmStatus` / push `status` | raw code only; verify lifecycle |
| handled | DERIVABLE | AEE `dealStatus` | current static logic treats 0 as unprocessed |
| handled at | AVAILABLE | AEE `dealTime` | restricted handling metadata |
| handler | RESTRICTED | may be user-related sensitive data | require business need and authorization |
| deal type | AVAILABLE | AEE `dealType` | code labels are partial |
| description | RESTRICTED | AEE alarm description / `dealDesc` | free text; require retention and display policy |
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
2. Current device GPS and raw GPS history are `AVAILABLE`; durable CHA location
   history is not yet implemented.
3. Media records are queryable, but their schema is only partially normalized.
4. Realtime usage history is `DERIVABLE` from current runtime events but is not
   persisted.
5. AEE alarm query capability is now `AVAILABLE` at interface/field level, but
   code maps, lifecycle/deletion semantics and retention remain partially
   unverified. AEE user activity remains `UNKNOWN`.
6. Missing values remain unknown/null. They must not be converted to zero for
   visual convenience.
