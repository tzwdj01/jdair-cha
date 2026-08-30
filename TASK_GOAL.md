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

Production state on **2026-08-30** after the authorized Phase 6 Candidate
retry was contained by rollback:

| Item | Observed state |
| --- | --- |
| V2 health / live / ready | prior stable V2 release is again active after rollback; V2 `live` is HTTP 200 |
| Phase 6 V2 candidate | Candidate commit `0d389d8` was packaged, deployed and identity-verified, then rolled back after the authorized Dashboard data request and current V2 PostgreSQL readiness gate failed |
| PostgreSQL client policy | protected V2 and scheduler runtime uses TLS-enforcing `sslmode=require` and `gssencmode=disable` |
| Private PostgreSQL path | recovered: three fresh CHA application-equivalent connections completed `SELECT 1`; TLS was active on every validated connection |
| Time synchronization | CHA and PostgreSQL nodes retain healthy `chrony`, normal leap status and low observed offsets |
| Inspection PostgreSQL data | retained; the controlled scheduler cycle persisted through the existing native read-only path without duplicate identity groups |
| Candidate readiness PostgreSQL field | HTTP 200 envelope but `status=degraded` / PostgreSQL `status=degraded`; this was a Canary failure, not a successful readiness result |
| M4 scheduler | recovered and active under its existing systemd service; one controlled cycle passed before managed start, with no immediate PostgreSQL error or restart |
| Production PostgreSQL | existing private listener restored through minimal cluster-to-Tailnet startup ordering; no public listener, data, schema or HBA change |
| Legacy / Nginx / Realtime scope | unchanged by this retry; do not infer or alter Realtime allowlists from public feature responses |
| Remote database backup | historical Master Plan records off-host backup PASS; it was not revalidated during this PG-blocked Preflight |

The current operational state is safe but is **not** a successful Dashboard
Canary. The prior V2 release was restored by its generated rollback helper;
Legacy remains active and the low-rate scheduler remains active through
systemd with `NRestarts=0` after rollback. The Candidate did not write
production business data, mutate the PostgreSQL schema or change AEE behavior.
Do not retry the Candidate or make another protected production change until
the new data-store PostgreSQL health failure has a documented cause and a
separate owner gate authorizes the next action.

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
  The current source suite passed **316 tests** with **2 explicit
  isolated-PostgreSQL skips**; the exact extracted Candidate package also
  passed **316 tests** with **10 intentional archive-only skips**. Package
  content and the tracked-file sensitive-string scan passed.
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
- **Phase 6 private PostgreSQL recovery:** the first failing layer was a
  loopback-only PostgreSQL listener caused by missing Tailnet service ordering
  at cluster startup. The authorized minimal dependency drop-in restored the
  existing private listener. Three protected, service-equivalent fresh
  `SELECT 1` connections passed with TLS active; a single controlled scheduler
  cycle was idempotent; and the existing systemd scheduler was recovered
  active without immediate restart or PostgreSQL error. See
  `docs/aee/M4_PHASE6_PRIVATE_PG_CONNECTIVITY_RECOVERY_20260830.md`.
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
- **2026-08-30 release safety corrections:** Candidate features preserve
  read-only realtime while enabling the intended Inspection Canary; the
  deployment helper now accepts the Inspection feature line and validates
  feature state dynamically. Its anonymous Dashboard assertion correctly
  expects the AuthorizedUser `401` envelope when Inspection is enabled.
- The Candidate release helper completed package validation, V2/Legacy
  start-up checks, Nginx syntax/reload checks and runtime identity checks for
  commit `0d389d8`. Anonymous Dashboard page/API checks correctly returned
  `401`; no anonymous Inspection data was exposed.

### COMPLETED / UNVERIFIED

- Historical M3 fullscreen user-activation evidence remains
  `COMPLETED / UNVERIFIED` by the approved M3 waiver.
