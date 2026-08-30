# M4 Phase 6 — Production Data-store Bounded Revalidation

**Date:** `2026-08-30`
**Status:** `FAIL — RAW_CONNECTION_SLOW / CANDIDATE NOT DEPLOYED`
**Scope:** owner-authorized, read-only scratch validation of the latest clean
Candidate against the protected production PostgreSQL configuration.

## Safety boundary

The validation used a temporary isolated source tree on the CHA production
host. It did not switch V2 `current`, restart a service, modify the PostgreSQL
schema/data, change protected environment files, or call AEE/MCS8.

The scratch tree and copied Candidate package were removed after the run.
Before and after the run:

| Check | Result |
| --- | --- |
| V2 current release | unchanged |
| V2 service / live endpoint | active / HTTP 200 |
| Legacy service | active |
| Nginx | active |
| M4 scheduler (`jdair-cha-m4-scheduler.service`) | active / running |

## Candidate identity

| Item | Value |
| --- | --- |
| Candidate Git commit | `a83199acb6b4e2287e6d91d2cb12957de2494074` |
| Local package SHA-256 | `96722d6e32117ee1f6306329f1056ce74a7e743331075cd5f817ecce2cba9e13` |
| Remote package checksum | matched the local package |
| Extracted `COMMIT` | matched the Candidate Git commit |

No secret, password, token, Cookie, header, address or database connection
identifier is recorded here.

## Read-only three-attempt matrix

Each layer ran at most three times using the Candidate code, its production
venv, and the protected runtime PostgreSQL configuration. All database actions
were `SELECT` only.

| Layer | Attempts | Result | Sanitized latency evidence |
| --- | --- | --- | --- |
| Raw `psycopg` fresh connection + `SELECT 1` | 3 | **1/3 PASS** | attempts 1–2: `OperationalError` at 10,000.66 ms and 10,001.65 ms; attempt 3: connect 4,782.58 ms, query 4,452.54 ms, total 9,235.37 ms, TLS active |
| Candidate `PostgresConnectionPool` acquire/release | 3 | **2/3 PASS** | attempt 1: `OperationalError` at 10,001.22 ms; attempts 2–3: acquire 7,906.56 / 6,585.71 ms, query 585.88 / 3,130.47 ms, release 449.84 / 1,032.43 ms |
| Candidate `PostgresInspectionStore.health_check()` | 3 | **3/3 eventually true** | total 8,123.24 / 6,399.46 / 6,331.83 ms |
| Candidate minimal `device_status_events` read | 3 | **3/3 PASS** | acquire 7,304.98 / 9,577.56 / 5,282.89 ms; query 2,710.32 / 5,093.60 / 3,084.63 ms; total 10,612.82 / 16,668.95 / 9,861.83 ms |

## Classification and decision

```text
NO — BLOCKED AT RAW_CONNECTION_SLOW
```

The first required layer was not stable: two of three fresh Candidate-equivalent
connections timed out at the 10-second configured connection bound. The pool
failure is a downstream consequence of the same cold connection behavior, not
evidence of a new pool-design defect. The later health and read layers
eventually completed, but their measured durations are incompatible with the
Candidate's bounded readiness and per-domain Dashboard availability budgets.

Under the owner-approved failure policy:

* the Candidate was **not** deployed;
* the AuthorizedUser Dashboard Canary was **not** started;
* no rollback was needed because `current` never changed;
* no code, PostgreSQL, network, AEE/MCS8, media, Redis/PgBouncer or other
  infrastructure change was made.

## What this evidence does and does not prove

It proves the exact current deployment blocker is unstable fresh PostgreSQL
connection performance in the protected production configuration.

It does **not** prove whether the root cause is PostgreSQL-node load, a private
network/TLS path, host scheduling, a transient external condition, or another
upstream factor. It must not be attributed to AEE, MCS8, realtime media,
Tailnet configuration or a PostgreSQL driver defect without new evidence.

Any next action requires a new owner-approved, bounded plan focused solely on
`RAW_CONNECTION_SLOW`. Do not repeat the Candidate deployment or the complete
Dashboard Canary until that gate is resolved.
