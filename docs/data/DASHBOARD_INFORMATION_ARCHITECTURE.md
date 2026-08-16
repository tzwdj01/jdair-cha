# M4 Dashboard Information Architecture

Last reviewed: `2026-08-15`

Status: `DESIGN / DATA-GATED`

## 1. Product position

M4 is a multi-page inspection data center. It is not one oversized screen and
it is not an AEE UI clone.

Realtime Video is a supporting drill-down action. The main value is:

* trustworthy operational data;
* historical trends;
* exception prioritization;
* device/media/flight/task relationships;
* transparent freshness and data quality.

### 1.1 Data domains (long-term, registered 2026-08-16)

The final CHA Dashboard revolves around these data domains:

1. 设备运行（device operations）;
2. 视频上传（media/files）;
3. 实时监察使用（realtime usage）;
4. 监察业务记录（inspection records）;
5. 告警/异常（alarms/exceptions）;
6. 飞机/航班/维修任务（aircraft/flights/maintenance tasks）;
7. 地点/地图（locations/map）;
8. 数据质量（data quality）。

Positioning:

* 总览页负责“发现问题”；
* 专题页负责“分析问题”；
* Inspection 页面负责“形成监察结论和业务留痕”。

Inspection records are planned in M4 P3; nothing in this section is
implemented before P2.5 completes.

## 2. First-release pages

### `/dashboard` — Inspection overview

Purpose:

* show current platform condition;
* summarize only metrics with verified sources;
* route users to focused pages.

Candidate cards:

| Metric | Source | Availability |
| --- | --- | --- |
| device total/online/offline | current device inventory | AVAILABLE |
| current online rate | current device inventory | AVAILABLE |
| today upload count | media record query/index | AVAILABLE, completeness required |
| 7/30-day upload trend | daily record counts/index | AVAILABLE, completeness required |
| current realtime sessions | runtime telemetry | AVAILABLE when feature enabled |
| today realtime views | finalized event + deterministic aggregation | DERIVABLE after persistence |
| long-time offline | future status history | DERIVABLE |
| long-time no upload | future media index | DERIVABLE |
| alarm count | normalized event + deterministic aggregation | DERIVABLE after complete ingestion |
| flight/task video coverage | normalized, confirmed relations | DERIVABLE after relation validation |

Unknown metrics must display “数据源未接入/待验证”, not zero.

### `/dashboard/devices` — Device operations

Views:

* current status by department/city/group;
* status freshness;
* 7/30-day uptime after event history exists;
* long-time offline;
* latest location age and raw event coverage;
* stale-location classification only after an approved threshold and source
  cadence are defined;
* device detail timeline.

Filters:

* city;
* department/group;
* current status;
* freshness/quality;
* time range.

Device detail actions:

* realtime video, when authorized and enabled;
* historical media;
* location track;
* flight/task references;
* alarms/exceptions.

### `/dashboard/media` — Media and file analysis

Views:

* today, 7-day and 30-day upload counts;
* volume by device, city and department;
* total duration/size only after units and scope are verified;
* latest upload time;
* long-time no upload;
* media-kind and status breakdown only after field cataloging.

Drill-down:

* trend → day → device → media rows → existing historical playback.

### `/dashboard/realtime` — Inspection usage

Views:

* current active sessions from runtime telemetry;
* today views and viewing time from persisted `RealtimeViewEvent`;
* first-frame success and latency;
* failure-reason distribution;
* views/time by user and device.

Privacy:

* user-level metrics require authenticated operational need;
* do not expose AEE credentials, session secrets or browser media parameters;
* define retention before production persistence.

## 3. Later data-gated pages

Add only when sources are verified:

* `/dashboard/alarms` (interface is known; add after lifecycle, privacy and
  retention rules are approved)
* `/dashboard/flights`
* `/dashboard/map`
* `/dashboard/data-quality`
* `/dashboard/inspections` (planned, M4 P3) — 监察业务记录

Planned `/dashboard/inspections` metrics (all computed from real
`InspectionRecord` / `RealtimeViewEvent`, no mock KPI):

* 今日监察次数、监察总时长、参与监察人数；
* 每账号监察次数/时长；
* 每设备被监察次数/时长；
* 涉及飞机数量、涉及航班数量、涉及维修任务数量；
* 发现问题次数 / 无问题次数 / 问题发现率；
* 问题类型分布、问题设备排行、问题飞机排行、问题站点排行、问题趋势。

Query scope for inspection records (P3): time range, inspector, account,
device, aircraft_no, flight_no, station, maintenance task, has_issue,
issue_type, issue_level.

Export (P3 first phase): CSV / XLSX with permission control; never export
Token / Cookie / Secret / internal media credential.

The Legacy record “reference information” helper is not a verified coverage
source. Its active path currently generates routine-task candidates only.
Candidate labels and scores must not be counted as confirmed flight/task video
coverage.

## 4. Drill-down model

```text
Overview
   |
   +-- Department / City
           |
           +-- Device
                   |
                   +-- Timeline
                          |
                          +-- Realtime video
                          +-- Historical media
                          +-- Location
                          +-- Flight / routine task
                          +-- Alarm / exception
```

Every drill-down request must preserve:

* selected scope;
* time range;
* source freshness;
* data-quality flags.

## 5. API architecture

Recommended read-only API groups:

```text
/api/v2/data/overview
/api/v2/data/devices
/api/v2/data/devices/{device_id}
/api/v2/data/devices/{device_id}/timeline
/api/v2/data/media
/api/v2/data/realtime
/api/v2/data/alarms
/api/v2/data/coverage
/api/v2/data/freshness
```

