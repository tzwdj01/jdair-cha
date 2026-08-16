# AEE Data Verification Runbook

Last reviewed: `2026-08-16`

Status: `EXECUTED 2026-08-16 (authorized VIDEOMONITOR account) / PARTIAL`

Execution note: this runbook was executed on `2026-08-16` with an authorized
test account (sufficient `VIDEOMONITOR` permission) in a real Chrome session.
DevOnlineList, RecordFileList and AlarmList live evidence was
captured and the sanitized conclusions were written to
`AEE_CAPABILITY_MATRIX.md`, `AEE_INTERFACE_CATALOG.md`,
`AEE_FIELD_CATALOG.md` and `DATA_AVAILABILITY_MATRIX.md`. Deterministic
fixtures derived from the sanitized samples were added under
`mature-modernization/v2/tests/fixtures/` with regression coverage in
`tests/test_aee_live_fixtures.py`. No credential, Cookie or reusable token was
recorded. Server-side token-lifecycle verification remains the next step.

Token/Cookie boundary result (2026-08-16, same authorized session):

* `fetch` without the page-injected `token` header → `error=333` (HTTP 200,
  empty data): the data API is `TOKEN_REQUIRED`.
* `fetch` with only the custom `token` header and `credentials:'omit'`
  (no Cookie sent) → `error=200` on both `/api/v1/DevOnlineList` (716 rows)
  and `/api/v1/RecordFileList` (347 rows): **token-only, no-Cookie requests
  succeed**, which is the exact server-side contract CHA will use.
* Token values were only ever referenced inside the page context; no value
  was read, logged or recorded.

This runbook turns the P0 `AEE VERIFICATION REQUIRED` items into concrete,
lawful observation steps. It only observes the authorized AEE session that the
project owner opens; it never bypasses permissions, never automates write
actions, and never records credentials.

## 1. Global rules (must hold for every step)

* Use an authorized test account with sufficient read permission (for example
  `VIDEOMONITOR`), in the same browser/network/time window as the target
  comparison.
* Never capture or save:
  * Cookie values, `Authorization` headers, passwords;
  * reusable or long-lived tokens (only record a redacted prefix like
    `tok_ab12…`);
  * private media URLs, SDP/ICE, or raw WebSocket payloads.
* Use only browser developer tools (Network, Console, WS inspector,
  Performance) and the page's normal UI.
* All captured rows must be sanitized before being written to a result file:
  replace free-text person/work fields with `[redacted]`, drop
  handler/deal-description free text, and keep only the fields listed below.
* Results go into a local ignored file (never Git), and the redacted
  conclusions are entered into the capability/field catalogs.

## 2. What to record per request

For every observed HTTP request, record:

```text
method path
query (full, including start/end/page/pagesize and selectors)
request headers that are NOT cookies/authorization/token (e.g. accept)
response status
response container name (data/list/records/Content/…)
row count in response
upstream total / page / pageSize fields when present
latency_ms (if visible)
```

Never record the `token` header value or any `Set-Cookie`.

## 3. A. DevOnlineList verification

Target: the authorized Statistics/Online page.

Observe:

1. The exact path and full query used for a window (start/end/enterprise/
   group/page/pageSize).
2. A raw response with at least two pages.
3. For every row, the raw fields actually present (for example `devId`,
   `status`, `time`, `groupId`, `id`, any extra numeric/text fields).

Questions to answer (record answers only):

* Is `status` always `1` when online? What other values appear and when?
* Is ordering by time stable? Are duplicates present? Do duplicate rows carry
  the same `id`?
* What time precision does `time` use, and is it business local time?
* Does the page count/`total` change across pages in the same window?
* How far back does history go (retention)? What happens at the oldest
  boundary?
* Does the response require the session cookie, or does the custom `token`
  header alone work?

Evidence template (sanitized):

```json
{
  "test": "dev_online_list",
  "window": {"start": "…", "end": "…"},
  "page": 1,
  "total_reported": 0,
  "row_count": 0,
  "status_values_seen": [],
  "ordering": "…",
  "duplicates_seen": false,
  "cookie_required": "unknown",
  "retention_boundary_observed": "…"
}
```

