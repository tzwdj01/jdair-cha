# CHA Video Record System Optimization — Active Task Goal

Last updated: `2026-08-31`

## 1. Overall Objective

在不影响既有 CHA / Legacy 业务、保持生产可回滚和证据可追溯的前提下，完成
CHA 视频记录系统的受控现代化。当前工作只允许推进已授权的 M4 数据中心与
Dashboard Canary 硬化；不得把历史计划、聊天记录或旧完成报告当作当前生产事实。

**Source of truth priority:** production read-only evidence → current Git code →
automated verification → dated release/canary evidence → this file → historical
plans.

---

## 2. Current Superseding State

**ACTIVE MILESTONE: M4**

**ACTIVE PHASE: PHASE 6 — DASHBOARD CONSOLIDATION & CANARY HARDENING**

**CURRENT SUBPHASE: OWNER-OBSERVED REFINEMENT — VIDEO INSPECTION WORKSPACE**

Production release `889d0b1` is deployed and usable. It includes the bounded
Video Inspection Workbench visual refinement, the dedicated InspectionRecord
route-order correction, shared-session multi-tile handoff and the minimal
record-correction UI. V2, Legacy, Nginx and the low-rate scheduler are active;
the protected public PostgreSQL TLS path is the accepted production path. The
release's exact package SHA-256 and runtime commit were verified at deployment.
This does not close M4, authorize a full rollout or authorize M5.

The previous AuthorizedUser-management refinement is `COMPLETED / VERIFIED`:
the admin-only page is live and uses the existing AuthorizedUser API without
handling AEE credentials or adding roles. Owner Business Acceptance now found
the next bounded M4 usability gap: Dashboard data pages did not form a clear
daily **video inspection workbench**. The released refinement reuses the
existing M3 realtime viewer and InspectionRecord lifecycle, preserves the
current AuthorizedUser boundary, and introduces no video copy, transcoding or
media infrastructure. Owner business acceptance of record creation/submission
and correction remains a deliberately separate non-destructive step.

All dated recovery and retry records below remain historical evidence. They
must not override this current production state.

---

## 3. Historical Production Baseline (2026-08-30)

Production state on **2026-08-30** before the owner-authorized public
PostgreSQL-path recovery and Phase 6 Candidate Canary retry:

| Item | Observed state |
| --- | --- |
| V2 health / live / ready | prior stable V2 release is again active after rollback; V2 `live` is HTTP 200 |
| Phase 6 V2 candidate | Candidate commit `0d389d8` was packaged, deployed and identity-verified, then rolled back after the authorized Dashboard data request and current V2 PostgreSQL readiness gate failed |
| PostgreSQL client policy | protected V2 and scheduler runtime uses TLS-enforcing `sslmode=require` and `gssencmode=disable` |
| PostgreSQL connection path | prior private-path revalidation was retained as historical evidence; the owner has authorized a separately bounded public TLS path, restricted to the CHA egress `/32`, after the public fresh-connection gate passed |
| Time synchronization | CHA and PostgreSQL nodes retain healthy `chrony`, normal leap status and low observed offsets |
| Inspection PostgreSQL data | retained; the controlled scheduler cycle persisted through the existing native read-only path without duplicate identity groups |
| Candidate readiness PostgreSQL field | HTTP 200 envelope but `status=degraded` / PostgreSQL `status=degraded`; this was a Canary failure, not a successful readiness result |
| M4 scheduler | intentionally stopped after a successful managed cycle for the recovery gate; the journal proves it completed one cycle and then normally waited for its configured next cycle |
| Production PostgreSQL | production data/schema/roles remain intact; any public listener and `hostssl` rule are limited to the authorized CHA egress `/32` and are subject to the fresh-connection revalidation below |
| Legacy / Nginx / Realtime scope | unchanged by this retry; do not infer or alter Realtime allowlists from public feature responses |
| Remote database backup | historical Master Plan records off-host backup PASS; it was not revalidated during this PG-blocked Preflight |

The current operational state is safe but is **not yet** a successful Dashboard
Canary. The prior V2 release remains the rollback baseline; Legacy and Nginx
remain active. The owner has now authorized only a bounded public-path
revalidation, scheduler recovery and, on success, the complete AuthorizedUser
Dashboard Canary. The Candidate must not write production business data, mutate
the PostgreSQL schema or change AEE behavior.

---

