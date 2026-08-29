# CHA Video Record System Optimization — Active Task Goal

Last updated: `2026-08-30`

## 1. Overall Objective

在不影响既有 CHA / Legacy 业务、保持生产可回滚和证据可追溯的前提下，完成
CHA 视频记录系统的受控现代化。当前工作只允许推进已授权的 M4 数据中心与
Dashboard Canary 硬化；不得把历史计划、聊天记录或旧完成报告当作当前生产事实。

**Source of truth priority:** production read-only evidence → current Git code →
automated verification → dated release/canary evidence → this file → historical
plans.

---

## 2. Current Production Baseline

Production Preflight observation on **2026-08-30** before the newly authorized
Phase 6 AuthorizedUser Dashboard Canary Retry:

| Item | Observed state |
| --- | --- |
| V2 health / live / ready | prior stable V2 release active; live and ready HTTP 200 |
| Phase 6 V2 candidate | not rebuilt or deployed in this retry; the prior pool-failure candidate remains rolled back |
| PostgreSQL client policy | protected V2 and scheduler runtime uses TLS-enforcing `sslmode=require` and `gssencmode=disable` |
| Time synchronization | CHA node `chrony` is active with normal, low observed offsets; PostgreSQL-node current recheck was not reached after the connection stop gate |
| Inspection PostgreSQL data | no mutation was made; current CHA application-equivalent fresh connection Preflight failed `0/3` |
| Current stable V2 readiness PostgreSQL field | `not_enabled`; this is expected for the rolled-back stable release and is not proof that PostgreSQL data is absent |
| M4 scheduler | safely stopped after a recent private PostgreSQL timeout/restart and the current `0/3` connection failure; no additional cycle was forced |
| Production PostgreSQL | not modified; current reachability from the protected CHA runtime is blocked by fresh connection failures |
| Legacy / Nginx / Realtime scope | unchanged by this retry; do not infer or alter Realtime allowlists from public feature responses |
| Remote database backup | historical Master Plan records off-host backup PASS; it was not revalidated during this PG-blocked Preflight |

The current operational state is safe but is **not** a successful Dashboard
Canary. The prior V2 release, Legacy and Nginx remain active; the low-rate
scheduler is deliberately stopped until private PostgreSQL connectivity is
restored. Do not modify further protected production
configuration, systemd, database, secret, current-symlink, firewall, or AEE
settings without a new explicit owner authorization.

---

## 3. Project Status Classification

Use only these labels: `COMPLETED / VERIFIED`, `COMPLETED / UNVERIFIED`,
`IN PROGRESS`, `TODO`, `BLOCKED`, `AEE VERIFICATION REQUIRED`.

### COMPLETED / VERIFIED

- M0 baseline/security governance, M1 engineering foundation and M2 situation
  dashboard: historical release evidence exists.
- M3 realtime first release: closed with the separately documented fullscreen
  evidence waiver; it is not being expanded in M4.
- M4 P0/P1/P2/P2.5/P3/P3.1/P3.2: historical data contracts, PostgreSQL
  rehearsal, controlled production data path, backup evidence, scheduler,
  AuthorizedUser/InspectionRecord model and initial dashboard/data wiring have
  dated evidence in `docs/aee/` and the Master Plan.
- Current local Phase 6 implementation has a shared AuthorizedUser boundary,
  bounded PostgreSQL pool, concurrent overview aggregation and readiness model.
  On 2026-08-28, the full local suite passed **301 tests** with **2 explicit
  isolated-PostgreSQL skips**; package content and the current tracked-file
  secret/address scan also passed.
- The guarded release helper correctly fail-stopped before a first `current`
  switch when a source-only test was unavailable in the production archive.
  The artifact test was repaired, then both source and extracted-package suites
  passed with no failures. The release helper and independent rollback wrapper
  were exercised during the controlled attempt.
- Production time synchronization and the approved PostgreSQL client policy
  were verified on both nodes. Repeated service-equivalent fresh connections
  passed with PostgreSQL TLS active.
- The Phase 6 candidate passed V2 live/ready and an enabled-inspector,
  production-PG-backed device-read gate before the later pool failure.
- Anonymous access to an Inspection data API returned `401`; no anonymous data
  exposure was observed. An enabled inspector received `200`.
- The scheduler kill switch was proven through an environment-only disabled
  invocation. A manual one-cycle and the first systemd-managed cycle both
  completed DEVICE -> MEDIA -> ALARM with no timeout/restart loop. Unchanged
  device state did not create new `initial_snapshot` rows.
