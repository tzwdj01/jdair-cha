# M4 Phase 6 — PostgreSQL Recovery and Dashboard Canary Retry

Date: `2026-08-29`

Status: `CANARY FAIL / V2 CANDIDATE ROLLED BACK`

This is a dated continuation record for the Phase 6 retry. It does not alter
the historical evidence in
`M4_PHASE6_AUTHORIZEDUSER_DASHBOARD_CANARY_20260828.md`.

## 1. Scope and Safety Boundary

The owner authorized only:

1. PostgreSQL client-connection recovery and time-synchronization validation;
2. a single native MCS8 scheduler-cycle recovery test, followed by managed
   low-rate scheduler startup;
3. a controlled AuthorizedUser Dashboard Canary.

No PostgreSQL schema migration, destructive data operation, Nginx change,
firewall change, public database exposure, AEE secret change, new media
infrastructure, or product-scope expansion was performed.

The candidate was rolled back immediately when the Dashboard performance and
pool-health gate failed. No AuthorizedUser management mutation or Inspection
workflow write was performed during this retry.

## 2. PostgreSQL Connection Recovery — PASS

Both production nodes were read-only audited for time synchronization:

* the active time-synchronization implementation was `chrony`;
* NTP synchronization was healthy on both nodes;
* UTC/local time and timezone were coherent;
* measured offsets were small (sub-millisecond to low-millisecond scale);
* no manual time change was made.

The protected runtime configuration for both the V2 application and the MCS8
scheduler was updated as authorized:

```text
CHA_PG_SSLMODE=require
PGGSSENCMODE=disable
```

The private-network route remained unchanged. Repeated service-equivalent
fresh `SELECT 1` probes for the V2 and scheduler contexts completed
successfully, and PostgreSQL read-only `pg_stat_ssl` evidence confirmed TLS
was active. No password, Token, Cookie, DSN, or address is recorded here.

## 3. Candidate Deployment and Minimal Read — PASS

The guarded release helper was first corrected so package tests run in an
isolated test environment rather than inheriting protected runtime variables.
Source tests, extracted-package tests, local rehearsal, and a
production-environment-equivalent isolated rehearsal passed.

The Phase 6 candidate was then deployed through the guarded release path:

* V2 process active;
* `live` and `ready` initially returned HTTP 200;
* readiness truthfully reported the inspection PostgreSQL dependency as ready;
* an authenticated enabled-inspector browser session successfully read
  `/api/v2/inspection/devices`;
* the returned payload identified the configured inspection store and reported
  real coverage metadata.

Anonymous access to protected inspection data had already returned HTTP 401 in
this retry context. No anonymous data exposure was observed.

## 4. Scheduler Recovery and Operationalization — PASS

Before starting the managed service:

* the kill switch was invoked through an environment-only override;
* the scheduler exited successfully with the expected disabled marker;
* no collection was performed by that disabled invocation.

One controlled native MCS8 scheduler cycle then completed successfully:

```text
DEVICE -> MEDIA -> ALARM -> PostgreSQL
```

Observed behavior:

* MCS8 server-side authentication/read succeeded;
* all three collection sources reported `ok`;
* no PostgreSQL timeout, login failure, or persistence failure marker appeared;
* a real status transition was recorded when present;
* unchanged device state produced no new status event;
* the `initial_snapshot` count did not increase;
* media identity behavior remained idempotent; only a new unique identity
  increased the durable total.

The formal systemd scheduler was then started:

* service state: active/running;
* no immediate restart loop;
* fresh restart count: zero;
* first managed cycle completed successfully;
* device source stored zero rows for unchanged state, while the media source
  completed without duplicate inflation;
* scheduler memory remained small and bounded during the short verification.

The scheduler remains a low-rate, sequential, read-only MCS8 collector. It is
not a browser-token or AEE-web-page integration.

## 5. Dashboard Canary Failure — CONFIRMED

The Canary stopped at the Dashboard performance/pool-health gate.

