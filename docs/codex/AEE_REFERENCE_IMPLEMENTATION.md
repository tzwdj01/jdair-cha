# AEE Reference Implementation Principles

## 1. Purpose

This document defines the engineering decision process for work involving AEE,
MCS8, realtime video, WebRTC, WebSocket, the AEE browser SDK, codec/RTP
parameters, stream profiles, device capability and media-session lifecycle.

AEE is the behavioral reference implementation for upstream capabilities. It
is not a license to copy credentials, production configuration, private
endpoints or unreviewed PoC code into CHA. CHA remains responsible for
authentication, authorization, session orchestration, observability, product
UX and safe resource cleanup.

The mandatory sequence is:

```text
AEE reference
  -> CHA comparison evidence
  -> capability classification
  -> CHA design
  -> bounded implementation
  -> real-device verification
```

Do not skip the evidence stage and guess an implementation.

## 2. When This Document Applies

Read and follow this document before changing code or architecture when any of
the following is true:

- AEE has a capability that CHA does not yet expose.
- MCS8/AEE SDK behavior, protocol fields or method semantics are unclear.
- WebSocket connection, reconnect, heartbeat or shutdown behavior is unclear.
- RTP, codec, capability negotiation or stream-profile behavior is unclear.
- The same device behaves differently in AEE and CHA.
- A media connection, first frame, track, consumer or release step fails.
- Device compatibility differs by model, firmware, tenant, account or profile.
- A proposal would introduce FFmpeg, a media relay, an SFU, a custom decoder,
  protocol emulation or another complex workaround.

## 3. Evidence Hierarchy

Use the strongest available evidence and record its date, environment, user
role, device and scenario:

1. **Observed AEE native behavior** in the approved AEE page with a real device.
2. **Captured AEE protocol behavior**, including redacted HTTP, WebSocket, SDK,
   SDP, RTP, codec, capability and lifecycle observations.
3. **The pinned AEE/MCS8 SDK and its provenance** already used by this
   repository.
4. **Observed CHA behavior** from the same account class, device and scenario.
5. Existing repository tests, probes, reports and Runbooks.
6. Assumptions or recollection, which are not implementation evidence.

Documentation and old probes may establish a baseline, but a current
device-specific discrepancy requires current comparison evidence.

All evidence must be redacted. Never store passwords, reusable tokens,
Authorization headers, cookies, unredacted `ConnecteInfo`, production env
files or private credentials in Git, reports, screenshots or logs.

## 4. AEE-to-CHA Comparison Procedure

### 4.1 Define a bounded question

State exactly what is unknown. Examples:

- Which `openVideo` method and parameters does AEE use for this device?
- Which stream profile is selected?
- Which H.264 profile/level or other codec is negotiated?
- Does AEE receive a live track and first frame from the device?
- What is the correct close/leave/disconnect order?

Do not start with a proposed workaround.

### 4.2 Establish a control

Use:

- the affected device;
- one known-good comparison device where possible;
- an approved user with the same required permissions;
- the AEE native page and the equivalent CHA page/operation;
- the same network and a short, non-disruptive observation window.

Do not run uncontrolled tests against business devices. Follow the production
Canary and rollback requirements in `docs/M3_REALTIME_RUNBOOK.md`.

### 4.3 Capture comparable observations

Collect only what is needed:

- HTTP request purpose, status, timing and redacted response shape;
- Gateway and Media WebSocket open/message/close sequence;
- room resolution and join events;
- SDK method names, argument shapes and event ordering;
- SDP offer/answer summaries;
- codec MIME type, payload type, profile/level and relevant fmtp values;
- RTP capabilities and selected producer/consumer parameters;
- requested stream type/profile/quality;
- consumer creation, MediaStream binding, track state and resolution;
- first-frame timing and timeout behavior;
- `closeVideo`/`closeAudio`, consumer close, room leave and socket disconnect;
- final active session/stream/Gateway/Media counters.

