# M4 Phase 6 — Data-store PostgreSQL Timeout Containment

**Date:** `2026-08-30`
**Status:** `LOCAL CONTAINMENT PASS / PRODUCTION REVALIDATION NOT AUTHORIZED`
**Scope:** bounded local diagnosis and regression hardening after the rolled-back
AuthorizedUser Dashboard Candidate. No production action was performed.

## Boundary

The Phase 6 Candidate remains rolled back. This record does **not** reopen the
already-passed private PostgreSQL listener recovery gate, authorize a new
Candidate deployment, or attribute the failure to AEE, MCS8, media, Tailnet or
PostgreSQL itself.

The Candidate evidence remains:

* its AuthorizedUser production-overview request did not complete within the
  bounded browser probe;
* readiness was `degraded` because `PostgresInspectionStore.health_check()`
  timed out;
* the separate workflow-store health check passed;
* rollback restored the prior V2 release successfully.

See `M4_PHASE6_CANARY_RETRY_ROLLBACK_20260830.md` for the production record.

## Established local mechanism

Source tracing established the following application-side failure amplifier:

1. `PostgresInspectionStore` runs synchronous PostgreSQL work through
   `asyncio.to_thread`.
2. A Python timeout of the awaiting coroutine does not stop an already-running
   driver thread.
3. `psycopg2.ThreadedConnectionPool.getconn()` serializes its driver
   connection-acquisition path, including a cold TCP/TLS connect attempt.
4. A slow acquisition can therefore continue after a readiness/overview caller
   reports timeout; later callers can stack behind the driver lock.

This mechanism is a **local application containment finding**. It does not
identify why the production connection acquisition was slow at the time of the
Candidate observation.

## Implemented containment

Commit `368c181670e9b9fb4fd92413a43d3e86153cda7f` adds only the following:

* `PostgresConnectionPool` has a bounded gate around driver `getconn()`.
  The gate covers connection acquisition only; normal query execution still
  uses the configured PostgreSQL pool concurrency. A concurrent acquisition
  returns the existing safe `database_busy` path instead of waiting
  unboundedly behind the driver lock.
* `ProductionOverviewService` applies a bounded timeout to each Dashboard
  domain. A timeout returns the explicit, truthful
  `{ "available": false, "error": "database_timeout" }` result, allowing the
  rest of the overview to render.
* Regression tests model a blocking driver acquisition and a slow Dashboard
  domain. They prove fast bounded failure, recovery after the blocker releases,
  and unaffected fast domains.

No AEE call path, token, browser state, media architecture, database schema,
production setting or production service changed.

## Local verification

| Check | Result |
| --- | --- |
| `tests.test_production_overview` | PASS — 7 tests |
| Full source unittest discovery | PASS — 318 tests, 2 explicit isolated-PostgreSQL skips |
| Python compile check | PASS |
| `git diff --check` before commit | PASS |
| Diff sensitive-value scan | PASS |
| Clean candidate package | PASS — COMMIT marker matched `368c181…` |
| Extracted candidate suite | PASS — 318 tests, 10 intentional archive-only skips |

Package SHA-256 produced locally:
`5d0ee1e1d95b6afae5959f78f3d7e96eadd7d6605265b16124b6e66eabd0e175`

The package was built and verified locally only. It was not deployed.

## Remaining unknowns and next gate

`AEE VERIFICATION REQUIRED` does not apply to this data-store failure: no AEE,
MCS8 or media behavior changed or needs to be inferred.

The remaining unknown is the real production cause of the one slow
data-store connection/read. It can only be investigated under a new owner
authorization with a bounded, protected production revalidation plan. That
plan should measure:

* data-store connection and read duration;
* readiness and overview timeout/busy outcomes;
* cold and warm AuthorizedUser Dashboard latency;
* pool recovery after a bounded failure;
* PostgreSQL → API → Dashboard reconciliation;
* rollback criteria and immediate containment.

Until that authorization is given:

* do not redeploy the Candidate;
* do not repeat the full Dashboard Canary;
* do not alter the recovered private listener;
* do not change AEE/MCS8/media behavior;
* do not introduce FFmpeg, a media server, an SFU, a proxy workaround or other
  architecture escalation.
