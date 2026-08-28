# M4 Phase 6 — AuthorizedUser Dashboard Canary Attempt

**Status:** `BLOCKED / ROLLED BACK`
**Scope:** controlled V2 Dashboard/Inspection Canary only
**Production data:** preserved; no migration, data reset, Nginx change, or
database write was performed by this attempt.

## Intended scope

The candidate was limited to the already-tested Phase 6 package:

- shared CHA-login + `AuthorizedUser` boundary;
- PostgreSQL-backed Inspection/Dashboard read paths;
- bounded application connection pools;
- truthful inspection PostgreSQL readiness reporting;
- no new media capability, scheduler data domain, RBAC system, feature flag,
  or Dashboard redesign.

The accepted clean branch was used. A small release-artifact test fix was
committed before retrying the deployment: source-check-only release-tooling
tests now skip when the production archive deliberately excludes repository
deployment scripts. The source suite and an extracted package suite both passed
with no failures.

## Release and rollback evidence

1. The existing V2 release was archived and a rollback wrapper was prepared
   before the change.
2. The first release attempt stopped **before** switching `current`: the
   archive test suite attempted to run a source-check-only test without the
   repository-level deployment scripts. No production release was changed.
3. After the artifact test fix, the guarded release helper completed its
   package validation, service restart, and local `live`/`ready` checks.
4. An authenticated browser request to an Inspection data endpoint then failed
   with an upstream timeout. This failed the Canary performance/availability
   gate.
5. The rollback wrapper restored the prior V2 release. After rollback, V2,
   Legacy, and Nginx were active and V2 `live`/`ready` returned HTTP 200.

The deployed candidate must therefore **not** be considered accepted or
active.

## Access-boundary evidence

| Check | Result |
| --- | --- |
| Anonymous Inspection API request | `401` observed |
| Authenticated browser identity | existing CHA session present |
| Authenticated Inspection API read | failed before authorization/data result could be evaluated |
| Non-authorized / disabled account `403` | not verified |
| Enabled inspector `200` | not verified |
| Admin `200` | not verified |

No browser token, Cookie, password, session identifier, or Authorization value
was collected or saved.

## Blocking production evidence

The failure is not an AEE/MCS8 protocol issue. It occurs while CHA opens a new
connection to the production PostgreSQL service over the approved private
overlay.

Observed from the CHA production host using the protected application
configuration and read-only `SELECT 1` probes:

| Probe | Result |
| --- | --- |
| Private-overlay TCP reachability to PostgreSQL | reachable |
| PostgreSQL TLS handshake probe | completed |
| Application connection with current `sslmode=prefer` | timed out |
| Application connection with `sslmode=require` | passed |
| Application connection with `sslmode=prefer` and `gssencmode=disable` | passed |
| Candidate bounded PostgreSQL store health check | failed with bounded `OperationalError` under current configuration |

The current V2 and scheduler environments both use the same PostgreSQL
connection settings, including `sslmode=prefer`. The scheduler was found in a
restart loop caused by the same connection timeout. It was **safely stopped**
to prevent repeated MCS8 collection attempts while PostgreSQL persistence was
unavailable. Existing production PostgreSQL rows were retained.

This is classified as:

```text
PRODUCTION POSTGRESQL CLIENT CONNECTION NEGOTIATION BLOCKER
```

The controlled tests strongly indicate that the current libpq
`sslmode=prefer` negotiation path is unsuitable in this private-overlay
environment. They do not, by themselves, prove the exact internal GSS/libpq
mechanism; no workaround has been applied.

## Time-synchronization observation

Both production nodes reported `NTPSynchronized=no`. Their server-local logs
were dated `2026-08-29` in `Asia/Shanghai` during an execution governed by the
project's `2026-08-28` date. This must be reviewed before treating any
transport-security conclusion as final. No clock or NTP configuration was
changed by this Canary attempt.

## Required owner decision before retry

Do **not** retry the AuthorizedUser Dashboard Canary until the following
controlled remediation is explicitly approved:

1. keep PostgreSQL private to the overlay and keep public `5432` closed;
2. choose and document an application connection policy that succeeds on the
   verified path, preferably enforcing TLS with `sslmode=require`;
3. update the protected V2 and scheduler environment consistently;
4. restart only the affected V2 and scheduler services;
5. verify a read-only PostgreSQL connection, scheduler single-cycle
   persistence, and V2 inspection readiness;
6. re-run the full AuthorizedUser access and Dashboard/API reconciliation
   Canary.

An alternative such as globally disabling GSS negotiation must be separately
reviewed; it must not silently weaken the existing PostgreSQL/Tailscale
security boundary.

## Explicit non-results

- No M4 closure, full-user rollout, M5 work, or Legacy retirement occurred.
- No change was made to production database schema/data, Nginx, public
  firewall exposure, AEE credentials, or media architecture.
- No FFmpeg, SFU, media server, transcoding, or workaround was introduced.