## 4. Project Status Classification

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
- **2026-08-30 local data-store timeout containment:** source tracing and a
  deterministic slow-driver regression proved that one cold/blocking
  `psycopg2` `getconn()` call can keep its driver lock while its
  `asyncio.to_thread` caller has already timed out. The local fix puts a
  bounded application gate around driver connection acquisition and bounds
  each Dashboard overview domain, returning the truthful
  `database_busy`/`database_timeout` result rather than indefinitely blocking
  the page. This proves containment of that application-side failure
  amplifier; it does **not** prove why the Candidate's production connection
  was slow. Source and extracted-package suites passed 318 tests (2 source
  isolated-PostgreSQL skips; 10 archive-only skips).
- **2026-08-31 Video Inspection Workspace refinement:** exact package commit
  `889d0b1` was deployed with matching SHA-256 and runtime identity. Source
  validation passed 332 tests with 2 explicit isolated-PostgreSQL skips; the
  extracted production package passed 332 tests with 12 intentional
  archive-only skips. The deployed dedicated InspectionRecord route exposes
  query/filter/CSV/XLSX UI instead of the previously shadowing generic page.
  Browser evidence confirmed the workbench source navigator, same-session
  1-to-2 live tiles, first frames at 1920x1080 with live tracks, a selective
  close with the survivor still playing, explicit workspace close, truthful
  uploaded-media metadata and same-origin inspection-context handoff. See
  `docs/aee/M4_VIDEO_INSPECTION_VISUAL_WORKSPACE_20260831.md`.

### COMPLETED / UNVERIFIED

- Historical M3 fullscreen user-activation evidence remains
  `COMPLETED / UNVERIFIED` by the approved M3 waiver.
- Historical earlier Phase 6 candidates were deployed and rolled back before
  the current runtime. Their PostgreSQL timeout evidence remains historical;
  it does not describe the current `889d0b1` release.
- The workbench correction form is deployed, but no production correction was
  written during technical acceptance. Actual draft creation, submission and
  correction remain for a lawful Owner business-acceptance session.

### IN PROGRESS

**ACTIVE MILESTONE: M4**

**ACTIVE PHASE: PHASE 6 — DASHBOARD CONSOLIDATION & CANARY HARDENING**

**CURRENT SUBPHASE: OWNER-OBSERVED REFINEMENT — VIDEO INSPECTION WORKSPACE**

**STATUS: IN PROGRESS — OWNER BUSINESS ACCEPTANCE OF THE RELEASED REALTIME
INSPECTION WORKFLOW WITHOUT ALTERING MEDIA INFRASTRUCTURE**

Current evidence distinguishes the two source types:

- **Realtime:** existing M3 is a verified Class B MCS8/AEE WebRTC adapter.
  The deployed workbench embeds it and reuses one M3 session for visual
  multi-tile selection. Production browser evidence covered one then two live
  sources, first frames, selective close and explicit workspace close; it does
  not change the evidenced six-stream maximum.
- **Uploaded video:** `media_files` contains safe Class A metadata (source ID,
  device, title, kind, duration and source times), but intentionally persists
  neither storage path nor signed playback URL. CHA has no preview/download
  route. The upstream SignedUrl operation has only static evidence, so browser
  preview is not assumed.

The released workbench preserves the secure shell, safe metadata source list,
realtime context handoff, manual candidate confirmation and InspectionRecord
draft/submit/audit UI. The dedicated InspectionRecord route correction, visual
multi-tile handoff and minimal Owner correction UI are deployed. It does
**not** claim uploaded-video playback until the required AEE comparison is
complete.

### TODO — current Owner-Observed Refinement

1. Owner acceptance: authorized login → realtime view → record context →
   candidate/manual confirmation → save draft / submit → record
   query/statistics/export/audit; test correction only with an intentionally
   created owner-owned record.
2. Keep uploaded-video selection truthful: metadata is usable, but no preview
   button or fake media association may be shipped before AEE evidence.
3. Keep 9/16 layouts disabled until a same-device AEE vs CHA capacity and
   resource-release comparison proves a safe configuration above six streams.

### BLOCKED

- `M4 CLOSED`, broad user rollout, M5 and Legacy retirement are not authorized.
- No historical infrastructure investigation is an active blocker. Stop only
  for new production P0 evidence: failed fresh public TLS connection, wrong
  runtime identity, anonymous exposure, AuthorizedUser regression, PoolError
  cascade, systemic Dashboard failure or Legacy regression.
- Completion of the actual non-AuthorizedUser `403` gate requires a lawful,
  explicitly supplied test identity; do not enumerate AEE/MCS8 users or
  repurpose unrelated accounts.