- The Phase 6 Candidate was deployed for the controlled retry and then rolled
  back. A lawfully supplied enabled test user could open the authorized
  Dashboard shell, but its production-overview data request did not complete
  within a bounded browser probe. Candidate V2 readiness reported PostgreSQL
  `degraded`; a protected one-shot `PostgresInspectionStore` health check
  timed out while the separate workflow-store health check passed. Any claim
  that the Candidate is active or accepted in production is false.
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
CANDIDATE ROLLED BACK / DATA-STORE POSTGRESQL ROOT CAUSE REQUIRED**

**STATUS: BLOCKED — DO NOT RETRY THE CANDIDATE**

The private-listener recovery remains `COMPLETED / VERIFIED` and is not being
reopened. The separately authorized Candidate retry proved a new, narrower
application-facing failure: the candidate's PostgreSQL **data-store** health
path timed out and prevented the authorized production-overview request from
finishing, although the workflow-store health check passed. The Candidate was
immediately rolled back. This is not evidence of an AEE/MCS8/media defect and
does not authorize a new media architecture or a further production retry.

### TODO — after root-cause authorization

1. Form a bounded, evidence-led root-cause plan for the Candidate
   `PostgresInspectionStore` timeout. Prefer isolated/rehearsal reproduction;
   do not repeat the production Candidate or reopen the already-passed private
   listener gate without a new explicit owner authorization.
2. After the data-store health path is demonstrated healthy, obtain a lawful
   ordinary authenticated-but-not-AuthorizedUser test identity
   for the real `403` production gate. The enabled inspector may only be
   temporarily disabled if a future owner authorization explicitly accepts that
   reversible test mutation.
3. Only after a new production gate, re-run the complete AuthorizedUser
   Dashboard Canary: anonymous `401`,
   ordinary/disabled `403`, enabled inspector/admin `200`, pool behavior,
   Dashboard cold/warm response time, PG -> API -> Dashboard reconciliation,
   and M2/Legacy regression.

### BLOCKED

- `M4 CLOSED`, broad user rollout, M5 and Legacy retirement are not authorized.
- The Phase 6 retry is blocked by the observed Candidate
  `PostgresInspectionStore` health timeout / degraded readiness. The direct
  cause is not yet proven; do not guess that the already-recovered Tailnet
  listener, AEE, MCS8 or a media protocol is responsible.
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

This recovery-complete Phase must not:

- deploy the Candidate, retry the Dashboard Canary, alter the protected
  production environment, systemd, Nginx, PostgreSQL, firewall or AEE settings
  without a new explicit owner instruction for that next gate;
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
| 2026-08-30 | Authorized private PostgreSQL recovery found a cluster startup-order defect: PostgreSQL had the correct existing private listener configuration but started before its Tailnet address was ready and listened only on loopback. A minimal service dependency drop-in restored the private listener. Three fresh protected TLS connections passed; `chrony` remained healthy on both nodes; the existing controlled scheduler cycle passed without duplicate identities; and the systemd scheduler was recovered active with no immediate PostgreSQL failure or restart. See `docs/aee/M4_PHASE6_PRIVATE_PG_CONNECTIVITY_RECOVERY_20260830.md`. |
| 2026-08-30 | Authorized Phase 6 Candidate retry: source and extracted-package tests passed, Candidate `0d389d8` deployed with verified runtime identity and correct anonymous `401` boundary. A lawful enabled test user loaded the Dashboard shell, but `/api/v2/dashboard/production-overview` did not finish within the bounded browser probe; Candidate readiness reported PostgreSQL `degraded`, and a protected `PostgresInspectionStore` health check timed out while the workflow-store check passed. The generated rollback helper restored the prior V2 release; scheduler remained active with `NRestarts=0`. See `docs/aee/M4_PHASE6_CANARY_RETRY_ROLLBACK_20260830.md`. |

---

## 11. Next Recommended Actions

1. Preserve the low-rate scheduler under natural production observation; do
   not manufacture a long polling run.
2. Do not redeploy the Candidate. Seek a separate owner authorization for a
   bounded root-cause investigation of the data-store PostgreSQL timeout,
   preferably in an isolated rehearsal environment.
3. After that gate is resolved, obtain a lawful ordinary non-AuthorizedUser
   test account for the required real `403` access-control evidence.
