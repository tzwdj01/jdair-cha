# Project Instructions

These instructions apply to the entire repository.

## Active Goal Management

- Read `TASK_GOAL.md` before planning substantial work.
- Preserve completed work and current Git state. Do not reset, reimplement or
  relabel completed milestones as TODO without contradictory repository
  evidence.
- Update `TASK_GOAL.md` only when evidence changes a milestone status,
  production baseline, decision, blocker or done criterion.
- Keep status labels explicit: `COMPLETED`, `COMPLETED BUT UNVERIFIED`,
  `IN PROGRESS`, `TODO` and `BLOCKED`.
- Historical reports remain historical evidence; do not rewrite them to make
  the current state look cleaner.

## AEE Reference Implementation

For any task involving AEE, MCS8, realtime video, WebRTC,
WebSocket media sessions, RTP, codecs, stream profiles,
device capabilities, SDK behavior, or device compatibility:

MUST read and follow:

`docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`

In particular:

- Evidence before workaround.
- Compare AEE vs CHA on the same device/scenario when behavior differs.
- Classify observed capabilities as Class A/B/C/D before implementation.
- Do not introduce FFmpeg, custom media servers, SFU, custom decoders,
  or major media infrastructure without Architecture Escalation Evidence.
- If AEE cannot be accessed legally from the current environment,
  mark the issue `AEE VERIFICATION REQUIRED`; do not invent AEE behavior.

## Production and Security

- Do not expose or commit passwords, reusable tokens, Authorization headers,
  cookies, production env files, server backup archives or unredacted AEE
  connection material.
- Keep stdout/stderr logs separate from structured JSON results and write text
  as UTF-8.
- Do not change production database, Nginx, systemd, `current`, production env,
  feature flags or service state without explicit authorization for that
  operation.
- Before a production change, confirm backup, rollback target, release
  isolation and abort criteria. After realtime tests, confirm session, stream,
  Gateway and Media resources return to zero.
- Preserve legacy `/api/*` behavior and existing M2 business functions unless
  the active milestone explicitly requires a compatible change.

## Scope Discipline

- Implement only the active milestone in `TASK_GOAL.md`.
- Do not add 9-stream video, PTZ, talkback, recording, custom transcoding,
  AccountPool or other new M3 product scope unless a later approved milestone
  explicitly authorizes it.
- Keep documentation/governance changes isolated from business-code changes
  when Git state permits.
