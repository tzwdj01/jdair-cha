# M4 P2.5 — PostgreSQL Rehearsal (BLOCKED / Environment Required)

Status: `EXECUTED 2026-08-16 / PASS` (isolated WSL Ubuntu 22.04, PostgreSQL
14.23, disposable `cha_m4_rehearsal` DB + `inspection_rehearsal` schema).

Owner authorization: project owner authorized a fully isolated, deletable,
NON-PRODUCTION PostgreSQL rehearsal inside the development machine's WSL
Ubuntu. No production database was connected, no production host/current/
Nginx/systemd was touched, no production credential was used, and no
database password was written to Git, TASK_GOAL.md, docs, tests or logs
(password lives only in `/root/.pgpass` 0600 inside WSL).

## 1. Environment probe (2026-08-16)

On the current development machine:

* `psql` / `pg_dump` / `pg_restore` / `initdb` / `pg_ctl` / `createdb` /
  `pg_isready` — **not found**;
* `docker` / `podman` — **not found**;
* nothing listening on TCP 5432; no `PG*` env vars or `DATABASE_URL`;
* Python PostgreSQL drivers (`psycopg2`, `psycopg`, `asyncpg`, `sqlalchemy`,
  `pg8000`) — **not installed**;
* WSL Ubuntu (v2) exists but has no PostgreSQL binaries installed.

Installing PostgreSQL would require root/admin (e.g. `sudo apt install
postgresql` in WSL). Per project instruction, that is **not** self-installed
without authorization. Rehearsal is therefore **BLOCKED** until a safe
isolated runtime is provided.

## 2. Minimal required environment

Provide ONE of the following (non-production, isolated, disposable, no
production data):

