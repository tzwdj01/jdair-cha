# M4 Governance Correction — 2026-08-26

> Recorded locally on 2026-08-28. The effective governance decision remains
> 2026-08-26; this document corrects the current execution state without
> rewriting historical evidence.

## Current Authority

```text
ACTIVE MILESTONE: M4
ACTIVE PHASE: PHASE 6 — DASHBOARD CONSOLIDATION & CANARY HARDENING
STATUS: IN PROGRESS / DASHBOARD CANARY NO-GO
M4 CLOSURE: NOT APPROVED / NOT ALLOWED
```

Phase 6 is **not** an authorization to deploy, enable users, expand scheduler
scope, redesign the dashboard, add product features or start M5.

## Correction to Historical Documents

`docs/aee/M4_COMPLETION_REPORT_20260818.md` remains preserved as dated
historical delivery evidence. Its historical wording must **not** be used as a
current `M4 CLOSED` approval. The current authoritative state is this document,
`TASK_GOAL.md`, and the corrected current-status section in
`docs/M4_MASTER_EXECUTION_PLAN.md`.

## Phase 6 Canary-Hardening Gate

Before an owner-approved AuthorizedUser Dashboard Canary, local code must prove:

1. date-independent inspection export tests and a zero-failure full suite;
2. one CHA-login + AuthorizedUser access decision for Dashboard pages/data and
   inspection/workflow APIs: anonymous 401, ordinary/disabled 403, enabled
   inspector/admin 200;
3. a small bounded PostgreSQL connection pool with reuse, rollback, broken
   connection discard and shutdown closeall behavior;
4. concurrent independent production-overview aggregation with isolated,
   honest domain failure payloads;
5. readiness that reports inspection PostgreSQL as `ready`, `misconfigured` or
   `unavailable` when enabled, while retaining a non-failing Legacy readiness
   path for an inspection-only database outage;
6. package inclusion, tracked-file secret/address redaction, unpushed-history
   audit and a clean Git review.

## Production Freeze

No production service, database, Nginx, systemd unit, current symlink, secret,
feature flag or AEE configuration is changed by this hardening phase. Existing
production scheduler, PostgreSQL, Legacy and Realtime operations remain under
their prior controls.

Read-only observation on 2026-08-28 confirms V2 health endpoints are reachable;
Dashboard, Inspection and Realtime feature flags are enabled, while Audio,
Control, AccountPool and Records are disabled. The deployed readiness endpoint
still reports PostgreSQL as `not_enabled`; that is a local-code observability
fix target, not a conclusion about the underlying production data path.

## Explicit Non-goals

- no AEE/media investigation or new media behavior;
- no 32-stream, AccountPool, FFmpeg, SFU, transcoding, PTZ, Talkback, recording
  or new infrastructure;
- no automatic Flight/Routine matcher or new business KPI;
- no final dashboard visual redesign;
- no M4 closure, M5 start, full rollout or Legacy retirement.

## Current Audit Blocker (2026-08-28)

The local Phase 6 code/test/package and current tracked-file scans passed, but
the branch is 48 commits ahead of its remote tracking ref and the unpushed
history contains 25 non-documentation infrastructure-address hits. No
high-confidence private-key, long-Bearer or credential-URL pattern was found.

A repository-external Git bundle backup must be created and verified, then the
work stops for `OWNER ACTION REQUIRED — GIT HISTORY SANITIZATION DECISION`.
Do not rebase, filter-repo, force-push, commit or deploy until the owner
chooses the sanitation approach.

## Required Stop Conditions

Stop and request owner input if a production modification is needed, a
credential would be exposed, a destructive database action is proposed, access
control cannot be made fail-closed, a production data path requires a new
infrastructure component, or unpushed Git history requires mass sanitation.