- **M4 Phase 6B local hardening:** production evidence and source tracing
  confirmed an application-side capacity bug: seven overview domains were
  launched together against a four-connection data pool whose psycopg2
  `getconn()` call is non-waiting. A simultaneous direct inspection read and
  readiness probe could then receive a raw pool-exhaustion failure. The driver
  pool is already `ThreadedConnectionPool`, not `SimpleConnectionPool`; the
  defect was unbounded aggregation and missing application-level exhaustion
  handling, not a thread-unsafe driver pool.
- Phase 6B adds a process-scoped, bounded pool lease; a process-shared
  two-domain overview limit that reserves two of the four data connections for
  direct reads/readiness; fast `database_busy` degradation; bounded readiness;
  release runtime identity; and a bounded rollback live-health retry. See
  `docs/aee/M4_PHASE6B_POOL_CONCURRENCY_HARDENING_20260829.md`.
- Phase 6B local validation passed: `315` source tests passed with `2`
  explicit isolated-PostgreSQL skips and `0` failures; Python compile checks,
  the Node realtime-runtime regression, a disposable rollback rehearsal, and
  source release-tooling checks all passed. The final M4 package is built only
  from a clean committed source tree so its runtime commit marker cannot
  misidentify a dirty artifact.

### COMPLETED / UNVERIFIED

- Historical M3 fullscreen user-activation evidence remains
  `COMPLETED / UNVERIFIED` by the approved M3 waiver.
- The Phase 6 code was deployed for the controlled retry but rolled back after
  a real candidate failure. Any claim that it is active in production is false
  until a future successful retry.
- Real authenticated-but-not-AuthorizedUser `403`, disabled-user `403`, and
  admin `200` have not been completed in this retry. Do not simulate these
  outcomes with arbitrary production identities.
- Full Dashboard API cold/warm performance, candidate pool recovery behavior,
  PostgreSQL -> API -> Dashboard reconciliation, and M2 compatibility were
  not accepted. The browser probe exposed the blocking pool failure first.

### IN PROGRESS

**ACTIVE MILESTONE: M4**

**ACTIVE PHASE: PHASE 6 — DASHBOARD CONSOLIDATION & CANARY HARDENING**

**CURRENT SUBPHASE: AUTHORIZEDUSER DASHBOARD PRODUCTION CANARY RETRY —
PREFLIGHT**

**STATUS: BLOCKED — PRODUCTION PG CONNECTION STILL UNSTABLE**

Phase 6B remains `COMPLETED / VERIFIED` locally. The owner authorized the
separate Canary Retry on 2026-08-30, but its mandatory Preflight found that
three protected CHA application-equivalent PostgreSQL connection attempts all
failed with `OperationalError`. A recent scheduler process had also failed on
the same private path and restarted once. Per the approved failure policy, the
scheduler was safely stopped and no Candidate was built or deployed.

### TODO — after the production PostgreSQL connection gate is restored

1. Restore and demonstrate stable protected CHA → PostgreSQL connectivity using
   the existing private/TLS-only architecture. Recheck current PostgreSQL-node
   time synchronization before any Candidate deployment; do not introduce a
   new proxy, public port or speculative infrastructure workaround.
2. Re-run three application-equivalent fresh connections with TLS active. Only
   after `3/3` pass may the scheduler recovery gate run: one controlled cycle,
   then managed scheduler start with no restart/persistence loop.
3. Rebuild the Candidate from the clean remote-tracked Phase 6B commit and
   confirm `RUNNING_RELEASE`, `RUNNING_COMMIT` and `PACKAGE_HASH` before
   browser/API validation.
4. Obtain a lawful ordinary authenticated-but-not-AuthorizedUser test identity
   for the real `403` production gate. The enabled inspector may only be
   temporarily disabled if a future owner authorization explicitly accepts that
   reversible test mutation.
5. Re-run the complete AuthorizedUser Dashboard Canary: anonymous `401`,
   ordinary/disabled `403`, enabled inspector/admin `200`, pool behavior,
   Dashboard cold/warm response time, PG -> API -> Dashboard reconciliation,
   and M2/Legacy regression.

### BLOCKED

- `M4 CLOSED`, broad user rollout, M5 and Legacy retirement are not authorized.
- **PRODUCTION PG CONNECTION STILL UNSTABLE:** the 2026-08-30 protected
  application-equivalent Preflight was `0/3`; do not deploy the Candidate or
  restart the scheduler until the private PostgreSQL connection gate passes.
- Completion of the actual non-AuthorizedUser `403` gate requires a lawful,
  explicitly supplied test identity; do not enumerate AEE/MCS8 users or
  repurpose unrelated accounts.

### AEE VERIFICATION REQUIRED

