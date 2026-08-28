# M4 Clean Branch Migration Record

**Date:** 2026-08-28

**Purpose:** Preserve the verified M4 outcome while replacing the local,
unpublished development history with a small, auditable clean branch history.

## Protected Historical Source

- Historical local development branch:
  `codex/m4-inspection-data-center-20260815`
- Original 48-commit source head:
  `f700fa457fe2385db881fb5b4eddb7c32449be01`
- Local temporary protection snapshot, which also contains the tested Phase 6
  hardening working tree:
  `8ff2c8a45e5dfdf946288028c6db0ee0c0cf30fb`
- Repository-external recovery bundles are retained under the local backups
  directory. They are not Git-tracked artifacts.

The historical branch is retained locally as **LOCAL HISTORICAL DEVELOPMENT
BRANCH — DO NOT PUSH**. Its original development commits are preserved for
local recovery and evidence review only.

## Clean Migration

- Verified clean base:
  `origin/codex/m4-inspection-data-center-20260815`
- Clean base commit:
  `9ed28c43d37f71981d19e0e8145ef11ba470d9a5`
- Clean branch:
  `codex/m4-clean-phase6-20260828`

The clean branch was created at the verified remote base. The complete final
tree from the protected local source snapshot was applied once, checked for
exact tree equality, then organized into a small set of logical commits.

## Scope Preserved

The migration preserves the final verified M4 product tree, including:

- normalized inspection-history data contracts and PostgreSQL stores;
- MCS8 native read-only collection, scheduler, backup runtime and tests;
- AuthorizedUser, inspection workflow, RealtimeViewEvent and candidate flows;
- production-PG operational Dashboard APIs, pages, locations and overview;
- Phase 6 Dashboard authorization, readiness, pool and concurrency hardening;
- M4 governance, evidence, runbook and reference documentation.

The clean branch intentionally does **not** retain the original 48-commit
history. Approved final-tree sanitization replaces environment-specific
infrastructure literals with safe documentation/test placeholders.

## Verification Rule

The authoritative clean branch head is read from Git after the final migration
commit; this file intentionally does not contain a self-referential commit SHA.
Before push, the final clean tree must match the protected source tree except
for approved sanitization, generated/local artifacts and this migration record.
