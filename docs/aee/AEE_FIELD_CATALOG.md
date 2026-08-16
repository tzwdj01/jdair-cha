# AEE Field Catalog

Last reviewed: `2026-08-16`

Status: `LIVE VERIFIED (2026-08-16) / PARTIAL`

This file catalogs sanitized field semantics. Unknown semantics remain
`UNKNOWN`; field names alone are not treated as proof.

## 1. Device-tree fields observed live

| AEE field | Example type | Observed meaning | Availability | Sensitivity | CHA mapping / note |
| --- | --- | --- | --- | --- | --- |
| `nid` / raw device identifier | string | stable device or group identity | AVAILABLE | internal | `device_id` or `group_id`, depending on `ntype` |
| `npid` | string | parent node identity | AVAILABLE | internal | group hierarchy parent |
| `ntext` / display name | string | device/group display name | AVAILABLE | internal | `device_name` or `group_name` |
| `ntype` | integer/string | node type | AVAILABLE | internal | code map requires verification |
| `ns1`, `ns2`, `ns3` | string/null | generic source slots | AVAILABLE | unknown | semantics remain `UNKNOWN` |
| `ni1`, `ni2`, `ni3` | number/null | generic numeric source slots | AVAILABLE | unknown | semantics remain `UNKNOWN` |
| `online` | integer/bool | management-tree online flag | AVAILABLE | internal | current status only |
| `status` | integer | management-tree status flag/code | AVAILABLE | internal | semantics beyond observed value `1` require cataloging |
| `alarm` | integer | current alarm code | AVAILABLE | internal | observed `205`; lifecycle/level requires verification |
| `alarmTime` | datetime/null | latest alarm time in normalized node | AVAILABLE | operational | source/lifecycle semantics require verification |
| `gpsTime` | datetime string | latest visible GPS/device timestamp | AVAILABLE | location-related | normalize timezone; use for freshness |
| `gpsType` | code/null | GPS source/type | AVAILABLE | location-related | code map unknown |
| `gpsLng`, `gpsLat` | number/string | latest coordinates | AVAILABLE | restricted location | validate range and coordinate system |
| `gpsAddr` | string/null | latest resolved address | AVAILABLE | restricted location | may contain sensitive location text |
| `gpsDirect`, `gpsSpeed` | number/null | direction and speed | AVAILABLE | restricted location | units/code semantics require verification |
| `battery` | numeric | raw battery field | AVAILABLE | operational | observed 0 on both control and target; units/reliability unknown |
| `netType`, `netSignal` | code/number/null | current network type/signal | AVAILABLE | operational | code/unit semantics unknown |
| `memSize`, `memUse` | number/null | device storage size/use | AVAILABLE | operational | units and update cadence require verification |
| `deviceType` | numeric | raw device type | AVAILABLE | internal | observed value 1; mapping unknown |
| `updated` | datetime/string/null | source node update marker | AVAILABLE | internal | exact semantics require verification |
| `enableVideo` | bool | device-level video capability flag | AVAILABLE | internal | does not guarantee current Media availability |
| draggable | bool/UI state | user may initiate monitor operation | DERIVABLE | permission-related | UI projection of permission, not device data |
| `ndata` | object | raw upstream node payload retained by page | AVAILABLE | high | do not persist wholesale; map only approved fields |

Evidence note:

`WXB358` had `online=1`, `status=1`, `enableVideo=true`, a stale `gpsTime` and
Media `devices is offline`. These fields must not be collapsed into one
synthetic health value without an explicit rule.

## 2. Device catalog fields recognized by CHA Legacy

| Raw field alternatives | Normalized meaning | Status | Notes |
| --- | --- | --- | --- |
| `szIDNO`, `devId`, `DevId` | device ID | AVAILABLE | stable identity candidate |
| `deviceName`, `szName`, `DeviceName`, `name` | display name | AVAILABLE | preserve source |
| `groupId`, `GroupId`, `roomId` | group identifier | AVAILABLE | hierarchy semantics require catalog |
| `groupName`, `GroupName` | group name | AVAILABLE | current maintenance filter uses group ID 30000002 |
| `nOnline`, `online` | current online flag | AVAILABLE | fallback when live DeviceStatus is absent |
| `nJingDu`, `lng` | longitude | AVAILABLE | coordinate validation required |
| `nWeiDu`, `lat` | latitude | AVAILABLE | coordinate validation required |
| `gpsTime` | source GPS timestamp | AVAILABLE | timezone/late-arrival policy required |

