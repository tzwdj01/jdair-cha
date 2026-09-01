# M4 Legacy Maintenance Realtime Workspace — Implementation Record

**Status:** `DEVELOPMENT VALIDATED / NOT DEPLOYED`
**Date:** 2026-09-02
**Scope:** bounded Owner-observed M4 product integration; no Legacy retirement.

## Purpose

Add a visible **实时视频** tab beside the existing Legacy `监察工作台` file and
playback controls. It is a maintenance-department entry point for the already
verified CHA M3 realtime capability, not a new video platform.

The user flow is:

`Legacy 监察工作台 → 实时视频 → 维修部在线 WXB 设备 → click one or more devices → shared M3 session / multi-tile playback → explicit close`

## Scope and capability classification

| Area | Classification | Decision |
| --- | --- | --- |
| M3 AEE/MCS8 WebRTC session, gateway and media lifecycle | Class B — SDK / protocol media capability | Reuse unchanged. |
| Legacy selector, WXB maintenance grouping and same-origin iframe handoff | Class C — CHA business/UI aggregation | Implemented as a bounded Legacy shell. |
| AEE Visual page UI details | Class D — reference only | No AEE UI code or private endpoint is copied. |

The integration follows `docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`: it adds
no media protocol, video copy, FFmpeg, transcoding, SFU, decoder or proxy.

## Implemented behavior

- Legacy adds a same-style modal/tab labelled `实时视频` in the `监察工作台`
  toolbar.
- The modal's left rail presents only devices that are both **online** and have
  a `WXB` identifier. Its display group is fixed to `维修部`; upstream display
  group labels are not trusted for this scope.
- The right stage embeds the existing same-origin visual M3 viewer at:
  `/api/v2/realtime?workbench=1&embed=visual&scope=maintenance_wxb`.
- Device clicks add streams to one reused M3 session. The existing verified
  limit remains **six** streams; this does not enable 9/16 layouts.
- The V2 realtime API enforces the scope server-side:
  - `GET /api/v2/realtime/devices?scope=maintenance_wxb` emits only online WXB
    devices and normalizes their public group to `维修部`.
  - A `maintenance_wxb` session rejects an attempt to add a non-WXB or offline
    device with the CHA error `device_not_in_scope` or the existing offline
    error. The browser filter is therefore not the security boundary.
- Parent/iframe commands and state messages use matching `location.origin` and
  `contentWindow` checks.
- Closing the modal sends the existing M3 close-session command, then unloads
  the iframe. Existing M3 stream/consumer/gateway/media cleanup remains the
  authority for resource release.

## Security and authorization boundary

- No AEE username, password, token, cookie, SessionId or media credential is
  added to Legacy HTML, JavaScript, logs or Git.
- Existing V2 realtime feature flags and realtime Canary allowlist are not
  changed. A Legacy session identity which is not eligible for M3 realtime is
  still rejected by the V2 realtime API/WebSocket boundary.
- Legacy's MCS8-backed session authentication remains unchanged; this work does
  not extend `AuthorizedUser` protection to Legacy.
- Device IDs are attached as escaped data attributes and handled by event
  listeners; no upstream value is interpolated into an inline click handler.

## Development verification

| Check | Result |
| --- | --- |
| Full V2 Python suite | PASS — 343 tests, 2 explicit isolated-PostgreSQL skips |
| V2 Python compilation | PASS |
| Node realtime runtime regression | PASS |
| Realtime maintenance-scope API regression | PASS |
| Legacy inline JavaScript syntax check | PASS |
| Browser/production visual playback | NOT YET RUN — requires controlled release and a lawful eligible user session |

## Release and owner-validation gate

Before a controlled production release:

1. build and freeze one exact V2 package from a clean committed tree;
2. create an isolated Legacy release from the observed active Legacy target;
3. retain the prior V2 and Legacy release targets as rollback points;
4. change neither Nginx, systemd unit definitions, feature flags, realtime
   allowlist nor production secrets;
5. validate HTTPS Legacy root, V2 live/ready, and retained Legacy functions;
6. using a lawful realtime-eligible account, validate one WXB first frame, a
   second WXB stream in the same session, explicit close and a clean re-open.

No production change has been made by this implementation record.

## Known limits

- Uploaded/recorded-video browser preview remains `AEE VERIFICATION REQUIRED`.
- AEE Visual dynamic 9/16 capacity and resource-release evidence is still
  required before enabling more than six realtime streams.
- This is a Legacy-to-V2 capability bridge, not an access-control migration or
  a replacement/retirement of Legacy.