No new AEE/MCS8/media protocol behavior is in this Phase 6 remediation scope.
The running scheduler continues to use the already verified native MCS8
read-only path. Any future AEE/MCS8/media behavior change remains
`AEE VERIFICATION REQUIRED` and must follow
`docs/codex/AEE_REFERENCE_IMPLEMENTATION.md` before implementation.

---

## 4. AEE Reference Evidence Rules

For AEE, MCS8, realtime video, WebRTC, WebSocket media sessions, RTP, codec,
stream profile, SDK behavior or device compatibility work:

1. read `docs/codex/AEE_REFERENCE_IMPLEMENTATION.md` first;
2. reproduce CHA and AEE on the same device/scenario when behavior differs;
3. record AEE vs CHA evidence before changing CHA;
4. classify the capability as Class A/B/C/D;
5. prefer an existing adapter/capability over a workaround;
6. do not introduce FFmpeg, a media server, SFU, custom decoder, transcoding
   pipeline or complex proxy without Architecture Escalation Evidence.

If legal AEE access is unavailable, mark the item `AEE VERIFICATION REQUIRED`;
do not invent upstream behavior.

---

## 5. Constraints / Non-goals

This Phase must not:

- retry the Dashboard Canary or modify protected production environment,
  systemd, Nginx, PostgreSQL, firewall, or AEE settings without explicit owner
  approval;
- introduce a second authentication system or complex RBAC;
- add business KPIs, visual-dashboard redesign, new scheduler domains,
  automatic Flight/Routine matching, PTZ, Talkback, recording, 32 streams,
  FFmpeg/SFU/transcoding or media infrastructure;
- expose passwords, tokens, session IDs, cookies, authorization headers,
  database connection strings or production addresses in Git, docs, tests,
  package artifacts or logs;
- modify historical evidence to make it look like current approval.

---

## 6. Verification Requirements

Phase 6 local acceptance requires:

- full project unittest discovery with **0 failures** (explicit skips may only
  be isolated PostgreSQL rehearsal tests with no injected rehearsal DB);
- access tests for anonymous, ordinary logged-in, disabled AuthorizedUser,
  enabled inspector and admin paths across Dashboard/data/workflow routes;
- pool reuse, `putconn`, rollback, broken-connection discard and `closeall`
  tests;
- a production-shape concurrent regression test covering overview + direct
  inspection read + readiness against one small bounded pool, followed by a
  recovery read proving no retained lease;
- overview concurrency and per-domain failure-isolation tests, including
  truthful `database_busy` degradation;
- readiness unit/integration tests for ready, degraded, misconfigured and
  unavailable inspection PostgreSQL states;
- source and extracted-package verification that the runtime exposes
  non-secret `RUNNING_RELEASE`, `RUNNING_COMMIT` and `PACKAGE_HASH`;
- a disposable rollback rehearsal proving an initial listener-not-bound health
  result retries within a bounded window and succeeds only after V2 is active
  and `live` returns HTTP 200;
- `git diff --check`, tracked-file secret/address scan, package build and
  package-content verification;
- no accidental business/API contract regression.

---

## 7. Production Safety Requirements

Any retry needs explicit owner authorization and a rollback baseline.
Before/after it must verify service state, restart count, Legacy health, V2
health/live/ready, feature state, logs, PostgreSQL availability, time
synchronization, AuthorizedUser decisions and Dashboard/API behavior. Canary
first; no full rollout by implication.

---

## 8. Git / Release Requirements

- Work only on the active branch; do not overwrite unrelated edits.
- Keep secrets, cookies, tokens, backups, archives and production environment
  files outside Git.
- Run an address/sensitive-string audit for both tracked files and unpushed
  history before push.
- The original M4 local development branch and verified external bundle are
  retained for recovery. Publish only the clean branch; do not force-push,
  filter-repo or publish the historical development branch.
- No production release/tag/merge is implied by a local Phase 6 commit.

---

## 9. Done Criteria for This Phase

The PostgreSQL connection-policy and time-synchronization gate is complete.
Phase 6B is locally complete only when the production pool failure has a
documented cause; the pool is thread-safe and process-scoped; overview
concurrency is bounded; exhaustion degrades rather than cascades; readiness
returns promptly and honestly; lifecycle, release identity and rollback retry
rehearsals pass; and the clean branch is packaged/pushed.

Even after Phase 6B passes, **Phase 6 itself remains pending** a separately
authorized production Dashboard Canary Retry. It is eligible for the following
broader conclusion only when every relevant Canary acceptance item passes:

```text
M4 PHASE 6 CANARY HARDENING PASS
DASHBOARD CANARY READY FOR OWNER BUSINESS ACCEPTANCE
```

