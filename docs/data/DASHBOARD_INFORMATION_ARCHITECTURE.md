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
| today realtime views | finalized `RealtimeViewEvent` contract | DERIVABLE after persistence |
| long-time offline | future status history | DERIVABLE |
| long-time no upload | future media index | DERIVABLE |
| alarm count | normalized AEE `AlarmEvent` | DERIVABLE after complete ingestion |
| flight/task video coverage | normalized relations | DERIVABLE |

Unknown metrics must display “数据源未接入/待验证”, not zero.

### `/dashboard/devices` — Device operations

Views:

* current status by department/city/group;
* status freshness;
* 7/30-day uptime after event history exists;
* long-time offline;
* stale location;
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
