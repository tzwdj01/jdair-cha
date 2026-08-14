# TASK_GOAL

Last updated: 2026-08-14

This file tracks the active objective and completion conditions for the current
CHA video-record and realtime-inspection optimization task. Historical details
remain in the release reports and Runbooks under `docs/`.

Status meanings:

- `COMPLETED`: implemented and verified for the stated scope.
- `COMPLETED BUT UNVERIFIED`: implemented, but the current target environment
  still lacks required acceptance evidence.
- `IN PROGRESS`: actively being executed and not blocked.
- `TODO`: not started and not currently blocked.
- `BLOCKED`: cannot safely continue until named evidence, access or approval is
  available.

## 1. Overall Objective

Improve the CHA video-record system's layout and operation model without
breaking existing data/API behavior, while adding a rollback-safe, read-only
realtime video inspection capability that reuses the AEE/MCS8 native media
chain.

The current objective is not to add more M3 product features. It is to resolve
the controlled-production evidence gap, repeat the approved Canary safely and
decide whether the already-developed M3 realtime capability may remain enabled
for approved users.

## 2. Current Production Baseline

Status: **COMPLETED BUT UNVERIFIED**

- Git branch: `codex/m3-release-fix-20260814`
- Git commit: `17a1b15ac82180269a82dfda430c4dfa00211489`
- Production V2 release:
  `/opt/jdair-cha/v2/releases/0.8.0-m3-final-rc-release-fix`
- Version/build: `0.8.0 / m3-final-rc`
- Legacy service, V2 service and Nginx were healthy after the latest Canary
  abort; V2 reported `NRestarts=0`.
- Production AEE and Canary configuration is present in the protected
  production environment; values are not stored in Git.
- Current production feature flags after the abort:

```text
CHA_V2_FEATURE_REALTIME_READONLY=false
CHA_V2_FEATURE_REALTIME_AUDIO=false
CHA_V2_FEATURE_REALTIME_CONTROL=false
CHA_V2_FEATURE_ACCOUNT_POOL_V2=false
```

- Latest verified rollback archive:
  `/opt/jdair-cha/backups/jdair-cha-before-m3-realtime-20260814-173601.tar.gz`
- Archive SHA-256:
  `31ab59496d0791b46389f1bd00f4c28f711a6fd5b5b120677256a74c296c2c95`

The release-fix is deployed, but M3 production activation is not accepted
because the required production 1 -> 4 -> 6 Canary sequence did not complete.

## 3. Completed Milestones

### COMPLETED

- Layout redesign phases and rollback records for the existing CHA pages.
- Day/night theme, compact video-record tables, reference-information
  expansion, popup historical playback and tab-based dispatch/query layouts.
- M0 rollback-safe modernization foundation.
- M1 read-only V2 adapter and compatibility layer.
- M2 situation dashboard, production release and rollback verification.
- M3.1 single-stream CHA session lifecycle and AEE-native video chain.
- M3.2A Model A selection:
  `1 CHA session -> 1 AEE login -> 1 Gateway -> 1 Media room/transport -> N consumers`.
- M3.2B formal 1/4-stream product UI and selective close/reopen behavior.
- M3.2C telemetry, lifecycle logging, security and cleanup hardening.
- M3 Final 1/4/6 product implementation, local screenshot and receive-only
  audio implementation.
- Historical real-AEE validation of six 1920x1080 H.264 live tracks using
  devices recorded in `docs/M3_FINAL_VALIDATION_REPORT.md`.
- Backend lifecycle churn, browser churn, package checks and release-candidate
  validation recorded in the M3 reports.
- Release-fix branch and commit pushed to
  `origin/codex/m3-release-fix-20260814`.
- Release tooling now uses the production V2 venv, fails before switching
  `current` when candidate tests fail and performs only one rollback/restart
  sequence after a post-switch failure.
- Automated Canary-user default-deny enforcement for realtime HTTP APIs and
  Control/Gateway/Media WebSocket endpoints.
- AEE Secret configuration through environment variables only; health
  distinguishes enabled/configured states without actively logging in to AEE.
- Isolated final-release rehearsal.
- Dedicated production backup and deployment of the release-fix with realtime
  initially disabled.

### COMPLETED BUT UNVERIFIED

- The M3 product is complete in code, but the current production deployment has
  not passed the required end-to-end 1 -> 4 -> 6 Canary.
- Non-Canary rejection is covered by automated tests, but a production
  authenticated non-Canary negative check was not completed in the latest
  Canary window.
- Historical six-stream evidence is valid for the devices and environment
  recorded at that time; it does not explain the current `WXB358` discrepancy.

## 4. Active Milestone

### BLOCKED — M3 Production Canary evidence and AEE/CHA discrepancy

Two controlled production attempts on 2026-08-14 failed consistently for
device `WXB358`:

