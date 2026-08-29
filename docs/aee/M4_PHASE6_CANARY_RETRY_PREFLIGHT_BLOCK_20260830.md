# M4 Phase 6 — AuthorizedUser Dashboard Canary Retry Preflight

Date: `2026-08-30`

Status: `BLOCKED — PRODUCTION PG CONNECTION STILL UNSTABLE`

## 1. Scope

The owner authorized a controlled retry of the Phase 6 AuthorizedUser
Dashboard Canary from the clean Phase 6B baseline. This record covers the
mandatory production Preflight only.

No Candidate package was rebuilt or deployed. No PostgreSQL schema/data,
protected environment, network/firewall, Nginx, AEE/MCS8 behavior or
Dashboard business code was changed.

## 2. Current Stable Baseline

Read-only checks confirmed:

* the prior stable V2 release remained active and its service working
  directory still resolved through the stable `current` target;
* V2 `live` and `ready` returned HTTP 200;
* Legacy and Nginx were active;
* the stable V2 readiness payload reported inspection PostgreSQL
  `not_enabled`, which is expected while the Phase 6 Candidate is not active;
* V2 and scheduler protected runtime configuration both retained
  `sslmode=require` and `gssencmode=disable`;
* the CHA node's existing `chrony` service was active with normal leap status
  and low observed clock offsets.

No credential, token, address, DSN, Cookie or connection identifier is
recorded in this document.

## 3. Stop-Gate Evidence

The required CHA application-equivalent PostgreSQL fresh-connection check ran
three read-only `SELECT 1` attempts with the protected runtime configuration.

Result:

```text
PG fresh connection: 0/3 PASS
Failure class: psycopg2 OperationalError
```

The current scheduler journal also showed a recent PostgreSQL private-path
connection timeout, followed by one systemd restart. The restarted process had
not established a new verified persistence cycle before this Preflight.

This is not a repeat of the completed Phase 6B pool/concurrency defect. The
Candidate was not running, so this evidence concerns the existing
CHA-to-PostgreSQL private connection path rather than Dashboard aggregation.

## 4. Safety Action

Under the approved failure policy, the low-rate scheduler was safely stopped
to avoid another persistence failure at the next cadence:

```text
scheduler: inactive / dead
scheduler process: absent
V2 live: HTTP 200
Legacy: active
Nginx: active
```

No production data was deleted, restored or otherwise changed.

## 5. Decision

```text
PG CONNECTION STILL UNSTABLE
AUTHORIZEDUSER DASHBOARD PRODUCTION CANARY: NOT DEPLOYED
M4 PHASE 6: BLOCKED
```

Do not:

* deploy the Candidate;
* restart the scheduler;
* retry Dashboard/AuthorizedUser access checks;
* widen the PostgreSQL pool;
* open PostgreSQL publicly;
* introduce PgBouncer, Redis, a proxy or other new infrastructure.

## 6. Required Recovery Gate

Before the authorized Canary Retry can resume:

1. restore stable connectivity over the existing private, TLS-only PostgreSQL
   path;
2. recheck current PostgreSQL-node time synchronization using its existing
   synchronization mechanism;
3. prove three fresh protected runtime-equivalent connections succeed, with
   TLS active;
4. run one controlled scheduler cycle and verify
   `DEVICE -> MEDIA -> ALARM -> LOCATION -> PostgreSQL` persistence,
   idempotency and no restart loop;
5. start the scheduler under systemd and confirm it remains active;
6. then rebuild and deploy only the clean Phase 6B Candidate, verify runtime
   identity, and resume the full AuthorizedUser Dashboard Canary matrix.

The eventual Canary must still obtain a lawful ordinary authenticated but
non-AuthorizedUser identity for the real production `403` gate.
