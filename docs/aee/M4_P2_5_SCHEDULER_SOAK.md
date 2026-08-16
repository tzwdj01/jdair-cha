# M4 P2.5 — Low-Rate Controlled Scheduler Soak (Design)

Status: `EXECUTED 2026-08-16 (controlled, non-production) / PASS`.

Soak may only start **after** all of the following are PASS:

* Media identity confirmed (see `M4_P2_5_IDENTITY_DEDUP_AUDIT_20260816.md`);
* Device dedup confirmed;
* PostgreSQL migration rehearsal PASS;
* PostgreSQL backup/restore rehearsal PASS;
* ONE SHOT PostgreSQL ingest PASS;
* Metric reconciliation PASS.

It runs only in a **non-production** environment; the production scheduler
stays disabled.

Execution note (2026-08-16): after PostgreSQL migration, ONE SHOT ingest,
idempotency, backup/restore, rollback, metrics reconciliation and
PG-backed Dashboard all PASS, a controlled soak ran against the disposable
`cha_m4_rehearsal` database: 3 overlapping runs of `InspectionIngestionScheduler`
with `PostgresInspectionStore` and a deterministic fixture collector, with a
device-status source failure injected on run 2. Results: no row growth
(1857/805/46 stable), source isolation (media/alarms persisted, no loss),
recovery on run 3 without inflation, bounded request volume (3 collection
calls). A **live** AEE token-expiry observation is not part of this controlled
soak (no server-side token was used); it remains a live-environment
observation item.

## 1. Goal

Validate the periodic collection loop, not realtime delivery. Initial soak
uses a conservative cadence to observe:

* watermark / overlap behavior (no data loss, no high-frequency meaningless
  requests);
* idempotency across overlapping windows;
* source isolation (single-source failure does not block others);
* token expiry behavior (observed naturally, not reverse-engineered);
* memory stability;
* database growth;
* request volume.

## 2. Configuration (all environment-driven, never in Git)

```text
CHA_V2_INSPECTION_SCHEDULER_ENABLED=false        # stays false until soak authorization
CHA_V2_INSPECTION_SCHEDULER_PERIOD_SECONDS=3600  # conservative hourly cadence
CHA_V2_INSPECTION_SCHEDULER_OVERLAP_SECONDS=300  # 5-min overlap per window
CHA_V2_INSPECTION_SCHEDULER_WATERMARK_TABLE=inspection_watermark
CHA_V2_INSPECTION_COLLECTOR_DEVICE_BACKOFF_SECONDS=60
CHA_V2_INSPECTION_COLLECTOR_MEDIA_BACKOFF_SECONDS=60
CHA_V2_INSPECTION_COLLECTOR_ALARM_BACKOFF_SECONDS=60
```

Watermark semantics: each run starts at `last_successful_watermark -
overlap`, records `watermark = window_end` only after all sources in that
window complete; a failed source keeps the watermark at the previous value
so the window is retried with overlap (no silent gap).

## 3. Token lifecycle observation

During the soak, only observe whether the AEE token expires inside the test
window. If it expires, record:

* observed lifetime (from first use to `error=333` / 401);
* error behavior (bounded `AEEDataHTTPError`, source marked `status="error"`);
* recovery requirement (manual Secret rotation, then a retry).

Do not invent a refresh API, a browser token-scraping daemon, or long-running
browser automation. A production `Token provisioning / rotation runbook` is
required before any production activation.

## 4. Acceptance for the soak

* N consecutive runs with correct watermark advance and no row inflation;
* a forced single-source failure does not block other sources and the
  watermark does not skip the failed window;
* bounded memory (no unbounded growth in the scheduler process);
* database growth matches the source row volume (no duplicate growth);
* request volume matches the configured cadence (no unexpected bursts);
* token expiry (if any) is observed, logged in a sanitized way and recovered
  via manual rotation.
