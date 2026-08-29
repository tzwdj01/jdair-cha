# M4 Phase 6B — PostgreSQL Pool / Dashboard Concurrency Hardening

Date: `2026-08-29`
Status: `PHASE 6B PASS / READY FOR AUTHORIZEDUSER DASHBOARD CANARY RETRY`

## 1. Scope and Safety Boundary

This is the narrow follow-up to the real Phase 6 Dashboard Canary incident
recorded in `M4_PHASE6_PG_RECOVERY_CANARY_20260829.md`.

Allowed work:

1. trace and reproduce the application-side pool exhaustion mechanism;
2. correct bounded pool/concurrency behavior locally;
3. add local regression, release-identity and rollback-wait coverage;
4. build a clean, traceable release artifact.

Not performed:

* no V2 Candidate deployment;
* no V2/Legacy/Nginx/scheduler restart;
* no production PostgreSQL change;
* no production data mutation;
* no AEE/MCS8 protocol change;
* no new database or media infrastructure.

The production runtime remains on the prior stable V2 release. The low-rate
native MCS8 scheduler remains independently active under its existing
systemd control.

## 2. Read-only Production Safety Confirmation

The current production baseline was re-confirmed read-only on `2026-08-29`:

* stable V2 `current` target and the V2 process working directory resolve to
  the same prior stable release;
* V2 `live` and `ready` returned HTTP 200;
* Legacy and Nginx were active with zero observed restart count;
* the low-rate scheduler was active with restart count zero;
* its latest observed cycle completed `DEVICE -> MEDIA -> ALARM` with all
  sources reporting success;
* PostgreSQL service/readiness was healthy and the durable inspection data
  path remained available.

No command in Phase 6B changed that state.

## 3. Confirmed Root Cause

The real Candidate evidence was:

```text
GET /api/v2/inspection/realtime -> HTTP 500
psycopg2.pool.PoolError: connection pool exhausted
```

It occurred during a bounded AuthorizedUser Dashboard probe while a
`/api/v2/health/ready` check subsequently stalled.

Source tracing and the new production-shape regression establish the
application-side mechanism:

1. `PostgresInspectionStore` owns one process-scoped, thread-safe
   `psycopg2.pool.ThreadedConnectionPool` with `minconn=1`, `maxconn=4`.
   It is **not** `SimpleConnectionPool`.
2. `PostgresInspectionRecordStore` owns a separate process-scoped
   `ThreadedConnectionPool` with `minconn=1`, `maxconn=2`.
3. Both stores are constructed once in `app.main` and closed by the FastAPI
   lifespan; they are not built per request.
4. `ProductionOverviewService.build()` previously started seven domains with
   one unbounded `asyncio.gather(...)`. Six of those domains can issue
   inspection-data reads; the seventh uses the workflow store.
5. psycopg2 `getconn()` is non-waiting when the pool is exhausted. A direct
   inspection request and readiness data-store health check competing with
   the overview could therefore receive a raw driver `PoolError`.

The P0 was therefore:

> unbounded application-side overview aggregation plus a non-waiting
> four-connection data pool, with no bounded admission or graceful
> exhaustion behavior.

It was not evidence that PostgreSQL capacity, network transport, AEE/MCS8,
or driver thread safety required new infrastructure.

## 4. Implemented Fix

### 4.1 Bounded process-scoped pool lease

`PostgresConnectionPool` now:

* continues to use `ThreadedConnectionPool`;
* owns a `threading.BoundedSemaphore` equal to `maxconn`;
* waits at most `0.5` seconds for a lease;
* normalizes driver pool exhaustion to `PostgresPoolExhaustedError` with
  stable client-safe code `database_busy`;
* releases every lease after success, query exception, rollback/commit
  failure, driver error and broken-connection discard;
* fails closed after lifespan shutdown instead of lazily recreating a new
  pool.

The data pool remains `maxconn=4`; the workflow pool remains `maxconn=2`.
No pool-size increase was used as a workaround.

### 4.2 Bounded overview aggregation

`ProductionOverviewService` is created once per V2 process and now shares an
`asyncio.Semaphore(2)` across all overview requests. At most two overview
domains can query at once. This preserves parallelism while reserving two
data-pool connections for direct inspection reads and readiness.

If one domain cannot obtain a connection, it reports:

```json
{"available": false, "error": "database_busy"}
```