It does **not** mean M4 Closed, a production deployment, a full-user rollout or
permission to start M5.

---

## 10. Evidence / Decision Log

| Date | Evidence / decision |
| --- | --- |
| 2026-08-18 | `docs/aee/M4_COMPLETION_REPORT_20260818.md` records historical delivery evidence only. It is not current M4 closure approval. |
| 2026-08-26 | Owner authorized Phase 6 local hardening and required a Dashboard Canary NO-GO until security, access, pool, readiness and package gates pass. |
| 2026-08-28 | Read-only production feature/health observation recorded the current feature state above. No deployment or configuration change was made. |
| 2026-08-28 | Local Phase 6 full validation: 301 tests passed, 2 isolated PostgreSQL rehearsal tests skipped, package content passed, current tracked-file secret/address scan passed. Production remains unchanged. |
| 2026-08-28 | Unpushed-history audit: 48 commits ahead of the remote contain 25 non-documentation address hits. High-confidence key/Bearer/credential-URL scan found no hits. History sanitation requires owner approval; no rewrite, commit or push may proceed. |
| 2026-08-28 | Owner authorized a clean-branch squash migration. The historical local branch and external recovery bundles were retained; the clean branch was rebuilt from the verified remote base with final-tree reconciliation and approved sanitization. |
| 2026-08-28 | Phase 6 candidate deployment attempted from the clean branch. The first run stopped before `current` changed because the production archive omitted source-only release-tooling scripts required by one test. The test was made artifact-aware, source and extracted-package tests passed, and the guarded deployment then completed. |
| 2026-08-28 | Authenticated Dashboard/Inspection validation failed before the access/data gates: new PostgreSQL connections with the current `sslmode=prefer` timed out. The prior V2 release was restored with the prepared rollback wrapper. The scheduler exhibited the same timeout/restart loop and was safely stopped. See `docs/aee/M4_PHASE6_AUTHORIZEDUSER_DASHBOARD_CANARY_20260828.md`. |
| 2026-08-28 | Read-only connection evidence: private TCP and PostgreSQL TLS handshake were reachable; `sslmode=require` and `sslmode=prefer` with GSS encryption disabled completed `SELECT 1`, while current `sslmode=prefer` timed out. Both production nodes reported unsynchronized NTP and server-local date drift requiring owner review. |
| 2026-08-29 | Authorized recovery completed: both nodes' existing chrony time synchronization was healthy; protected V2/scheduler policy was set to `sslmode=require` plus `gssencmode=disable`; repeated service-equivalent TLS connections passed; minimal authorized inspection read passed; scheduler kill switch, controlled one-cycle, and managed service startup passed. |
| 2026-08-29 | The Phase 6 Dashboard probe then exposed a real candidate `psycopg2.pool.PoolError: connection pool exhausted`, an HTTP 500 on an inspection endpoint, and a readiness timeout. The candidate was rolled back; the prior V2 release is healthy and the low-rate scheduler remains active. See `docs/aee/M4_PHASE6_PG_RECOVERY_CANARY_20260829.md`. |
| 2026-08-29 | Owner authorized Phase 6B local-only hardening. Source tracing confirmed `ThreadedConnectionPool` (not `SimpleConnectionPool`), one process-scoped four-connection data pool, a separate two-connection workflow pool, seven unbounded overview domains, non-waiting `getconn()`, and concurrent direct/readiness demand as the incident mechanism. No production deployment or state change is part of Phase 6B. |
| 2026-08-30 | Owner authorized the Phase 6 AuthorizedUser Dashboard Canary Retry. Read-only Preflight confirmed the stable V2/Legacy/Nginx baseline, TLS-only PostgreSQL runtime policy and healthy CHA `chrony`; however, three protected application-equivalent PostgreSQL fresh connections failed with `OperationalError`. A recent scheduler timeout had already caused one systemd restart. The scheduler was safely stopped to prevent recurrence. No Candidate package/build/deployment, PostgreSQL mutation, network change or Dashboard/access test occurred. See `docs/aee/M4_PHASE6_CANARY_RETRY_PREFLIGHT_BLOCK_20260830.md`. |

---

## 11. Next Recommended Actions

1. Restore and prove the existing private PostgreSQL connection path stable,
   then recover the low-rate scheduler with the documented one-cycle gate.
2. Re-run the already authorized AuthorizedUser Dashboard Canary from the clean
   Phase 6B baseline only after the PostgreSQL Preflight passes.
3. Obtain a lawful ordinary non-AuthorizedUser test account for the required
   real `403` access-control evidence.
