# CHA Video Record System Optimization — Active Task Goal

Last updated: `2026-08-28`

## 1. Overall Objective

在不影响既有 CHA / Legacy 业务、保持生产可回滚和证据可追溯的前提下，完成
CHA 视频记录系统的受控现代化。当前工作只允许推进已授权的 M4 数据中心与
Dashboard Canary 硬化；不得把历史计划、聊天记录或旧完成报告当作当前生产事实。

**Source of truth priority:** production read-only evidence → current Git code →
automated verification → dated release/canary evidence → this file → historical
plans.

---

## 2. Current Production Baseline

Read-only observation on **2026-08-28** (no production configuration or service
was changed during this review):

| Item | Observed state |
| --- | --- |
| V2 health / live / ready | HTTP 200 |
| `dashboard_v2` | enabled |
| `inspection_v2` | enabled |
| `realtime_readonly` | enabled |
| `realtime_audio` / `realtime_control` / `account_pool_v2` | disabled |
| `records_v2` | disabled |
| Current readiness PostgreSQL field | reports `not_enabled` in the deployed release; this is a known observability gap, **not** proof that the production data store is absent |
| Realtime rollout scope / allowlist | not inferred from the public feature response; do not change or guess it |

Production deployment is **frozen** for this phase. Scheduler, PostgreSQL,
Legacy and currently enabled Realtime continue under their existing operational
controls. No feature flag, Nginx, systemd, database, secret, current symlink or
AEE configuration may be changed by this task.

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
  secret/address scan also passed. It is **not deployed**.

### COMPLETED / UNVERIFIED

- Historical M3 fullscreen user-activation evidence remains
  `COMPLETED / UNVERIFIED` by the approved M3 waiver.
- Any claim that production already contains this Phase 6 hardening is
  `COMPLETED / UNVERIFIED` until an explicitly authorized Canary deployment
  and browser/API validation occur.

### IN PROGRESS

**ACTIVE MILESTONE: M4**

**ACTIVE PHASE: PHASE 6 — DASHBOARD CONSOLIDATION & CANARY HARDENING**

**STATUS: IN PROGRESS / CLEAN-BRANCH VALIDATION**

Phase 6 is limited to local hardening and evidence preparation:

1. remove the date-dependent Inspection CSV test flake;
2. apply the same CHA-login + AuthorizedUser decision to Dashboard pages/data
   and inspection/workflow routes;
3. reuse bounded PostgreSQL connections, safely return/rollback/discard them,
   and close pools at application shutdown;
4. aggregate independent overview domains concurrently while isolating a
   single domain failure;
5. report the actual inspection PostgreSQL readiness state without making
   unrelated Legacy compatibility unavailable;
6. complete documentation, package, address-redaction and Git-history audits.

### TODO — only after this Phase is explicitly accepted

- An owner-authorized **AuthorizedUser Dashboard Canary deployment** of the
  tested Phase 6 package.
- Post-deployment verification: anonymous 401; non-authorized/disabled 403;
  AuthorizedUser and admin 200; PostgreSQL readiness; Dashboard response time;
  pool connection behavior; legacy/realtime regression.
- Natural operational observation. Do not create artificial hours-long scheduler
  runs or expand product scope while observing.

### BLOCKED

- `M4 CLOSED`, broad user rollout, M5 and Legacy retirement are not authorized.
- An AuthorizedUser Dashboard Canary deployment remains separately authorized
  work. The current clean-branch migration must be fully validated and pushed
  before any deployment decision.

### AEE VERIFICATION REQUIRED

No new AEE/MCS8/media behavior is in Phase 6 scope. Existing AEE/MCS8 unknowns
(code maps, upstream behavior or device compatibility) remain reference-only
and must follow `docs/codex/AEE_REFERENCE_IMPLEMENTATION.md` before any future
media/data adapter change.

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

- deploy or modify production;
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
- overview concurrency and per-domain failure-isolation tests;
- readiness unit/integration tests for ready, misconfigured and unavailable
  inspection PostgreSQL states;
- `git diff --check`, tracked-file secret/address scan, package build and
  package-content verification;
- no accidental business/API contract regression.

---

## 7. Production Safety Requirements

Any later deployment needs an explicit owner authorization and a rollback
baseline. Before/after it must verify service state, restart count, Legacy
health, V2 health/live/ready, feature state, logs, PostgreSQL availability,
AuthorizedUser decisions and Dashboard/API behavior. Canary first; no full
rollout by implication.

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

This Phase is eligible for the following local-only conclusion only when every
item above passes and the security/history audit does not require an owner
intervention:

```text
M4 PHASE 6 CANARY HARDENING PASS
READY FOR AUTHORIZEDUSER DASHBOARD CANARY DEPLOYMENT
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

---

## 11. Next Recommended Actions

1. Complete clean-branch regression, package and security/address checks, then
   push only `codex/m4-clean-phase6-20260828` without deployment.
2. Only after separate owner deployment approval, perform a controlled
   AuthorizedUser Dashboard Canary and record real production evidence.