- **Uploaded-video browser preview and a durable MediaFile ↔ InspectionRecord
  relationship** are `AEE VERIFICATION REQUIRED`; no SignedUrl, object path or
  playback workaround may be guessed or persisted in the meantime.

### AEE VERIFICATION REQUIRED

**Question:** can a lawful CHA server-side adapter request a temporary browser
preview URL for one `RecordFileList.id` without exposing an AEE credential or
persisting a signed URL?

**Required evidence:** same authorized user, same representative video device
and record, same browser/network window. Observe the AEE file preview action,
the request to `/api/v1/oss/SignedUrl?id=...`, response content type and expiry
behaviour, and whether the resulting media is browser-playable. Do not retain
the URL, token, Cookie, object key or storage fields.

**Current result:** this execution environment reached `493 JFE Forbidden`
before an authorized AEE page session could be established. This is not a
reason to bypass JFE/WAF or add a proxy. Re-run only through a lawful,
authorized AEE browser/session and then classify the capability before any
CHA playback work.

**Visual-page evidence update (2026-08-31):** opening AEE `/v3/visual` in the
available browser context redirected to `/v3/login`; no credential was entered.
Static `mcs__p__v3__visual.chunk.js` evidence is recorded in
`docs/aee/M4_AEE_VISUAL_CHA_COMPARISON.md` as `STATIC_EVIDENCE_ONLY`. It shows
a device/file/alarm/map visual dashboard, not a proven WebRTC tile runtime.
CHA continues to reuse the independently verified M3 MCS8/AEE adapter. The
current six-stream ceiling remains in force; any 9/16-stream expansion is
`AEE VERIFICATION REQUIRED` and cannot be inferred from a visual layout.

---

## 5. AEE Reference Evidence Rules

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

## 6. Constraints / Non-goals

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

## 7. Verification Requirements

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

## 8. Production Safety Requirements

Any retry needs explicit owner authorization and a rollback baseline.
Before/after it must verify service state, restart count, Legacy health, V2
health/live/ready, feature state, logs, PostgreSQL availability, time
synchronization, AuthorizedUser decisions and Dashboard/API behavior. Canary
first; no full rollout by implication.

---

## 9. Git / Release Requirements

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

## 10. Done Criteria for This Phase

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

## 11. Evidence / Decision Log

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
| 2026-08-30 | Owner-authorized bounded scratch revalidation used current protected production PostgreSQL configuration with Candidate `a83199a`; it did not switch `current`. Raw fresh `psycopg` `SELECT 1` was only 1/3 successful, with two 10-second `OperationalError` outcomes. Candidate pool acquire/release was 2/3 successful; health check was 3/3 eventually true but 6.3–8.1 seconds; the minimal production read was 3/3 successful but 9.9–16.7 seconds. Candidate deployment and Dashboard Canary were not started. Stable V2/Legacy/Nginx and the actual M4 scheduler service remained active. See `docs/aee/M4_PHASE6_PRODUCTION_DATASTORE_BOUNDED_REVALIDATION_20260830.md`. |
| 2026-08-31 | AEE `/v3/visual` comparison is `STATIC_EVIDENCE_ONLY`: the lawful browser context redirected to login, so only public static page evidence was used. It supports a status-first left/centre/right workspace model, not claims about camera-wall media, playback URLs or capacity. See `docs/aee/M4_AEE_VISUAL_CHA_COMPARISON.md`. |
| 2026-08-31 | Exact package `889d0b1` was deployed as the Video Inspection Workspace visual refinement. Production browser evidence confirmed M3 same-session 1-to-2 live tiles, 1920x1080/live tracks, selective close with a surviving tile, explicit workspace close, inspection-context handoff, honest uploaded-media metadata and the corrected InspectionRecord query/export route. V2, Legacy, Nginx and scheduler remained active with zero restarts. No InspectionRecord was written in technical acceptance. See `docs/aee/M4_VIDEO_INSPECTION_VISUAL_WORKSPACE_20260831.md`. |

---

## 12. Next Recommended Actions

1. Run Owner business acceptance of the deployed workbench using a deliberate
   test record: realtime view → context → manual candidate confirmation →
   draft/submit → query/export/audit; test correction only against that record.
2. Preserve the low-rate scheduler under natural production observation; do
   not manufacture a long polling run.
3. Run the lawful AEE SignedUrl preview evidence comparison before proposing
   any uploaded-video playback or durable file-to-record association.
4. Keep standalone Issue workflow, automatic matching, M4 closure, full
   rollout and M5 out of scope until separately authorized.
