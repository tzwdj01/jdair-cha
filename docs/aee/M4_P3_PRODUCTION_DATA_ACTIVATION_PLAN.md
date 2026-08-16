# M4 P3 — Production Data Activation Plan (PROPOSAL / NOT EXECUTED)

Status: `PROPOSAL — NOT AUTHORIZED / NOT EXECUTED`.

This document prepares the production data activation path. Nothing here is
executed without a separate explicit owner authorization. The current WSL
PostgreSQL is development/rehearsal only and must never become the CHA
long-term production database.

## 1. Production PostgreSQL placement

Options in preference order:

1. Cloud-managed PostgreSQL (managed backups, TLS, no server maintenance);
2. An approved server PostgreSQL with the operator's DBA support;
3. Not the WSL rehearsal instance; not video files in PostgreSQL.

Resource estimate (initial, to be confirmed against real volume):

* rows: device_status ~1.9k/3-day window, media ~805/3-day window (will grow
  with history accumulation), alarms, inspection records;
* storage: metadata only (no media payload) — start with a few GB, monitor
  growth;
* compute: a small instance (2 vCPU / 4 GB is a reasonable starting point);
* version: PostgreSQL >= 14 (match rehearsal 14.23 or the platform default).

## 2. Database / schema / roles

* `database`: `cha_m4` (non-production naming only during staging);
* `schema`: `inspection` (event history + inspection workflow);
* roles: `cha_m4_app` (DML) and `cha_m4_migrator` (DDL for migration runs);
* no reuse of production AEE accounts or credentials; no AEE password/token
  stored in the database.

## 3. Secret injection

* All credentials (PG password, AEE token) via environment variables or a
  protected secret manager; never in Git, docs, logs or the browser.
* Template (names only):
  `CHA_PG_HOST`, `CHA_PG_PORT`, `CHA_PG_DATABASE`, `CHA_PG_USER`,
  `CHA_PG_PASSWORD`, `CHA_PG_SSLMODE`, `CHA_AEE_TOKEN_PROVIDER`.

## 4. Backup

* `pg_dump` custom format daily + `WAL` (or managed-platform backups);
* backup location off-host; retention: 14 daily + 4 weekly + monthly (proposal);
* restore rehearsal at least once per quarter; record SHA-256 of dumps.

## 5. Migration procedure

1. New forward-only versioned migration (e.g. `0003_*.sql`);
2. migration test on the rehearsal PG (migration + unique/index/constraint
   review + repository test + backup/restore compatibility);
3. backup before every production migration;
4. apply via `cha_m4_migrator` with `ON_ERROR_STOP`; verify schema; then app.

## 6. Rollback procedure

Forward-only migrations; rollback = restore the pre-change backup
(`pg_restore`) + deploy the previous application release. No fake DOWN
migration.

## 7. AEE token provisioning / rotation

* Token is injected server-side only (`CHA_AEE_TOKEN_PROVIDER`);
* manual rotation: replace the secret, then re-run collection;
* token failure behavior: fail-closed, source marked `status="error"`,
  bounded retry, no infinite retry;
* production Canary naturally observes real token lifetime; do not
  reverse-engineer a refresh API or scrape browser tokens.

## 8. Scheduler cadence (proposal, low-rate first)

* period: `3600 s` initially; overlap: `300 s`; watermark table records the
  last fully-successful window;
* source-level backoff (e.g. `60 s`) per failing source;
* health monitoring: per-run report (source status / error / completeness /
  watermark), DB growth, request volume;
* no production scheduler is enabled in this phase.

## 9. Token risk

* `TOKEN-ONLY API: VERIFIED` (2026-08-16 live: token header without Cookie
  returns data);
* `LONG-LIVED SERVER TOKEN LIFECYCLE: NOT YET LIVE-SOAK VERIFIED`;
* plan supports Secret replacement, fail-closed and manual rotation;
* controlled production Canary will collect real lifecycle evidence naturally.

## 10. Gate

`READY FOR CONTROLLED PRODUCTION DATA ACTIVATION` is only reported when:
PG placement approved, secrets injected safely, migration+backup+rollback
rehearsed on staging, low-rate soak evidence collected, and a production
Canary window authorized. Until then the answer is `NOT AUTHORIZED`.