## 4. B. RecordFileList verification

Target: the authorized Server Files page.

Observe:

1. The exact path and query (start/end/type selector/page/pageSize/device).
2. At least two pages of raw rows.
3. Per row: `id`, `devId`, `title`, `fType`, `lType`, `source`,
   `upLoadStatus`, `fileLen`, `duration`, `startTime`, `uploadTime`,
   `workNo` (mark `[redacted]` if free text/person), and any other fields
   present.

Questions to answer:

* Is `id` unique across all devices/pages, or only per device/page?
* What is the max page count / max rows before truncation (e.g. 10,000)?
* What values do `fType`, `lType`, `source`, `upLoadStatus` take?
* Which of `startTime` / `fileTime` / `beginTime` is actually populated, and
  what do they mean (shoot vs upload)?
* Does the response need the session cookie or only the custom `token`?

Evidence template:

```json
{
  "test": "record_file_list",
  "window": {"start": "…", "end": "…"},
  "page_size_requested": 0,
  "total_reported": 0,
  "row_count": 0,
  "fType_values_seen": [],
  "lType_values_seen": [],
  "source_values_seen": [],
  "upLoadStatus_values_seen": [],
  "id_scope": "unknown",
  "max_rows_before_truncation": null,
  "cookie_required": "unknown"
}
```

## 5. C. Token-only vs Cookie dependency

Target: the same data endpoints, using a request editor (e.g. browser
devtools "edit and replay" or a temporary local script).

Procedure:

1. Capture a normal data request from the page and note its headers.
2. Replay it with the custom `token` header only (no Cookie header). Record the
   status and whether rows return.
3. Replay it with the session Cookie but no `token`. Record the status.
4. Replay it with an intentionally wrong/expired `token`. Record the status and
   error shape.
5. Replay the exact same request twice a few minutes apart and record whether
   the token still works (lifetime/refresh signal).

Never save the actual token value. Record only:

```json
{
  "test": "token_cookie_dependency",
  "endpoint": "/api/…",
  "token_only": "ok | 401 | other",
  "cookie_only": "ok | 401 | other",
  "wrong_token": "status",
  "replay_after_minutes": 0,
  "replay_status": "…"
}
```

## 6. D. AlarmList code map and lifecycle

Target: the authorized Alarm page.

Observe:

1. The exact query (timeType, groupWithChild, page/pageSize, any filters).
2. At least two pages of rows.
3. Per row: `id`, `devId`, `alarmType`, `alarmStatus`, `dealStatus`,
   `dealType`, `alarmTime`, `dealTime`, `isDeleted` (mark handler/description
   as `[redacted]`).

Questions to answer:

* Which `alarmType` / `alarmStatus` / `dealStatus` / `dealType` values appear?
* How do status/deal codes change over time for the same `id` (update vs new
  row)?
* Is `alarmTime` business local time? Is `dealTime` populated only when dealt?
* Are deleted rows returned with `isDeleted`?

Evidence template:

```json
{
  "test": "alarm_list",
  "window": {"start": "…", "end": "…"},
  "row_count": 0,
  "alarmType_values_seen": [],
  "alarmStatus_values_seen": [],
  "dealStatus_values_seen": [],
  "dealType_values_seen": [],
  "lifecycle_observed": "…",
  "deleted_rows_seen": false,
  "cookie_required": "unknown"
}
```

## 7. Result handling

* Fill one evidence template per test into a local ignored result file.
* Enter redacted conclusions into:
  * `docs/aee/AEE_INTERFACE_CATALOG.md`;
  * `docs/aee/AEE_FIELD_CATALOG.md`;
  * `docs/aee/AEE_CAPABILITY_MATRIX.md`;
  * `docs/data/DATA_AVAILABILITY_MATRIX.md`.
* Update `TASK_GOAL.md` `AEE Verification Required` entries to
  `COMPLETED / VERIFIED` only for items with direct evidence; everything else
  stays `UNKNOWN` / `AEE VERIFICATION REQUIRED`.