The exact routes may follow existing FastAPI conventions. Avoid wrapping the
same monolithic snapshot for every page; each endpoint should have a bounded
query and explicit data contract.

Each response should expose:

* `generated_at`;
* business timezone;
* requested scope/time range;
* source freshness;
* availability/data-quality status;
* nullable values for unavailable metrics;
* links or identifiers for drill-down.

Location aggregate responses must not expose coordinates unless the caller is
authorized for the device-detail/location scope. Summary pages should use only
counts, source span, latest-event age and explicit quality/completeness flags.

## 5.1 Store-backed data service

`app/services/inspection.py` provides the read-side page service over the
`InspectionStore`:

* `device_overview`: current online/offline/unknown counts, latest status per
  device, last online/offline times, range-clipped uptime and per-group
  rollups;
* `media_overview`: media-kind counts, video duration, file size, latest
  upload/create time, per-business-day upload counts and per-group rollups;
* `realtime_overview`: user/device view counts and durations, first-frame
  success and failure reasons;
* `alarm_overview` and `location_overview`.

It intentionally does not produce long-time offline, long-time no upload or
stale-location classifications because governed thresholds do not exist yet.
Raw coverage/age values are exposed instead. API routes and pages are not yet
wired.

The group dimension uses the source `group_id` (department/division key) and
provides the `部门/分组 → 设备` drill-down level; `city` remains a derived
value that is not produced until a governed geocoding/coordinate policy exists.

Threshold-based labels are governed by `CHA_V2_INSPECTION_THRESHOLDS`:
`long_no_upload_hours` (media) and `stale_location_hours` (locations) produce
hits only when configured; otherwise raw coverage/age values are shown and no
label is invented. “长时间离线” waits for the non-1 status map to be verified.

### 5.2 Read-only inspection API

`app/api/inspection.py` exposes the service over HTTP under
`/api/v2/inspection/{devices,media,realtime,alarms,locations}`.

Availability is explicit:

* feature flag `CHA_V2_FEATURE_INSPECTION_V2` off → `404 feature_disabled`;
* flag on but no store wired → `503 store_not_configured`;
* store wired → computed metrics with `source: inspection_store`, the requested
  scope and JSON-safe serialization.

The API is registered in the V2 app but the feature flag defaults to off, so
production behavior is unchanged. Dashboard pages are not wired yet.

### 5.3 First-batch inspection pages

`GET /api/v2/dashboard/{devices,media,realtime,alarms}` serve a shared four-tab
page
(`app/templates/inspection.html`) that consumes only the inspection API:

* `/dashboard/devices`: current online/offline/unknown, per-device online rate,
  online duration, offline transitions, last online/offline;
* `/dashboard/media`: media-kind counts, video duration, file size, latest
  upload, per-device upload and daily trend;
* `/dashboard/realtime`: per-user/per-device view counts and duration,
  first-frame success rate and failure reasons.
* `/dashboard/alarms`: raw alarm/status/deal code distributions and per-device
  alarm counts; code maps remain unverified, so no business labels are shown.
* `/dashboard/data-quality`: per-table row counts, rows carrying quality
  flags, latest event time, distinct device count, and source-system
  distribution for the requested window.

The page never fabricates values. When the store is not configured or has no
history, it displays “数据源未接入/待验证”. Long-time offline/no-upload and
stale-location classifications remain un-produced until governed thresholds
exist. Pages are feature-gated by `CHA_V2_FEATURE_INSPECTION_V2` (default off).

Device timeline drill-down:

* `GET /api/v2/inspection/devices/{device_id}/timeline` returns the device's
  scoped status events, media files and location coverage;
* coordinates are restricted and omitted from the response; only time,
  measurement and raw-code fields are returned;
* the devices page renders the timeline inline, giving the
  `总览 → 设备 → 时间线` drill-down path.

Realtime runtime state:

* `/api/v2/inspection/realtime` returns a `runtime` block with current active
  sessions/streams and Gateway/Media connections when a realtime session
  manager is wired; it is `null` otherwise;
* runtime state is reported separately from durable store history and is never
  mixed into historical metrics.

## 6. Data-source labels

Every page must distinguish:

* current live value;
* cached value;
* sampled snapshot;
* persisted historical event;
* derived metric;
* unavailable/unknown.

Recommended UI labels:

* 实时/当前；
* 缓存；
* 历史；
* 推导；
* 数据延迟；
* 数据源未接入；
* 数据质量异常。

## 7. Error and stale-data behavior

* one source failure must not blank unrelated pages;
* stale data may be served only within configured bounds;
* stale values display age and source;
* missing values remain null/unknown;
* partial pagination/query results display a partial-data flag;
* AEE report pages currently aggregate at most 10,000 raw file rows in the
  browser; CHA must not use those displayed totals without validating
  completeness or paging the source itself;
* source authentication failures are not converted to empty datasets;
* no page initiates frequent AEE login or media-monitor probes.

## 8. Realtime scope

M4 does not expand realtime concurrency as a primary goal.

* existing 1/4/6 capability is retained;
* near-term product maximum scope is 16 streams, only if a future approved
  business case and capacity test require it;
* 32 streams are `DEFERRED`;
* no complex AccountPool, FFmpeg, SFU, transcoding or H.265 workaround;
* realtime is linked from device/exception/timeline drill-down.

## 9. Acceptance evidence

For every visible metric:

1. field/source catalog entry;
2. availability classification;
3. query or event source;
4. freshness and timezone;
5. null/error behavior;
6. automated service test;
7. page/browser test;
8. drill-down target;
9. data-quality rule;
10. production rollout and rollback path.
