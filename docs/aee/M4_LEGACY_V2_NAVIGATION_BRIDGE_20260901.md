# M4 Legacy ↔ V2 Navigation Bridge — Production Validation

**Status:** `DEPLOYED / USABLE` — no Legacy functionality or authorization
model was replaced.

## Released behavior

The stable Legacy root remains the site root. Its existing header now contains
one non-intrusive link:

`监察数据中心` → `/api/v2/dashboard`

The V2 shared navigation continues to expose the reciprocal link:

`经典视频监控` → `/`

This is a navigation bridge only. It does not alter Legacy video playback,
Legacy root routing, Legacy API behavior, AEE behavior or the V2 data model.

## Authentication boundary — read-only confirmation

| Surface | Current model |
| --- | --- |
| Legacy | Legacy `/api/login` performs the existing MCS8 WebSocket login. The server creates an in-memory session and returns the HTTP-only, SameSite `jdair_mcs8_session` cookie. Legacy protected APIs require that session. The root HTML carries the login shell and does not itself become an AuthorizedUser-gated V2 page. |
| V2 | V2 resolves the existing Legacy session identity through the Legacy session endpoint, then requires the account to be enabled in the durable CHA `AuthorizedUser` list for protected Data Center and Inspection routes. |
| Does `AuthorizedUser` protect Legacy? | **No.** Legacy checks its own MCS8-backed session and has no `authorized_users` access check. |

The release intentionally leaves these models separate.

## Production release evidence

| Check | Result |
| --- | --- |
| Git implementation commit | `6aa499bcd6c3e91ddbc408388fb3a3ceb9ac0d80` |
| Legacy release | `20260901125005-legacy-v2-nav-6aa499b` |
| Legacy root | HTTP 200 |
| Legacy → V2 entry | present in publicly served Legacy HTML |
| V2 navigation asset | HTTP 200 |
| V2 → Legacy entry | present in the production navigation asset |
| Legacy protected API without a session | HTTP 401, unchanged |
| V2 Dashboard without a session | HTTP 401, unchanged |
| Legacy / V2 / Nginx / scheduler | active |

The Legacy candidate was copied from the observed active production release,
then only the three navigation/CSS insertions were applied and syntax-checked
before the `current` link changed. This preserves production-only runtime
settings that are not part of the tracked historical snapshot. No such setting
was copied into Git, documentation or deployment output.

## Verification

- Source suite: 338 tests passed, with 2 explicit isolated PostgreSQL skips.
- New static regression checks confirm the exact Legacy → V2 link and the
  retained Legacy session-login code path.
- Legacy source syntax compilation passed before release.
- The release script retained the previous Legacy target and rolls back the
  `current` link if a post-switch health check fails.

## Future authorization options — not implemented

### Option A — current, recommended for this stage

Keep Legacy on its current MCS8-backed session authorization and keep V2 on
`Legacy session identity + AuthorizedUser`. This preserves current Legacy user
access and contains the new M4 business controls within V2.

### Option B — later unified Legacy AuthorizedUser control

Do not change the Legacy login or cookie first. The smallest safe future scope
would be to add an explicit Legacy authorization gate **after** its existing
session identity is resolved, backed by the same durable AuthorizedUser source.
That separate project must define:

1. the shared/read-only identity-to-AuthorizedUser lookup boundary;
2. a migration and bootstrap path for legitimate Legacy users;
3. explicit `401` (no session) and `403` (session but not authorized) behavior;
4. audit records, an enabled-admin recovery path and a session-only rollback;
5. production canary tests that prove Legacy video functions remain available
   for authorized users and unavailable for the correct reason otherwise.

It would change Legacy access control and is therefore outside this navigation
release.