- AEE login succeeded.
- Gateway and Media connections were established.
- The first attempt proved `WXB353` could reach first frame and play.
- `WXB358` received an accepted `openVideo` path but did not produce a first
  frame and reached `FIRST_FRAME_TIMEOUT`.
- The browser also reported `openvideo is not defined`.
- Retrying `WXB358` as the first and only stream reproduced the failure.
- Both failed sessions recorded `session_closed`,
  `gateway_proxy_disconnected` and `media_proxy_disconnected`.
- Realtime was immediately disabled after the failure.

No product-code workaround is authorized until the AEE reference comparison
below is completed.

## 5. Remaining Work

### IN PROGRESS

- No business implementation is currently in progress. The active product
  milestone is intentionally stopped at the blocker above. Governance-file
  integration is the only work in this change.

### BLOCKED

- Determine whether `WXB358` is an upstream/device/profile/permission issue or
  a CHA SDK/orchestration mismatch.
- Complete the production 1 -> 4 -> 6 video Canary with six currently safe,
  approved online devices.
- Approve production realtime activation only after the complete Canary and
  resource-release checks pass.

### TODO

- Perform the AEE-native versus CHA comparison defined below.
- Record a capability classification using
  `docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`.
- If evidence identifies a CHA gap, implement only the smallest evidence-based
  fix on a dedicated branch and repeat automated lifecycle/release tests.
- Verify an authenticated non-Canary user is rejected by the realtime page,
  APIs and all three WebSocket endpoints in the controlled production window.
- Repeat the approved sequence:
  one stream -> four streams -> selective close/reopen -> six streams ->
  selective close/reopen -> screenshot/fullscreen -> session close.
- Confirm post-close active session, stream, Gateway and Media gauges are zero.
- Observe V2/legacy health, service restart count, 5xx errors and structured
  realtime errors after the Canary.
- Update the release/Canary evidence report without rewriting historical
  reports.

## 6. AEE Reference Evidence Rules

All AEE/MCS8/media decisions must follow:

**AEE -> CHA comparison evidence -> capability classification -> CHA design**

The full rules are in:

`docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`

### AEE VERIFICATION REQUIRED — WXB358 first-frame discrepancy

- **What to verify:** whether the AEE native page can open `WXB358`, which SDK
  method and exact parameter/profile it uses, whether a consumer and live track
  are created, and whether first frame succeeds.
- **Devices:** `WXB358` as the affected device and `WXB353` as the latest
  known-good control. If available and approved, also compare with the
  historically validated devices `WXB301`, `WXB342`, `WXB345`, `WXB367` or
  `WXB368`.
- **User/permission:** an approved AEE/CHA Canary account with realtime video
  permission. Credentials and tokens must remain outside Git and evidence
  files.
- **Pages/scenarios:** first open one device in the AEE native realtime page;
  then run the equivalent single-device flow in CHA
  `/api/v2/realtime`. Use separate approved accounts if simultaneous sessions
  would interfere; otherwise run sequentially.
- **HTTP evidence:** login/session purpose, device status/capability response,
  media-server resolution, status codes, timing and redacted response shape.
- **WebSocket evidence:** Gateway and Media URL class, open/message/close order,
  room join, `openVideo` command/ack, consumer creation and close/leave
  sequence. Redact tokens, cookies, internal credentials and reusable
  connection material.
- **SDK evidence:** exact method name/casing, argument shape, event ordering,
  consumer/track callbacks and the source of `openvideo is not defined`.
- **RTP/codec/capability evidence:** SDP summaries, selected codec and profile,
  H.264 fmtp/profile-level-id where present, payload type, RTP capabilities,
  selected stream type/profile/quality and resolution.
- **Outcome evidence:** first-frame latency, `videoWidth/videoHeight`, track
  state, timeout/error, close acknowledgement and final active resource
  counters.

Until this comparison is complete, do not infer that AEE lacks support and do
not introduce FFmpeg, a custom decoder, a media server, an SFU or protocol
emulation.

## 7. Constraints / Non-goals

- Do not reimplement milestones already marked completed.
- Do not add new M3 product capability during Canary remediation.
- Do not implement 9-stream layout.
- Do not implement PTZ, device control, talkback, microphone send media,
  recording or central media storage.
- Do not enable receive-only audio in production without a separate approval.
- Do not introduce AccountPool unless later evidence and an approved milestone
  require it.
- Do not introduce FFmpeg, transcoding, a self-hosted media server, an SFU or a
  custom decoder as a shortcut.
- Do not replace existing AEE SDK media behavior or legacy business APIs.
- Do not perform destructive database migration.

## 8. Verification Requirements

For an evidence-based code fix:

- run the repository's existing backend tests;
- run Python compile checks;
- run JavaScript syntax/build checks defined by the project;
- add regression coverage for the identified discrepancy where mockable;
- repeat single-stream open/close/reopen;
- repeat four-stream survivor and reopen behavior;
- repeat six-stream survivor and reopen behavior when six approved devices are
  available;
- verify first frame, resolution and live track state;
- verify duplicate close and failure cleanup are idempotent;
- verify screenshot/fullscreen behavior when in scope;
- verify no page errors or unbounded reconnect loops;
- verify all realtime resource gauges return to zero.

No real-device conclusion may be generalized beyond the tested device,
firmware/profile, account and environment without supporting evidence.

## 9. Production Safety Requirements

- Keep realtime disabled while investigating or deploying an unverified fix.
- Keep audio, control and AccountPool disabled.
- Use the explicit Canary allowlist; an empty allowlist must deny all users.
- Back up production env, current release and required application data before
  a production change.
- Use a new release directory and preserve the previous rollback target.
- Run release dry-run and isolated rehearsal before switching `current`.
- Do not place production credentials, env files or backup archives in Git.
- Abort immediately on repeated first-frame timeout, resource leakage,
  Gateway/Media growth, authentication/owner-isolation failure, legacy impact,
  service instability or sensitive-data exposure.
- On abort, disable realtime first, verify health and resource release, and
  roll back only if the deployed release itself is unhealthy.

## 10. Git / Release Requirements

- Keep governance/documentation commits separate from business-code fixes.
- Use a dedicated fix branch for any evidence-based media change; do not append
  unrelated product work to the release-fix branch.
- Before commit: inspect `git status`, run `git diff --check` and confirm no
  secrets or generated logs/results/archives are tracked.
- Run project-defined tests and package validation before a release commit.
- Push the dedicated branch; do not auto-merge or create a release tag.
- Do not update production `current` from an uncommitted or unpushed source
  state.

## 11. Done Criteria

The current active milestone is done only when all of the following are true:

- [ ] The `WXB358` discrepancy has current AEE-versus-CHA evidence.
- [ ] The result is assigned a documented capability classification.
- [ ] Any CHA change is minimal, evidence-based and regression-tested, or the
      issue is documented as upstream/device-specific with an approved safe
      device set.
- [ ] Production Canary user isolation is positively and negatively verified.
- [ ] One-stream playback and deterministic close pass.
- [ ] Four-stream playback, selective close and reopen pass.
- [ ] Six-stream playback, selective close and reopen pass.
- [ ] First frame, resolution and live track states are recorded.
- [ ] Screenshot/fullscreen checks pass for the existing product.
- [ ] Session, stream, Gateway and Media active counters return to zero.
- [ ] Legacy and V2 health remain normal with no release-induced 5xx/restarts.
- [ ] Long-lived AEE credentials remain server-side and absent from Git/logs.
- [ ] Production activation decision and rollback evidence are recorded.
- [ ] Git worktree is clean and the approved branch is pushed.

## 12. Evidence / Decision Log

| Date | Milestone | Evidence / decision | Status |
| --- | --- | --- | --- |
| 2026-08-13 | M0-M2 | Rollback-safe V2 foundation, read-only adapter and situation dashboard released with documented backups and rollback checks. | COMPLETED |
| 2026-08-14 | M3.1 | AEE native chain integrated through CHA session orchestration with deterministic single-stream lifecycle. | COMPLETED |
| 2026-08-14 | M3.2A | Real-device evidence selected Model A: one AEE login/Gateway/Media session with multiple consumers. | COMPLETED |
| 2026-08-14 | M3 Final | Historical six-stream H.264 validation, churn, screenshot, receive-only audio and resource cleanup recorded in `docs/M3_FINAL_VALIDATION_REPORT.md`. | COMPLETED |
| 2026-08-14 | Release fix | Production venv release tests, fail-fast behavior, single rollback path, Canary allowlist and env-only AEE Secret configuration added and tested. | COMPLETED |
| 2026-08-14 | Production deployment | Dedicated backup created and release-fix deployed; health checks passed. | COMPLETED |
| 2026-08-14 | Production Canary | `WXB353` reached first frame; `WXB358` repeatedly timed out and browser reported `openvideo is not defined`; sessions and relay connections closed; realtime disabled. | BLOCKED / AEE VERIFICATION REQUIRED |

## 13. Next Recommended Actions

1. Keep production realtime disabled.
2. Use the AEE native page to execute the bounded `WXB358`/`WXB353`
   comparison described in section 6.
3. Classify the result before proposing code.
4. If the issue is a CHA gap, create a dedicated minimal fix branch and run the
   existing M3 lifecycle/release test suite.
5. If the issue is device/profile-specific, document the compatibility rule
   and assemble six approved devices that pass the native AEE check.
6. Request a new controlled production Canary window and repeat the complete
   acceptance sequence.
7. Do not start any new large feature milestone as part of this governance
   change.