1. A reachable non-production / staging PostgreSQL instance:
   * PostgreSQL >= 14, compatible with the planned production version;
   * an independent database and schema namespace (created for the rehearsal,
     deletable afterwards);
   * a dedicated role with rights to `CREATE TABLE`, `CREATE INDEX`, DDL for
     that schema, and to run `pg_dump` / `pg_restore`;
   * `psql`, `pg_dump`, `pg_restore` binaries available to the rehearsal
     runner (either on the host or via the same client toolchain);
   * connection settings injected only through environment variables
     (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` or a
     `CHA_V2_PG_DSN`), never in Git.
2. Or: explicit authorization to install PostgreSQL inside the existing WSL
   Ubuntu (a disposable, non-production runtime), then follow the same
   procedure.

Never: connect to the production database; modify production PostgreSQL;
install system software on a production host; use SQLite as a PostgreSQL
stand-in.

## 3. Rehearsal procedure (to run once the environment exists)

1. **Empty DB → migration**: apply `migrations/0001_inspection_history.sql`;
   inspect resulting schema, indexes and constraints
   (`\d device_status_events`, `\d media_files`, `\d realtime_view_events`,
   `\d alarm_events`, `\d device_location_events`, plus the unique/index
   definitions).
2. **Live/sanitized one-shot ingest**: ingest the sanitized live window
   (DevOnlineList 1857 / RecordFileList 805 / AlarmList 46) through the
   normalizer into the PG repository; reconcile source / normalized / stored
   counts and quality flags.
3. **Idempotency**: re-ingest the same window; assert stored row counts do
   not grow.
4. **Queries**: device + time-range, media device + time-range, alarm device
   + time-range, daily aggregation (`date_trunc('day', occurred_at AT TIME
   ZONE 'Asia/Shanghai')`), and RealtimeViewEvent queries; verify the same
   result sets as the memory/live reconciliation.
5. **Backup / restore**: `pg_dump` the rehearsal DB → record SHA-256 → empty
   / destroy the target → `pg_restore` → compare row counts and key metrics
   for all four tables.
6. **Rollback model**: `0001` is forward-only (no fake DOWN migration).
   Rollback = restore the pre-change backup (via `pg_restore`) + deploy the
   previous application release. Rehearse this path explicitly.
7. **Coverage semantics**: confirm the query layer still computes
   `requested_window_days` / `available_coverage_days` / `FULL | PARTIAL |
   EMPTY` from real distinct business-local days with data — a 30-day request
   with 3 days of history must stay `PARTIAL`, never auto-`FULL` just because
   the table has rows.

## 3.1 Executed results (2026-08-16)

* Environment: WSL Ubuntu 22.04.5 LTS, PostgreSQL `14.23` (official Ubuntu
  repo), tools `psql`/`pg_dump`/`pg_restore` `14.23` verified; `SELECT
  version()` OK; CREATE/INSERT/SELECT/INDEX/CONSTRAINT/TRANSACTION probed
  OK → `POSTGRESQL REHEARSAL ENVIRONMENT READY`.
* Migration `0001` applied to `inspection_rehearsal`; schema/index/constraint
  inspection confirmed all 5 tables + `uq_*` unique indexes + `ix_*` range
  indexes.
* ONE SHOT ingest via `PostgresInspectionStore` + existing `InspectionIngestor`
  (normalizer unchanged):
  `device_status 1857/1857`, `media_files 805/805`, `alarms 46/46`,
  `realtime_view_events 1/1` (source = PG stored), report `completed=True`.
* Second same-window ingest: stored counts identical → **no growth /
  idempotency PASS**.
* Metrics reconciliation (memory vs PG, service layer that powers the
  Dashboard API): `device_overview`, `media_overview`, `realtime_overview`,
  `alarm_overview` all identical, including `HistoricalCoverage` → **no
  metric drift PASS**.
* PG-backed Dashboard API: `/api/v2/inspection/{devices,media,realtime,
  alarms,data-quality}` all 200 with `store_configured=true`; coverage
  semantics correct (devices/media/alarms FULL 4/4, realtime PARTIAL 1/4 for
  the seeded window) → **PASS**.
* Backup/restore: `pg_dump -Fc` → SHA-256 → disposable target
  `cha_m4_rehearsal_restore` → `pg_restore` → row reconciliation
  (1857/0/805/1/46 identical) and metric reconciliation identical → **PASS**.
* Rollback (forward-only model: fresh migration state → restore backup):
  rows and metrics identical to reference; measured RTO ≈ 0.9 s for this
  dataset → **PASS**.
* Non-production LOW-RATE scheduler soak: 3 overlapping runs against PG with
  an injected device-status source failure on run 2 — no row growth, source
  isolation (media/alarms still persisted, no loss), recovery on run 3,
  bounded request volume → **PASS**.

Failure points encountered and fixed during rehearsal (recorded for
repeatability):

1. `ON CONFLICT ON CONSTRAINT <name>` is not valid for unique **indexes**
   created via `CREATE UNIQUE INDEX`; switched to column-inference
   `ON CONFLICT (…)` matching each `uq_*` index.
2. `pg_restore` hung because `PGHOST` was unset (libpq fell back to the Unix
   socket) and because the `.pgpass` only matched database
   `cha_m4_rehearsal` (not the restore target) → libpq prompted for a
   password on the TTY. Fixed by setting `PGHOST=127.0.0.1` and exporting
   `PGPASSWORD` from the WSL-local `.pgpass` (never printed).

## 4. RealtimeViewEvent persistence

During the rehearsal, verify a realtime session
(open → first frame → close) produces exactly one `RealtimeViewEvent` and
that a sink write failure never fails the realtime session (covered by
`tests/test_store_sinks.py` and `tests/test_realtime_view_events.py`). The
event must contain only username/user_id/device_id/session_id/stream_id/times/
durations/result/error_code — never Token, Cookie, Gateway or Media
credentials.

## 5. Blocker

`POSTGRESQL_REHEARSAL_BLOCKED` until a safe isolated PostgreSQL environment
is provided. This blocks only the PostgreSQL PASS; it does not block the
identity/dedup audit, coverage semantics, Dashboard validation or scheduler
soak design work.
