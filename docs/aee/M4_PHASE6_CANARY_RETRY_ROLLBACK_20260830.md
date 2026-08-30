# M4 Phase 6 — AuthorizedUser Dashboard Canary Retry

**Date:** `2026-08-30`  
**Status:** `BLOCKED / ROLLED BACK`  
**Scope:** controlled V2 Candidate deployment and AuthorizedUser Dashboard
Canary only.

## Result

The clean Candidate was built from committed source and deployed successfully,
but the authorized Dashboard data path did not meet the Canary availability
gate. The generated rollback helper restored the prior V2 release immediately.

This is **not** an M4 completion, a user rollout, an AEE/MCS8 result or a media
architecture decision.

## Candidate evidence

| Item | Result |
| --- | --- |
| Candidate commit | `0d389d8b879ebef7b9e4a5072809d17c08ee47e3` |
| Candidate package SHA-256 | `99e3bec7a3951adab03b70cb2b6bd8a3cb1624d5e15493a876c713b97372f446` |
| Source tests | PASS — 316 tests, 2 isolated rehearsal skips |
| Extracted package tests | PASS — 316 tests, 10 intentional archive-only skips |
| Release identity | PASS — `RUNNING_RELEASE`, `RUNNING_COMMIT` and package hash matched the Candidate |
| V2 / Legacy startup checks | PASS — active, direct/proxied health HTTP 200 |
| Feature contract | PASS — Dashboard, Inspection and read-only realtime enabled; audio, control, account pool and records remained disabled |
| Anonymous Dashboard page/API | PASS — both returned the expected `401` AuthorizedUser envelope; no data exposure observed |

The first deployment attempt exposed a release-helper assertion that assumed
the unauthenticated M2 Dashboard route always returned HTML. That assumption
is invalid when the Inspection feature deliberately applies the AuthorizedUser
boundary. The assertion was corrected, covered by a release-tooling test,
retested, committed and packaged before the successful Candidate deployment.

## Authorized-user observation

A lawfully supplied, enabled CHA test user successfully signed in and opened
the Inspection Dashboard shell. The page then requested:

```text
GET /api/v2/dashboard/production-overview?days=7
```

The request did not complete within a bounded browser probe (about eight
seconds) and was cancelled by the probe. Therefore no Dashboard data,
performance, reconciliation or workflow conclusion was accepted.

## Current Candidate failure evidence

| Observation | Result |
| --- | --- |
| Candidate `/api/v2/health/ready` HTTP | 200 envelope |
| Candidate readiness status | `degraded` |
| Candidate readiness PostgreSQL dependency | `degraded` |
| Protected one-shot `PostgresInspectionStore.health_check()` | `TimeoutError` |
| Protected one-shot workflow-store health check | PASS |
| V2 service restart count during observation | `0` |
| Scheduler after rollback | active, `NRestarts=0` |

The already-passed private PostgreSQL listener recovery is not reopened by
this evidence. The direct cause of the **data-store** health timeout remains
unproven. It must not be attributed to AEE, MCS8, Tailnet routing, media
protocol behavior or a PostgreSQL driver defect without further evidence.

## Containment and rollback

The generated Candidate rollback helper completed successfully:

```text
ROLLBACK_HEALTH_ATTEMPT=3
ROLLBACK_LIVE_HTTP=200
ROLLBACK=passed
```

After rollback:

* `current` again pointed to the prior V2 release;
* V2 was active and `/api/v2/health/live` returned HTTP 200;
* the scheduler stayed active with `NRestarts=0`;
* production PostgreSQL data, schema and AEE configuration were not modified
  by this Candidate attempt.

## Not accepted in this retry

The following gates remain unverified and must not be inferred:

* authenticated-but-not-AuthorizedUser `403`;
* disabled AuthorizedUser `403`;
* admin `200`;
* Dashboard cold/warm response time;
* pool recovery under an authorized production request;
* PostgreSQL → API → Dashboard reconciliation;
* M2 compatibility after an accepted Candidate.

## Next gate

`OWNER AUTHORIZATION REQUIRED — DATA-STORE POSTGRESQL ROOT-CAUSE PLAN`

Prefer an isolated/rehearsal reproduction. Do not repeat the production
Candidate, modify the already-recovered private listener, change AEE behavior,
or introduce a media/server/workaround architecture without a separate,
evidence-led authorization.