Using the authorized inspector browser session, a bounded production Dashboard
API probe was started for the approved overview and domain endpoints. The
probe did not complete within approximately 105 seconds and was safely
cancelled. Candidate V2 evidence then showed:

* an inspection realtime request returned HTTP 500;
* V2 logged `psycopg2.pool.PoolError: connection pool exhausted`;
* a local candidate `ready` request subsequently timed out during the same
  incident window.

This is a real Candidate failure, not a browser-only observation. It blocks
the remaining AuthorizedUser access matrix, Dashboard performance comparison,
and PostgreSQL -> API -> Dashboard reconciliation gates.

### Code Evidence for the Follow-up Fix

Static inspection of the rolled-back candidate shows a credible mechanism that
must be reproduced and fixed in a dedicated follow-up:

* `ProductionOverviewService.build()` starts seven domain aggregations with
  `asyncio.gather`;
* the data store has a bounded four-connection pool;
* the pool acquires with the non-waiting psycopg2 `getconn()` call.

This is recorded as a **root-cause candidate**, not as a final causal claim.
The next fix must add a production-like regression test and prove bounded,
graceful behavior under concurrent overview/domain reads. It must not simply
increase pool limits or introduce PgBouncer, Redis, a proxy, or other new
infrastructure without new owner authorization.

## 6. Rollback — PASS

Per the approved failure strategy, the Phase 6 V2 candidate was immediately
rolled back to the prepared prior V2 release.

The first rollback wrapper invocation switched the V2 release target and
restarted the service, but its immediate health probe ran before the process
had bound its listener and therefore returned connection-refused. This is an
operational wrapper timing defect, not evidence of a failed rollback.

After normal application startup:

* the prior V2 release was active;
* V2 `live` returned HTTP 200;
* V2 `ready` returned HTTP 200;
* V2 restart count was zero;
* Legacy/Nginx were not modified;
* the scheduler remained active with restart count zero;
* PostgreSQL production data was retained.

The rollback wrapper needs a bounded startup-wait/readiness retry in a future,
separately tested release-tooling change.

## 7. Durable Data and Resources

After the controlled scheduler work and rollback:

* DeviceStatusEvent, DeviceLocationEvent, MediaFile, AlarmEvent,
  RealtimeViewEvent, and InspectionRecord rows remained present;
* the database remained small and connections remained low;
* CHA and PostgreSQL node memory/swap/disk baselines were acceptable for the
  low-rate operational state;
* no production database restore, truncation, or rollback was performed.

The off-host PostgreSQL backup destination remains unresolved. Local database
dumps must not be treated as the sole production backup. This is still:

```text
REMOTE BACKUP DESTINATION REQUIRED
```

## 8. Current Decision

```text
PRODUCTION PG CONNECTION RECOVERY: PASS
PRODUCTION TIME SYNCHRONIZATION: PASS
LOW-RATE SCHEDULER OPERATIONALIZATION: PASS
AUTHORIZEDUSER DASHBOARD PRODUCTION CANARY: FAIL / V2 ROLLED BACK
M4 PHASE 6: BLOCKED — CANDIDATE CONNECTION-POOL EXHAUSTION
```

## 9. Required Next Gate

Do not retry the candidate until the owner authorizes a narrow Phase 6
pool/concurrency and rollback-wrapper fix. That follow-up must:

1. reproduce the production-like concurrent overview/domain workload against
   PostgreSQL;
2. prove no pool exhaustion, leaked connection, readiness stall, or request
   hang;
3. preserve a bounded connection footprint and private TLS-only PostgreSQL
   transport;
4. add a bounded startup wait to the rollback verification path;
5. pass local and isolated PostgreSQL tests before another production Canary;
6. use a lawful ordinary logged-in but non-AuthorizedUser test identity for
   the required real HTTP 403 gate; do not enumerate or repurpose arbitrary
   production identities;
7. re-run the complete access, performance, reconciliation, and M2
   compatibility matrix.

No M4 closure, M5 work, full-user rollout, Dashboard redesign, media feature,
or infrastructure escalation is authorized by this record.