Exact AEE page use of these field names is still
`AEE VERIFICATION REQUIRED`.

## 3. GPS-history fields recognized by CHA Legacy

| Raw field alternatives | Normalized field | Status | Notes |
| --- | --- | --- | --- |
| `lat`, `latitude` | latitude | AVAILABLE | validate range |
| `lng`, `longitude` | longitude | AVAILABLE | validate range |
| `gpsTime`, `dateTime`, `time` | occurred time | AVAILABLE | semantics/timezone need verification |
| `speed` | speed | AVAILABLE | unit assumed by UI, must confirm |
| `direct`, `direction` | direction | AVAILABLE | unit/zero semantics need confirmation |
| `accuracy` | accuracy | AVAILABLE | unit/quality semantics unknown |
| `battery` | battery | AVAILABLE | units/scale unknown |
| `gpsType` | GPS source/type | AVAILABLE | code map unknown |
| `netWorkType` | network type | AVAILABLE | code map unknown |

## 4. Media-record fields

The AEE Server Files page and its current static source confirm the following
normalized row fields. Current CHA Legacy also recognizes alternative names
listed below.

| Raw field alternatives | Logical field | Status | Evidence note |
| --- | --- | --- | --- |
| `id` | upstream record ID | AVAILABLE | LIVE VERIFIED: globally unique across a 711-row 3-day window (not merely page-unique) |
| `devId`, `DevId`, `szIDNO` | device ID | AVAILABLE | normalized by Legacy |
| `deviceName`, `devName` | device name | AVAILABLE | may be filled from catalog |
| `title`, `fileName`, `name`, `fileTitle` | file title | AVAILABLE | AEE page uses `title`; Legacy has fallbacks |
| `startTime`, `fileTime`, `beginTime` | create/shoot time | AVAILABLE | LIVE VERIFIED non-null business-local times; `startTime/fileTime` equal in observed rows |
| `endTime`, `finishTime` | capture end time | AVAILABLE | LIVE VERIFIED non-null; equals `startTime` + `duration` in observed rows (e.g. 04:11:33 + 301s → 04:16:33) |
| `uploadTime`, `upLoadTime`, `endTime` | upload/end time | AVAILABLE | LIVE VERIFIED non-null; `upLoadTime` observed minutes after capture (upload lag) |
| `fileSize`, `fileLen`, `size` | size | AVAILABLE | LIVE VERIFIED: `fileLen` is bytes (e.g. 187109839 for a 301s video) |
| `duration`, `videoTime` | duration | AVAILABLE | LIVE VERIFIED: raw value is seconds for video (e.g. 301) and audio (e.g. 18); non-video duration treated as N/A |
| `fType` | media kind code | AVAILABLE | LIVE VERIFIED 3-day distribution: 1=image (16), 2=audio (6), 3=video (689); code 4 remains static-only |
| `lType` | list/import type | AVAILABLE | LIVE VERIFIED: 0=708, 1=3 in the observed window |
| `source` | source code | AVAILABLE | raw code; only the observed upload branch semantics are known |
| `upLoadStatus` | upload status code | AVAILABLE | when `source==2` and status is not `3`, page treats upload as incomplete/unavailable; full code map unknown |
| `workNo` | work number | AVAILABLE | user/operations-sensitive |
| `peopleNo` | personnel number | AVAILABLE | restricted user-related field |
| `peopleName` | personnel name/filter | AVAILABLE | restricted; presence in all row shapes not yet verified |
| `des` | description/remark | AVAILABLE | free text; restricted and requires retention policy |
| `groupId` | group identity | AVAILABLE | hierarchy relation |
| `isDeleted` | deletion marker | AVAILABLE | lifecycle semantics require verification |
| object key/playback alternatives | storage/playback key | UNKNOWN | identify safe stable field; do not record signed URL |
| channel | channel | UNKNOWN | sanitized AEE/MCS8 row required |

