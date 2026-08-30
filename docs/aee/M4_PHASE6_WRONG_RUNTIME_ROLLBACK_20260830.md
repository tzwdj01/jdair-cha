# M4 Phase 6 — Wrong-runtime Rollback and Package Binding Guard

**Date:** `2026-08-30`
**Status:** `ROLLED BACK / LOCAL RELEASE-GUARD PASS`
**Scope:** a controlled Phase 6 Candidate deployment was stopped at runtime
identity before any business-acceptance, authorization or Dashboard data gate.

## Observed failure

The operator-side preflight validated the newly built Candidate package and its
commit. The historical deployment helper, however, used a separate fixed
default package filename. A stale package at that filename was selected when
the helper ran.

The runtime identity emitted by the release correctly exposed the mismatch.
This is a deployment P0: the Candidate was not the intended clean source, so
no Authorization, pool, data-reconciliation, performance or Dashboard
acceptance outcome is valid from that attempt.

## Containment

The generated release rollback helper was invoked immediately. It restored the
previous V2 release and bounded live health returned HTTP 200. Legacy, Nginx
and the low-rate scheduler remained active with a stable restart count. The
attempt did not modify PostgreSQL data/schema/roles, scheduler collection
semantics, MCS8/AEE behavior or production feature scope.

## Minimal correction

`ops/mature_phase0_deploy_v2.sh` now supports:

* `CHA_V2_RELEASE_PACKAGE` — the exact package path to release;
* `CHA_V2_EXPECTED_PACKAGE_SHA256` and `CHA_V2_EXPECTED_COMMIT` — optional
  identity values validated before any service-affecting release action; and
* `CHA_V2_DEPLOY_VERIFY_ONLY=true` — a no-mutation package identity preflight.

Invalid/mismatched package input fails before a rollback trap is installed,
before a release directory is created, and before `current`, Nginx, protected
environment files or services are touched.

## Automated evidence

The release-tooling suite now executes the helper in verify-only mode against a
temporary package. It proves both:

1. an exact package, SHA-256 and commit pass; and
2. a mismatched commit is rejected before deployment.

The full V2 suite passed with the two explicit isolated PostgreSQL skips. The
previously built package also passed the new no-mutation exact-identity check.

## Next gate

Do not re-run the production Candidate merely to prove this release guard. A
future owner-authorized Phase 6 Canary must first run the verify-only exact
package preflight, record the resulting package identity, then use the same
package path and expected values for the guarded deployment.
