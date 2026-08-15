# AEE / MCS8 Interface Catalog

Last reviewed: `2026-08-15`

Status: `INITIAL / SANITIZED / LIVE+STATIC EVIDENCE`

No credential, reusable token, Cookie, Authorization value or private media URL
is recorded here.

## Catalog rules

Each interface must record:

* product page or operation;
* transport;
* method/path or SDK method;
* request parameters;
* response fields;
* permission;
* refresh behavior;
* stability;
* sensitivity;
* CHA status and migration recommendation.

An interface found only in CHA Legacy is labeled accordingly. It must not be
claimed as an AEE page interface until the AEE page is observed using it or
upstream documentation confirms it.

## HTTP data authentication boundary

Current sanitized evidence:

| Item | Evidence |
| --- | --- |
| Login endpoint | `/api/v1/auth/Token`, already used by the server-side M3 AEE Adapter and `STATIC VERIFIED` in the current AEE bundle |
| Login output | response `access_token`; no value was read or recorded |
| Browser storage | current AEE code places the access token in session-scoped browser state |
| Data request header | current AEE request helper initializes a custom HTTP header named `token` from that session-scoped access token |
| Live correlation | authorized DevTree, RecordFileList, AlarmList and DevOnlineList page requests succeeded through the same helper |
| 401 behavior | the current page has bounded HTTP error handling; an explicit token-refresh contract was not found |
| Token lifetime | `AEE VERIFICATION REQUIRED` |
| Cookie dependency | same-origin browser requests may also carry browser session state; token-only server integration is not yet live-isolated |

Security conclusion:

* the AEE data API does **not** use an evidenced
  `Authorization: Bearer <token>` contract;
* CHA must use a server-side token provider and the evidenced custom `token`
  header;
* token values, browser storage and credentials must never be returned to the
  CHA browser, logged or committed;
* a token-only, read-only live integration check is still required before
  enabling ingestion.

CHA implementation status:

* `AEEDataHTTPClient` now provides an exact GET allowlist, injected in-memory
  token provider, bounded CHA error codes and one retry after a 401-driven
  token invalidation;
* `AEEReadOnlyDataAdapter` now provides endpoint-specific, read-only contracts
  for DevTree, DevOnlineList and RecordFileList, with explicit source timezone,
  range and pagination validation plus bounded page-envelope parsing;
* `collect_aee_pages` now follows pages deterministically and exposes
  max-page/max-record truncation, changing totals, empty pages, unknown totals,
  duplicate source IDs and invalid rows as quality evidence;
* it contains no username/password login logic and is not connected to an API,
  scheduler, database or production configuration;
* login ownership, token lifetime and refresh remain separate evidence-gated
  work.

## Confirmed interfaces

### AEE device tree

| Item | Value |
| --- | --- |
| Page | GIS, Monitor and APPS shared navigation |
| Transport | HTTP GET |
| Path | `/api/v1/ext/DevTree` |
| Request parameters | none observed |
| Response shape | hierarchical device/group rows; normalized fields are cataloged in `AEE_FIELD_CATALOG.md` |
| Permission | authenticated AEE user; exact read permission name not yet isolated |
| Refresh | loaded on page entry; live alarm/status changes may also arrive through the existing Gateway connection |
| Evidence | `LIVE VERIFIED` in an authorized session; field semantics remain partial |
| Sensitivity | internal device, group, location and operational status data |
| Classification | Class A |
| CHA recommendation | use a server-side, narrow read-only Adapter; never expose AEE credentials to the browser |

### AEE server file list

| Item | Value |
| --- | --- |
| Page | `/v3/tabs/file` |
| Transport | HTTP GET |
| Path | `/api/v1/RecordFileList` |
| Observed query fields | `devId`, `groupId`, `groupWithChild`, `isDeleted`, `page`, `pagesize`, `timeSelector`, `timeType`, `st`, `et`, cache-buster `_` |
| Additional static query fields | `fType`, `lType`, `title`, `workNo`, `peopleNo`, `peopleName`, `des` |
| Response envelope | rows under `data`; total under `recordsTotal` |
| Live result | read-only search returned hundreds of records with device, file title, media type, size, duration, capture time, upload time and personnel/work references |
| Permission | authenticated file-query access; exact permission name not yet isolated |
| Refresh | user-initiated search/pagination |
| Evidence | endpoint and basic table schema `LIVE VERIFIED`; expanded filters and code branches `STATIC VERIFIED` |
| Sensitivity | media metadata; `workNo`, `peopleNo`, names and descriptions may be user-sensitive |
| Classification | Class A |
| CHA recommendation | normalize metadata only; do not persist signed playback URLs, tokens or private storage connection material |