Server Files live table evidence (2026-08-16, authorized account, 3-day
window) confirms file title, type, MB, duration, capture/file time, upload
time, work number, personnel number and remark columns. A live read-only
search returned `recordsTotal=711` rows in one page (`pageCount=1`,
`length=1000`, `error=200`) with a 55-field schema including
`GId, bType, category, dasDevId, dasFileTime, dasIp, delTime, des, devId,
duration, enableSsl, endTime, enterId, fType, fileLen, fileName, fileTime,
firstFramePath, firstFrameStatus, gbDevId, groupId, id, ip, isDeleted,
keywords, lType, lat, lng, ossBucket, ossId, ossObjctName, ossType, path,
peopleNo, port, shortVideo, signType, source, startTime, storeType,
sttError, sttProvider, sttRaw, sttStatus, sttTaskId, sttText, sttTime,
taskNo, timeline, title, upLoadInfoStatus, upLoadStatus, upLoadTime,
vieoCode, webUrl, webUrlExpires, workNo`. `id` was globally unique across
all 711 rows; `isDeleted=false`, `source=0` and `upLoadStatus=0` across the
sample. Sensitive fields (`path`, `oss*`, `lat/lng`, `ip/port`,
`firstFramePath`, `webUrl*`, `peopleNo`, `workNo`, `dasIp`, `des`) are
recorded in the catalog only as field names and are not persisted by CHA.

The AEE File Num, Video Duration and File Size reports were also live-verified.
Their current browser aggregation:

* groups rows by `devId`;
* counts `fType==1/2/3` as image/audio/video;
* sums video `duration` and divides by 60 for minutes;
* sums all `fileLen` and divides by 1,048,576 for MB.

The report request uses a maximum page size of 10,000. CHA must surface
truncation/partial-data risk rather than assuming the report is complete.

Important separation:

recent uploaded-file activity for a device does not prove that its current
Realtime Media service is available. File ingestion and realtime monitoring
must remain separate dimensions.

Current CHA normalization boundary:

* verified aliases are normalized into the M4 `MediaFile` contract;
* `fileLen/fileSize/size` remains bytes and video duration remains seconds;
* `fType` maps only to the verified image/audio/video/device-file values;
* `source`, `upLoadStatus` and deletion markers are preserved as raw codes with
  partial/unverified-semantics flags;
* `id` is preserved as `source_record_id` with
  `source_id_scope_unverified`;
* `peopleNo`, `peopleName` and `des` are omitted by default and require an
  explicit restricted-data decision to enter the normalized object;
* normalization is implemented and tested but is not yet persisted, exposed
  through an API or connected to production ingestion.

## 5. Realtime fields

These are CHA-owned fields derived from the existing M3 session manager, not
AEE user-audit fields.

| Field | Source | Availability | Persistence |
| --- | --- | --- | --- |
| `username` | CHA authenticated session | AVAILABLE | not persisted |
| `session_id` | CHA session manager | AVAILABLE | runtime only |
| `stream_id` | CHA session manager | AVAILABLE | runtime only |
| `device_id` | selected realtime device | AVAILABLE | runtime only |
| `opened_at` | stream creation time | AVAILABLE | runtime only |
| `first_frame_at` | first-frame event | AVAILABLE | runtime only |
| `closed_at` | stream close time | AVAILABLE | runtime only |
| `duration_seconds` | derived | DERIVABLE | not implemented |
| `result` | final lifecycle state | DERIVABLE | not implemented |
| `error_code` | normalized CHA error | AVAILABLE | runtime only |

These fields define the minimum future `RealtimeViewEvent`.

## 6. Alarm fields

| Target field | Status | Required evidence |
| --- | --- | --- |
| `alarm_id` (`id`) | AVAILABLE | LIVE VERIFIED: AlarmList row `id` present in a 41-row 3-day window |
| `device_id` (`devId`) | AVAILABLE | live page/static row and device alarm context |
| `alarm_type` (`alarmType`) | AVAILABLE | LIVE VERIFIED: raw codes 205 (40 rows) and 206 (1 row) observed; human label/code map still partial |
| `level` | UNKNOWN | source code/label |
| `created_at` (`alarmTime`) | AVAILABLE | LIVE VERIFIED: non-null business-local times in AlarmList rows |
| alarm status (`alarmStatus`/push `status`) | AVAILABLE | LIVE VERIFIED: **AlarmList rows carry no `alarmStatus` field**; alarm status is the `status` column (null in the observed sample; push contract uses it too) |
| `deal_status` (`dealStatus`) | AVAILABLE | LIVE VERIFIED: raw code present; 0 observed across the sample; static logic treats 0 as unprocessed and values greater than 0 as handled |
| `handled` | DERIVABLE | `dealStatus` after code-map confirmation |
| `handled_at` (`dealTime`) | AVAILABLE | restricted handling metadata |
| `handler` (`dealUser`) | RESTRICTED | user-related field; requires business need and authorization |
| `deal_type` (`dealType`) | AVAILABLE | raw code; UI includes manual confirmation, system processing and other |
| `description` (`dealDesc`/alarm description) | RESTRICTED | free text or mapped description; retention and display scope required |