Keep raw logs separate from structured JSON results. Use UTF-8 for all text.

### 4.4 Compare behavior

Create a small comparison table:

| Step | AEE native | CHA | Difference | Evidence |
| --- | --- | --- | --- | --- |
| Login/token | | | | |
| Gateway connect | | | | |
| Media resolve/connect | | | | |
| Room join | | | | |
| `openVideo` request | | | | |
| Consumer/track | | | | |
| First frame | | | | |
| Close/release | | | | |

The comparison must distinguish an upstream/device failure from a CHA
orchestration failure.

## 5. Capability Classification

Classify the result before designing a change:

1. **AEE NATIVE / CHA SUPPORTED**
   Behavior is confirmed and CHA already matches it. No feature work is
   required; improve tests or operations evidence only if needed.

2. **AEE NATIVE / CHA GAP**
   AEE works, CHA differs, and the protocol/SDK delta is identified. Implement
   the smallest change that makes CHA follow the confirmed AEE behavior.

3. **AEE NATIVE / POLICY-GATED**
   AEE supports the capability, but CHA intentionally disables it for security,
   authorization, product-scope or production-safety reasons. Do not bypass the
   gate.

4. **DEVICE / ACCOUNT / TENANT SPECIFIC**
   Behavior depends on device model, firmware, account permission, tenant,
   stream profile or current device state. Record the compatibility boundary;
   do not generalize from one device.

5. **AEE VERIFICATION REQUIRED**
   Evidence is missing, stale or contradictory. Do not guess. Record the exact
   verification plan in `TASK_GOAL.md` and continue only with unrelated work.

6. **NOT AEE NATIVE / ARCHITECTURE DECISION REQUIRED**
   AEE does not provide the required behavior. Any FFmpeg, custom media server,
   SFU, decoder, transcoder or protocol workaround requires a separate approved
   architecture decision, threat model, capacity plan, rollback plan and
   operational ownership. It must not be introduced as an incidental fix.

## 6. CHA Design Rules

- Reuse the verified AEE native media chain whenever available.
- Keep CHA session management separate from AEE media objects.
- Keep long-lived AEE credentials and reusable tokens server-side.
- The browser may receive only the minimum same-origin session/relay material
  proven necessary; document any unavoidable temporary exposure.
- Do not modify the vendored AEE SDK unless comparison evidence proves a pinned
  SDK defect and the change has an explicit maintenance/provenance plan.
- Do not replace existing business APIs to solve a media issue.
- Add only the capability required by the active milestone.
- Preserve receive-only behavior unless an independently approved milestone
  explicitly covers send media or device control.
- Treat first-frame success and deterministic release as separate acceptance
  requirements.

## 7. Lifecycle and Release Requirements

Every realtime change must account for:

```text
login/token
-> Gateway connect
-> Media resolve/connect
-> room join
-> openVideo/openAudio
-> consumer/track/first frame
-> close consumer
-> leave room
-> disconnect Media/Gateway
-> clear CHA session
```

Normal close, selective stream close, browser disconnect, first-frame timeout,
upstream failure, duplicate close and service shutdown must not leave active
tracks, consumers, sockets, background tasks or zombie CHA sessions.

Verification must include the relevant automated tests plus a bounded
real-device comparison when upstream behavior is involved. Production
activation requires feature flags, Canary isolation, backup, rollback and
post-close counters returning to zero.

## 8. Decision Record

For every material AEE-related decision, add a concise entry to
`TASK_GOAL.md` under **Evidence / Decision Log** containing:

- date and milestone;
- question;
- AEE evidence;
- CHA evidence;
- classification;
- decision and non-goals;
- verification result or `AEE VERIFICATION REQUIRED`;
- links to sanitized repository evidence.

Unknowns must remain explicit. Absence of evidence is not evidence that AEE
cannot provide a capability.