### AEE file statistics reports

| Item | Value |
| --- | --- |
| Pages | `/v3/tabs/report/reportFile/fileNum`, `/fileDuration`, `/fileSize` |
| Upstream data | `/api/v1/RecordFileList` with `st`, `et`, `enterId`, `groupId`, `devId`, `keywords`, `page`, `pagesize` |
| Live outputs | per-device/group image count, audio count, video count, total video minutes and total file MB |
| Current aggregation | browser groups raw rows by `devId`; counts `fType` 1/2/3, sums video `duration/60`, sums all `fileLen/1048576` |
| Evidence | all three report pages and non-empty results `LIVE VERIFIED`; aggregation code `STATIC VERIFIED` |
| Data-quality caveat | page requests up to 10,000 raw rows and aggregates client-side; completeness depends on upstream truncation/pagination behavior |
| Classification | raw RecordFileList is Class A; the page aggregation/UI is Class D reference |
| CHA recommendation | compute deterministic server-side aggregates from normalized rows, expose partial/truncation flags and do not copy browser-only report logic |

### AEE alarm list

| Item | Value |
| --- | --- |
| Page | `/v3/tabs/alarm` |
| Transport | HTTP GET |
| Path | `/api/v1/AlarmList` |
| Live query fields | `devId`, `alarmType`, `alarmStatus`, `dealType`, `dealStatus`, `s5`, `keywords`, `page`, `pagesize`, `groupId`, `groupWithChild`, `timeType`, `st`, `et`, cache-buster `_` |
| Live table columns | device name, group name, time, alarm, alarm description, deal status, deal user, deal time, deal description, action |
| Static row fields | `id`, `devId`, `alarmType`, `alarmTime`, `dealStatus`; display/detail branches also use handling fields |
| Live result | selected authorized lookback returned non-empty, paginated rows including alarm label, alarm description and unprocessed/waiting handling state |
| Permission | authenticated alarm-page access; handling actions require separate authorization and are outside the current read-only investigation |
| Refresh | user search plus alarm push through the existing Gateway session |
| Evidence | endpoint, query fields and visible schema `LIVE VERIFIED`; row/handling code paths `STATIC VERIFIED` |
| Sensitivity | operational alarms; handler identity and free text are restricted |
| Classification | Class A for query; alarm push is an upstream event source |
| CHA recommendation | ingest read-only events after retention/privacy rules are approved; do not invoke deal/update actions in M4 discovery |

### AEE alarm handling update

| Item | Value |
| --- | --- |
| Page | alarm handling dialog |
| Transport | HTTP request from page code |
| Path | `/api/v1/AlarmUpdateDeal` |
| Static fields | `id`, `dealUser`, `dealTime`, `dealType`, `dealStatus`, `dealDesc` |
| Evidence | `STATIC VERIFIED` only |
| M4 status | `RESTRICTED`; not called during read-only investigation |
| Classification | write operation, outside current Class A ingestion scope |
| CHA recommendation | do not migrate or call without a later explicit business, permission, audit and production-safety decision |

### AEE device online history

| Item | Value |
| --- | --- |
| Page | `/v3/tabs/report/reportDev/online` |
| Product capability | device online transition list with client-side duration aggregation |
| Transport | HTTP GET |
| Path | `/api/v1/DevOnlineList` |
| Live query fields | `st`, `et`, `enterId`, `groupId`, `devId`, `keywords`, `page`, `pagesize` |
| Response fields used by current page | `id`, `devId`, `groupId`, `devType`, `status`, `time` |
| Current page derivation | groups rows by `devId`; `status==1` opens/continues an online interval, other statuses close it; sums seconds and counts close transitions |
| Live result | authorized page returned a non-empty, paginated device list with computed online duration |
| Evidence | endpoint/query/UI `LIVE VERIFIED`; aggregation algorithm and row fields `STATIC VERIFIED` |
| Remaining unknowns | upstream event generation, ordering guarantee, exact non-1 status map, retention, duplicate behavior and pagination/rate limits |
| Important caveat | the current page extends an unclosed online interval to browser current time; this algorithm must not be copied without clipping to the requested range and testing boundary conditions |
| Classification | Class A |
| CHA recommendation | ingest raw transition rows, sort and deduplicate explicitly, preserve source status/time, and compute reproducible range-clipped metrics in CHA |

