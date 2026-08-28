# M4 P2 — Live ONE SHOT Vertical Slice Evidence

Date: `2026-08-16`

Environment: authorized AEE session (VIDEOMONITOR test account), real Chrome,
3-day window `2026-08-13 00:00:00` ~ `2026-08-16 23:59:59` (Asia/Shanghai).

Security: rows were sanitized **inside the browser** before leaving the page;
only the projection `{id, devId, groupId, devType, status, time}` /
`{id, devId, groupId, fType, lType, source, upLoadStatus, fileLen, duration,
startTime, endTime, upLoadTime, isDeleted, title}` / `{id, devId, groupId,
alarmType, alarmTime, status, dealStatus, dealType}` was returned. No Token,
Cookie, path, oss, coordinates, people or work fields left the browser. The
live rows were written only to a local git-ignored directory.

## 1. Source (all `error=200`)

| Source | recordsTotal | sanitized rows |
| --- | --- | --- |
| `/api/v1/DevOnlineList` | 1857 | 1857 |
| `/api/v1/RecordFileList` | 805 | 805 |
| `/api/v1/AlarmList` | 46 | 46 |

## 2. Ingest #1 (normalizer → memory repository → ingestor)

| Source | accepted | invalid | error | stored |
| --- | --- | --- | --- | --- |
| device_status | 1857 | 0 | None | 1857 |
| media_files | 805 | 0 | None | 803 |
| alarms | 46 | 0 | None | 46 |

`media_files` stored 803 vs accepted 805: 2 source rows shared the same
`source_record_id` + device and were collapsed by the idempotent upsert
(flagged `source_id_scope_unverified`). Report `completed=True`.

## 3. Ingest #2 (same window, idempotency proof)

Stored counts after the second ingest: device_status 1857, media_files 803,
alarms 46 — identical to ingest #1. **No growth.**

## 4. Device metric reconciliation (`aggregate_device_uptime`)

* 54 devices, fetched 1857, invalid 0, duplicate events removed 303.
* Real `1→0→1` transition device `WXB301`:
  `offline_transitions=14`, `first_online=2026-08-12 17:31:51Z`,
  `last_offline=2026-08-15 17:26:03Z`, `online_seconds=126824`, event
  count 33, flags include `conflicting_status_same_time` (same-second
  0/1 conflict explicitly marked), `missing_start_state` and
  `open_interval_clipped_to_window_end`.
* Device `WXB305`: `offline_transitions=17`, also
  `conflicting_status_same_time`.
* Results are deterministic for the same input rows.

## 5. Media reconciliation (`aggregate_media_files`)

* 43 devices, fetched 805 = records_total 805, `partial=False`.
* image 17 / audio 6 / video 782.
* video_duration_seconds = 251306 (raw seconds, no early unit conversion).
* size_bytes = 147,809,843,624 (raw bytes).
* Per-device top: `WXB310` (62 files, 61 video, 17980 s, 9,640,017,453 B).

## 6. Alarm reconciliation (`normalize_alarm_events` → `aggregate_alarm_events`)

* Normalized 46 / invalid 0; stored 46.
* `alarm_type_counts = {2: 1, 205: 44, 206: 1}` — code `2` is beyond the
  live-verified 205/206 and is **preserved as raw, not dropped**; code map
  stays `UNKNOWN`/PARTIAL.
* `deal_status_counts = {0: 46}`; devices with alarms = 5;
  top `WXB358` (22×205), `WXB347` (9×205), `WXB369` (8×205).

## 7. Historical coverage (requested = 4 days)

| Domain | requested | available | completeness | range |
| --- | --- | --- | --- | --- |
| device_status | 4 | 4 | FULL | 2026-08-13 ~ 2026-08-16 |
| media_files | 4 | 4 | FULL | 2026-08-13 ~ 2026-08-16 |
| alarm_events | 4 | 4 | FULL | 2026-08-13 ~ 2026-08-16 |

Longer requests (e.g. 30 days) with only 3 days of data report
`completeness=PARTIAL (3/30)`, never a fake 30-day statistic.

## 8. Source isolation

* Collector collects each source independently (`status="ok"`/`"error"` +
  `error_code`); a failing DevOnlineList does not block RecordFileList or
  AlarmList.
* Scheduler report exposes per-source `status`, `error_code`,
  `last_successful_at` and `complete`; a failed source makes
  `report.completed=False`.

## 9. Status

* `M4 ACTIVE / P2 IN PROGRESS`.
* `POSTGRESQL_REHEARSAL_BLOCKED` (no isolated PostgreSQL runtime in this
  environment) — does not block other P2 code or verification.
* RealtimeViewEvent integration stays failure-isolated via
  `StoreViewEventSink` (stats write failure never fails the realtime
  session); no Token/Cookie/credential persisted.
* Production untouched; periodic scheduler remains disabled.
