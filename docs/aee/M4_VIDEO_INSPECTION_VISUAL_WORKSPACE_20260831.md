# M4 Video Inspection Visual Workspace — Production Validation

**Date:** 2026-08-31  
**Scope:** bounded Owner-observed refinement only; M4 remains active.

## Released artifact

| Item | Evidence |
| --- | --- |
| Source commit | `889d0b11571966354cab2d4a034ca76289a6eee8` |
| Package SHA-256 | `a114c22886ceba33c186b5064fe15174fc99b8ff46fcacb9db26c64ff65bfde2` |
| Production release | `20260831130743-video-inspection-visual-889d0b1` |
| Runtime identity | commit and package hash matched the frozen package |
| Rollback point | prior `aa90fd9` Video Inspection Workbench release was retained |

The deployment guard, extracted-package test suite and health checks passed
before the V2 release switch. The source suite passed **332** tests with two
explicit isolated-PostgreSQL skips; the extracted package also passed **332**
tests with twelve intentional archive-only skips.

## What changed

- `/api/v2/dashboard/workbench` remains the only video-inspection workspace.
- The existing M3 viewer is embedded in visual mode and receives same-origin
  commands to add or close a device in **one existing M3 session**.
- `/api/v2/dashboard/inspections` now resolves to the dedicated
  InspectionRecord list/query/export page before the generic summary route.
- Existing InspectionRecord context, draft, submit, audit and correction APIs
  are reused; the correction form is visible only for eligible records.
- Uploads remain safe persisted metadata only. No playback source, signed URL,
  credential, token, cookie or AEE implementation was copied into CHA.

## Production browser evidence

An existing authorized Administrator browser session exercised only read/realtime
actions; it did not create, submit or correct a production inspection record.

| Check | Result |
| --- | --- |
| Workspace source navigator and visual layout | PASS |
| First realtime source | `WXB357`: M3 established, first frame, `1920x1080`, track `live` |
| Additional source in the same session | `WXB348`: joined without iframe/session reset, first frame, `1920x1080`, track `live` |
| Shared multi-tile state | PASS: auto 2x2 layout, `2` streams reported active |
| Per-tile record handoff | PASS: selecting `记` transferred safe device/time context to the parent form; no draft was persisted automatically |
| Selective close | PASS: closing `WXB348` released it while `WXB357` remained playing |
| Workspace close | PASS: explicit close command unloaded the embedded viewer; existing M3 session/pagehide cleanup remained in control |
| InspectionRecord route | PASS: dedicated `监察记录` page exposed filters and CSV/XLSX export links |
| Uploaded-media tab | PASS as metadata: real MediaFile rows shown; each correctly states online preview is pending AEE evidence |

## Post-deploy operational confirmation

After browser validation, V2, Legacy, Nginx and the low-rate scheduler were
active. V2 health and readiness both returned HTTP 200. All three relevant
services reported zero restarts. The scheduler's latest observed cycle completed
and entered its normal 600-second wait state; no long manual observation was
performed.

## Evidence boundary and remaining work

- **AEE Visual:** `STATIC_EVIDENCE_ONLY`; its public chunk supports an
  operational status-first information architecture, not WebRTC, media or
  capacity parity. See `M4_AEE_VISUAL_CHA_COMPARISON.md`.
- **Realtime capacity:** this production acceptance directly exercised one then
  two sources. Existing M3 has prior 1/4/6 evidence and still enforces six
  streams. `9` and `16` remain disabled pending a lawful same-device AEE vs CHA
  capacity and resource-release comparison.
- **Uploaded video playback:** `AEE VERIFICATION REQUIRED` for a lawful AEE
  SignedUrl/browser-preview evidence record. CHA must not guess or persist a
  playback URL.
- **Owner workflow acceptance:** use a deliberately created Owner test record
  to validate draft, submit, query, export, audit and correction. This technical
  validation intentionally did not write a production InspectionRecord.

No FFmpeg, self-hosted media server, SFU, transcoding, video copy/storage,
complex RBAC or new media infrastructure was introduced.
