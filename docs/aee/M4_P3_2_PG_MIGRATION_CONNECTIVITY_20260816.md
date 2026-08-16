# M4 P3.2 — Production PG Migration & CHA Connectivity Gate

Date: `2026-08-16`

Status: `PRODUCTION PG MIGRATION & CONNECTIVITY PASS / READY FOR INITIAL ONE SHOT`

## A. Pre-migration baseline

`PRE-MIGRATION DATABASE STATE = EMPTY / BASELINE` (cha_m4 had no objects).
Security re-confirmed: listen `127.0.0.1:5432` + `100.117.170.25:5432`;
public `47.251.105.9:5432` CLOSED; pg_hba minimal (app/migrator only from
`100.74.86.85/32` scram, localhost scram, reject `0.0.0.0/0`+`::/0`).
Baseline manifest SHA-256: `7968f15e…` (version/roles/objects, no passwords).

## B/C. Migrations 0001 + 0002

Applied by `cha_m4_migrator` to `cha_m4`/`inspection` (`ON_ERROR_STOP=1`,
search_path `inspection,public`); both `RC=0`, all CREATE TABLE/INDEX +
COMMIT. No error / constraint conflict / permission error.

## D. Schema verification

10 tables: `device_status_events`, `device_location_events`, `media_files`,
`realtime_view_events`, `alarm_events`, `authorized_users`,
`authorized_user_audit_events`, `inspection_records`,
`inspection_record_views`, `inspection_audit_events`; 48 indexes incl.
9 `uq_*` unique indexes; 10 constraints; PKs present.

## E. App role privileges

`cha_m4_app`: `rolsuper=f rolcreatedb=f rolcreaterole=f`; cannot CREATE in
`inspection`; granted `SELECT/INSERT/UPDATE/DELETE` on all tables +
`USAGE,SELECT` on sequences (+ default privileges for future tables). DDL
remains with `cha_m4_migrator`.

## F. CHA SSH / access

CHA SSH resolved (correct account credentials); read-only `postgresql-client`
(psql 16) installed on CHA for the verification (no app/service change).

## G. CHA → PG real connectivity

From CHA host (`cn-edge` `100.74.86.85`) via Tailscale to Aliyun
`100.117.170.25:5432`: TCP OK; authenticated `psql` returned
`PostgreSQL 14.23` / `cha_m4` / `cha_m4_app`. This is the real CHA
production host → real Aliyun production PG path.

## H. Connection latency

`psql` connect + `SELECT 1`: ≈1.85–2.66 s per new connection (~160 ms RTT ×
multiple handshake/SSL/scram round-trips + process startup). Records the
`PostgresInspectionStore` per-method short-connection risk; a connection
pool is a later optimization (no refactor this gate).

## I. Secret injection readiness

CHA protected secret file `/etc/cha-pg-secrets` (0600) holds
`CHA_PG_HOST=100.117.170.25` (Tailscale IP, not public), `PORT/DATABASE/
USER/PASSWORD/SSLMODE=prefer/SCHEMA=inspection`. Production app **not**
restarted.

## J. DML transaction smoke test

From CHA as `cha_m4_app`: `BEGIN → INSERT synthetic authorized_user →
SELECT (seen=1) → ROLLBACK`; residue check = 0. App role read/write PASS.

## K. pg_dump

`cha_m4_after_migration_20260816230618.dump` (custom, 46,590 B),
SHA-256 `bd76d3f02692bfed46b00e6df99258e6aa99e2aef62e429b1ef4b54e0d6449e4`.

## L. Restore verification

Restored into disposable `cha_m4_restore_verify` (`RC=0`, 10 tables/48
indexes), then the disposable DB was dropped. No destructive restore on
production `cha_m4`.

## M. Remote backup status

`REMOTE BACKUP DESTINATION REQUIRED BEFORE CANARY COMPLETION` — remote
destination not yet provided; local short-term dump only.

## N. Resource usage

RAM 1.6 GiB (297 MiB used / 1.1 GiB available), swap 2 GiB (0 used), disk
32 GiB free, PG DB size ≈9.4 MB, PG processes ≈47 MB total. No abnormal
growth; low-concurrency Canary node only.

## O. Security

No credentials/tokens in Git/docs/logs; transport = **Tailscale / WireGuard
encrypted** AND **PostgreSQL SSL enabled** (`ssl=on`); public 5432 closed;
CHA secret file 0600; app not restarted; production current/nginx/systemd
untouched.

## P. Git / production state

`codex/m4-inspection-data-center-20260815`; production app/current/nginx/
systemd unchanged. ONE SHOT / scheduler / AuthorizedUser / Inspection
rollout deferred to the next gate.