Current CHA contract:

* start/end must be timezone-aware and are formatted in an explicitly supplied
  source timezone;
* `enterprise_id` is required;
* page numbers are positive and page size is bounded to 10,000;
* malformed rows and unknown totals are retained as data-quality flags rather
  than silently treated as complete data.
* source IDs are observed for duplicate diagnostics but are not deduplicated
  because their uniqueness scope remains unverified.

### AEE task list

| Item | Value |
| --- | --- |
| Product capability | task list used by GIS side panel |
| Transport | HTTP GET |
| Path | `/api/v1/TaskList` |
| Static query fields | `st`, `et`, `taskType`, `taskStatus` |
| Evidence | `STATIC VERIFIED` |
| Response schema / business relation | `AEE VERIFICATION REQUIRED` |
| Classification | potential Class A |
| CHA recommendation | compare with existing AMRO routine-task data before introducing a second task source |

### AEE job line by record

| Item | Value |
| --- | --- |
| Product capability | record-associated job/track line |
| Transport | HTTP request |
| Path | `/api/v1/JobLineByRecordId` |
| Evidence | `STATIC VERIFIED` |
| Request/response semantics | `AEE VERIFICATION REQUIRED` |
| Classification | potential Class A |
| CHA recommendation | investigate only if media-to-task/location drill-down requires it |

### AEE user configuration

| Item | Value |
| --- | --- |
| Product capability | page/user configuration |
| Transport | HTTP GET |
| Path | `/api/v1/UserConfig` |
| Observed query fields | `configType`, cache-buster `_` |
| Observed config types | map/message page configuration |
| Evidence | `LIVE VERIFIED` |
| Classification | Class D unless a specific operational requirement emerges |
| CHA recommendation | do not treat page preferences as inspection data or a runtime dependency |

### AEE device information command

| Item | Value |
| --- | --- |
| Page operation | device information panel |
| Transport | existing authenticated Gateway request |
| Command | `getDeviceInfo` |
| Request | `devId` |
| Static response fields | `battery`, `devId`, `hardware`, `lat`, `lng`, `network`, `peopleNo`, `recording`, `totalSize`, `useSize`, `version`, `workNo` |
| Evidence | exact command and display mapping `STATIC VERIFIED` |
| Live response | `AEE VERIFICATION REQUIRED` |
| Sensitivity | device metadata, location and personnel/work references |
| Classification | potential Class A through a server-side supported Adapter; Gateway protocol behavior remains Class B infrastructure |
| CHA recommendation | verify live permission, units and error behavior before ingestion; never expose Gateway credentials |

### AEE signed file access

| Item | Value |
| --- | --- |
| Page operation | file preview/download |
| Transport | HTTP GET |
| Path | `/api/v1/oss/SignedUrl` |
| Query | `id` |
| Static response fields | relative/public URL and content type |
| Evidence | `STATIC VERIFIED` |
| Sensitivity | high; returned URL may grant temporary media access |
| Classification | restricted operational interface |
| CHA recommendation | do not persist or log signed URLs; metadata ingestion must remain independent of preview/download |

### Realtime media monitor

| Item | Value |
| --- | --- |
| Page | `/v3/gisMonitor/monitor` |
| Transport | Gateway/Media WebSocket through current MCS8 SDK |
| Operation | `mediaMonitor` |
| Verified request fields | device ID, kind=`video`, `streamType=2`, channel/server context |
| Verified result | `opened` or upstream error such as `devices is offline` |
| Permission | `VIDEOMONITOR` |
| Refresh | user initiated; AEE UI may retry failed open about every 3 seconds |
| Stability | current product behavior verified on 2026-08-14 |
| Sensitivity | session/media connection data is sensitive |
| Classification | Class B operation; open result may be Class A availability evidence |
| CHA recommendation | keep existing M3 Adapter; do not use repeated media opens as a Dashboard poll |

### Realtime media close