Live alarm page evidence (2026-08-16) confirms the query endpoint, visible
columns and non-empty paginated rows (`recordsTotal=41`, `length=1000`,
`error=200`). Row schema:
`id, enterId, groupId, devId, alarmTime, alarmType, status, alarmDesc,
dealType, dealStatus, dealUser, dealTime, dealDesc, gpsModel, code, ex,
keywords, peopleNo, workNo`. Sanitized rows showed a low-battery alarm label,
percentage description and `Waiting` deal-state label. The raw alarm/deal code
maps, deletion semantics and complete lifecycle remain partial evidence.

CHA normalization status:

* `AlarmEvent` now requires source `id`, `devId`, `alarmType` and
  `alarmTime`;
* alarm, status, deal-status and deal-type codes remain raw integers with
  partial-map quality flags;
* `handled` remains `null`; the implementation does not infer it from an
  incomplete `dealStatus` map;
* `dealUser`, `dealTime` and `dealDesc` are omitted by default and require an
  explicit restricted-field opt-in;
* source-ID scope, deletion semantics, lifecycle and retention remain
  unverified and are not hidden by friendly labels.

Alarm live-push static evidence:

* method/event: `AlarmUpload`;
* fields: `alarmType`, `status`, `devId`, `alarmTime`, `GPSModel/gPSModel`;
* observed code path: status `2` clears the current alarm; other statuses
  update the device alarm/GPS projection.

This does not yet prove the complete alarm lifecycle or retention semantics.

## 7. Device detail and online-history fields

Static AEE code shows the exact Gateway command `getDeviceInfo` and displays:

* `battery`;
* `devId`;
* `hardware`;
* `lat`, `lng`;
* `network`;
* `peopleNo`;
* `recording`;
* `totalSize`, `useSize`;
* `version`;
* `workNo`.

The live response, permission boundary, error behavior and storage-unit
semantics remain `AEE VERIFICATION REQUIRED`.

The current online-statistics page uses `/api/v1/DevOnlineList` with:

* query fields:
  `st`, `et`, `enterId`, `groupId`, `devId`, `keywords`, `page`, `pagesize`;
* row fields used by the page:
  `id`, `devId`, `groupId`, `devType`, `status`, `time`; the full live row
  schema also includes `enterId, enterName, groupName, devName, lat, lng,
  addr, remarks, storeType, network, battery, totalSize, useSize, version,
  hardware`.

Live verification on `2026-08-16` (authorized account, Statistics/Online
page, 3-day window, `error=200`) returned `recordsTotal=1696`,
`pageCount=1`, `length=10000`. `id` was unique across all 1696 rows and
`time` was non-null business-local time (`"2026-08-13 00:31:11"` style).
`status` distribution was `1=849` and `0=847`; `devType` was `1=1249` and
`2=447`; `storeType`, `network` and `battery` were almost uniformly `0`.
Transition rows were observed: the same device can appear with `status=0`
and `status=1` at the same second (e.g. `WXB312`), and `WXB301` showed
`1 → 0 → 1` across minutes — these are online/offline transition rows, not
deduplicated snapshots.

The static page algorithm interprets `status==1` as online and another status
as closing the online interval. It groups by `devId`, sums interval seconds and
counts close transitions. The live page displayed non-empty per-device online
duration results.

Important quality caveats:

* exact meanings of all non-1 status codes remain unknown;
* upstream ordering and duplicate guarantees remain unknown;
* retention and pagination limits remain unknown;
* an unclosed interval is extended to browser current time by the AEE page,
  rather than explicitly clipped to the requested query end.

CHA must ingest raw rows, sort/deduplicate them and clip calculations to the
requested reporting window. It must not copy the page algorithm blindly.

Current CHA normalization preserves every valid `status` as `status_code`.
`status==1` is normalized to `online=true` and `status==0` is normalized to
`online=false` (live-verified in the observed dataset). Any other value keeps
`online=null` plus `non_online_status_map_partial` and
`online_state_unknown`. This prevents an unverified code map from becoming a
false historical offline event.

## 8. Field governance

For every durable CHA field:

* preserve source system and source field;
* record `occurred_at`, `observed_at` and `ingested_at` where relevant;
* record derivation method for derived fields;
* preserve null/unknown rather than using zero;
* document units and timezone;
* document sensitivity and retention;
* do not persist tokens, Cookies, Authorization headers, signed media URLs or
  page-private connection parameters.