Other domains remain independent and the overview returns PARTIAL/degraded
truthfully rather than cascading to a full failure.

### 4.3 Safe exhaustion/readiness behavior

* A direct inspection/workflow route that receives
  `PostgresPoolExhaustedError` returns a client-safe HTTP 503
  `database_busy`, never the raw psycopg2 exception or a generic HTTP 500.
* `inspection_postgresql_readiness()` checks both store health paths with a
  bounded per-check timeout (default `1.0` second).
* Capacity contention or timeout reports `postgresql.status=degraded`.
  A hard health failure remains `unavailable`.
* Legacy-compatible readiness behavior remains HTTP 200 when the Legacy core
  is healthy; its payload is honest that only the M4 inspection dependency is
  degraded.

### 4.4 Runtime identity and rollback timing

The M4 package now includes a generated non-secret `COMMIT` marker and the
packaged rollback helper. The deployment helper writes its detached
`PACKAGE_SHA256` marker into the extracted release directory.

`GET /api/v2/system/version` now exposes:

* `running_release`;
* `running_commit`;
* `package_hash`.

These values come from the actual imported release directory, not merely the
mutable `current` symlink. On Linux, systemd starts from the `current`
working directory but the running process's package path resolves to the real
release directory; this explains the earlier symlink-versus-runtime
observation.

`ops/rollback-v2.sh` now supports a bounded live-health retry after a managed
restart. It succeeds only after:

```text
systemd service active
AND
/api/v2/health/live = HTTP 200
```

The old inline generated rollback wrapper delegates to that helper. The
rehearsal deliberately returns one transient `000`/connection-not-ready
result, then HTTP 200, proving retry rather than a fixed long sleep.

The M4 package builder refuses a dirty source tree. This prevents an artifact
from claiming a Git commit that does not actually contain its code.

## 5. Regression Evidence

Local source validation:

```text
python -m compileall -q app tests                 PASS
python -m unittest discover -s tests -v           PASS
315 tests, 2 explicit isolated-PostgreSQL skips, 0 failures
node tests/realtime_runtime_test.cjs              PASS
```

Added/extended coverage verifies:

* thread-safe driver-pool selection, bounded acquisition and recovery;
* pool reuse across store calls, `closeall`, no post-shutdown re-create;
* success, rollback and broken-connection discard;
* driver `PoolError` normalization without a leaked permit;
* two-domain overview concurrency limit;
* per-domain `database_busy` isolation;
* concurrent **overview + direct read + readiness** against one
  four-connection fake pool, followed by a recovery read;
* bounded readiness `degraded` response for pool busy/timeout;
* HTTP 503 safe response instead of raw pool error;
* non-secret runtime identity endpoint fields;
* rollout tooling source checks;
* actual disposable rollback rehearsal:

```text
M4_PHASE6_ROLLBACK_REHEARSAL=passed
```

The release package is intentionally built only after the final source commit
so its `COMMIT` marker is exact. Package-content verification confirmed:

* `COMMIT` present;
* `ops/rollback-v2.sh` present;
* no tracked production `.env`/secret material;
* extracted package test suite passes.

## 6. Architecture Decision

No architecture escalation is justified.

Rejected for this P0:

* PostgreSQL server resize;
* PgBouncer;
* Redis;
* database proxy;
* queue/Celery/Kafka;
* FFmpeg/SFU/media changes;
* AEE/MCS8 workaround.

The incident is fully addressed at the existing application pool and
aggregation layer. This is unrelated to AEE media capability; no additional
`AEE vs CHA` evidence is required for this code fix.

## 7. Remaining Production Gate

After source/package/security/Git validation, the correct next status is:

```text
PHASE 6B POOL/CONCURRENCY HARDENING: PASS
READY FOR: AUTHORIZEDUSER DASHBOARD CANARY RETRY
```

That is **not** authorization to deploy. A new owner-approved Canary must
still validate:

1. expected runtime identity before browser/API tests;
2. anonymous `401`;
3. lawful ordinary/disabled `403`;
4. enabled inspector/admin `200`;
5. Dashboard cold/warm response and no pool cascade;
6. PostgreSQL -> API -> Dashboard reconciliation;
7. M2/Legacy compatibility.

`REMOTE BACKUP DESTINATION REQUIRED` also remains open and prevents declaring
M4 or P3.2 Canary complete.