| Item | Value |
| --- | --- |
| Transport | Gateway/Media WebSocket |
| Operation | `closeMediaMonitor` |
| Verified result | closes successful and failed monitoring attempts |
| Permission | same authorized media context |
| Classification | Class B |
| CHA recommendation | retain explicit close and resource-release semantics |

### New media consumer

| Item | Value |
| --- | --- |
| Transport | Media WebSocket + WebRTC |
| Event | `newConsumer` |
| Verified fields | `rtpParameters`, codec list, app data, track |
| Verified codec sample | H.264 `profile-level-id=42e01f`, 1920×1080 on WXB353 |
| Classification | Class B |
| CHA recommendation | M4 may use only aggregate operational outcomes already produced by M3; no media redesign |

## MCS8 interfaces verified in current CHA Legacy

### Device catalog

| Item | Value |
| --- | --- |
| Source | current CHA Legacy |
| Transport | HTTP GET to MCS8 API |
| Path | `/api/GetDevListByGroupId` |
| Parameters | `groupType=0`, `groupId=0` |
| Response | list of raw catalog rows |
| Current CHA use | builds maintenance device inventory |
| Current cache | 30 seconds |
| AEE page usage | `AEE VERIFICATION REQUIRED` |
| Sensitivity | internal device metadata |
| Recommendation | create normalized adapter after field catalog and live response validation |

### GPS history

| Item | Value |
| --- | --- |
| Source | current CHA Legacy |
| Path | `/api/GetGpsModelList` |
| Parameters | start, end, device ID, page, page size |
| Response fields currently recognized | latitude, longitude, GPS time, speed, direction, accuracy, battery, GPS type, network type |
| Current CHA use | GPS track and recent-city derivation |
| AEE page usage | `AEE VERIFICATION REQUIRED` |
| Sensitivity | location data; restricted operational data |
| Recommendation | minimize scope, audit access, normalize event/observation time |

### Record-file list

| Item | Value |
| --- | --- |
| Source | current CHA Legacy |
| Path | `/api/GetRecordFileList` |
| Parameters | start, end, live/type selector `lt=-1`, optional device ID, page, page size |
| Response | raw rows under several possible container names |
| Current CHA use | records page, per-device 3-day count/size, daily count trend |
| AEE page usage | `AEE VERIFICATION REQUIRED` |
| Sensitivity | media metadata and potentially object identifiers |
| Recommendation | capture sanitized rows; create stable `MediaFile` mapping; never persist signed URLs or storage secrets |

## Remaining AEE interface evidence gaps

| Capability | Expected page/scenario | Required evidence | Status |
| --- | --- | --- | --- |
| device tree | GIS/Monitor/APPS | complete code maps, group hierarchy semantics, refresh/push cadence | PARTIAL LIVE EVIDENCE |
| group tree | device navigation | stable group IDs, parent relation, rename/deletion behavior | PARTIAL LIVE EVIDENCE |
| current device status | device tree/detail | exact semantics for `status`, `online`, alarm and GPS freshness | PARTIAL LIVE EVIDENCE |
| device detail/model | device detail | live `getDeviceInfo` response, permission, model/firmware/network/battery/capability semantics | STATIC PARTIAL / AEE VERIFICATION REQUIRED |
| device online history | statistics/device-online page | sanitized raw response, non-1 status map, ordering, retention, duplicates and pagination limits | LIVE+STATIC PARTIAL |
| media/file search | server files | stable ID uniqueness, code maps, status/storage/channel semantics | LIVE+STATIC PARTIAL |
| alarm list | alarm page | complete lifecycle/code maps, retention, deletion semantics and pagination limits | LIVE+STATIC PARTIAL |
| user sessions | administration/audit page, if authorized | endpoint, retention, privacy restrictions | AEE VERIFICATION REQUIRED |
| viewing audit | monitoring/audit page, if provided | device/user/session/duration fields | AEE VERIFICATION REQUIRED |

## Stability and migration policy

* Prefer documented or stable backend read-only interfaces.
* Wrap AEE/MCS8 data in a narrow CHA Adapter.
* Persist normalized CHA records, not raw authenticated responses.
* Store source interface/version and ingestion timestamp.
* Do not make Dashboard rendering depend directly on AEE page-private APIs.
* Do not expand an interface catalog through protocol guessing.
