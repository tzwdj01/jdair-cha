# M4 AEE Visual vs CHA Evidence

**Status:** `STATIC_EVIDENCE_ONLY` for AEE Visual; no AEE browser credential
was entered or retained for this comparison.

## Scope and boundary

This record compares the product model of AEE `/v3/visual` with the currently
deployed CHA capabilities.  It does not make AEE a CHA runtime dependency and
does not copy AEE source code, browser credentials, cookies, tokens or media
URLs.

## AEE evidence (2026-08-31)

### Live access result

Opening `http://aee.jdcloud.com/v3/visual` redirected to `/v3/login` in the
available browser context.  The page was not treated as authenticated and no
credential was submitted.  Therefore device interactions, media tiles,
WebSocket calls, stream profiles, RTP parameters and resource release are all
`AEE_VISUAL_LIVE_VERIFICATION_BLOCKED`.

### Static evidence only

The public `mcs__p__v3__visual.chunk.js` was available as static JavaScript.
Its observable behaviour is a **visual data/dashboard page**, not evidence of
a WebRTC camera-wall implementation:

- it calls the upstream device-tree capability (`DevTree`) and separates
  online/offline device status for a chart;
- it renders file statistics (including image, video and audio categories),
  device statistics and alarm-oriented views;
- it composes a left / centre / right visual area, with a central geographic
  scatter/map and surrounding summary/chart panels;
- it links to alarm, file-management and historical-track pages;
- this chunk contains no `openVideo`, `newConsumer`, `MediaStream`,
  `WebSocket`, `rtpParameters` or codec operation evidence.

This is useful evidence for information architecture and status-first visual
design. It is **not** evidence that `/v3/visual` owns the MCS8 realtime media
protocol, supports a particular number of concurrent streams, or can provide
CHA with an uploaded-video playback URL.

## AEE Visual UX model

| Area | AEE pattern (static evidence only) | CHA adoption decision |
| --- | --- | --- |
| Overall page | compact visual dashboard with a central operational focal point and contextual side panels | adopt the clear left/source, centre/video, right/inspection hierarchy |
| Device status | device tree and online/offline aggregation before drill-down | reuse CHA normalized `DeviceStatusEvent` snapshot; M3 remains the final live check |
| File information | file categories and file-management drill-down | reuse safe `MediaFile` metadata; do not invent preview URLs |
| Alarms/track | related operational pages rather than forcing all detail into the visual page | retain CHA Dashboard navigation and drill-down pages |
| Realtime video tiles | no proof in this chunk | reuse the independently verified CHA M3 MCS8/AEE adapter only |
| Multi-stream capacity | no proof | retain CHA's currently configured six-stream ceiling until separate evidence exists |

## Current CHA capability mapping

| Desired visual capability | CHA existing authority | Classification |
| --- | --- | --- |
| device navigator / status badge | `GET /api/v2/inspection/workbench/sources`, normalized device status; M3 device re-check | Class A + Class C |
| realtime tile | M3 `/api/v2/realtime`, realtime session API, MCS8 adapter | Class B |
| start/first-frame/failed/close state | existing M3 tile runtime and session manager telemetry | Class B |
| tile resource release | stream DELETE, session DELETE, heartbeat, pagehide cleanup in M3 | Class B |
| uploaded-video list | safe `MediaFile` metadata via workbench sources | Class A |
| uploaded-video online preview | no persisted playback source; upstream SignedUrl semantics unverified | `AEE VERIFICATION REQUIRED` |
| inspection context and record | existing InspectionRecord create/update/submit/audit API | Class C |
| aircraft / flight / station / task candidate | existing read-only candidate API; user confirmation required | Class C |
| independent Issue workflow | only inspection issue fields exist | `PARTIAL` |

## CHA current-state inventory (code and production evidence)

The classifications below distinguish an Owner-visible action from a merely
present API, data table or backend service. They reflect the deployed
`889d0b1` visual-workspace refinement and its production browser evidence;
Owner business acceptance of records that write production data remains
separate.

| # | Capability | Classification | Evidence / limitation |
| --- | --- | --- | --- |
| 1 | Device list/status | `OWNER_USABLE` | Workbench sources expose normalized status; M3 re-checks online state before opening. |
| 2 | Realtime video | `OWNER_USABLE` | M3 native session path has production first-frame evidence. |
| 3 | Realtime multi-tile | `PARTIAL` | Visual-workspace multi-select now reuses one M3 session. Production evidence covered 1→2 tiles; existing M3 retains its 1/4/6 ceiling and 9/16 remain evidence-gated. |
| 4 | Media/upload record list | `OWNER_USABLE` | Safe persisted `MediaFile` metadata is rendered in the workbench. |
| 5 | Uploaded-video playback | `NOT_IMPLEMENTED` | No browser-playable source is stored or claimed; `AEE VERIFICATION REQUIRED`. |
| 6 | `RealtimeViewEvent` | `PARTIAL` | Persisted by M3 lifecycle and summarized in the protected realtime Dashboard; no per-tile event-history view is exposed in the workbench. |
| 7 | Video Inspection Workbench | `OWNER_USABLE` | Existing `/api/v2/dashboard/workbench`; this refinement improves its visual multi-tile flow. |
| 8 | Create InspectionRecord from realtime | `OWNER_USABLE` | Tile `记` sends same-origin context into the Owner form; service derives identity. |
| 9 | Edit InspectionRecord | `OWNER_USABLE` | Drafts load and save through the existing endpoint. |
| 10 | Aircraft confirmation | `OWNER_USABLE` | Candidate/manual confirmation form; no automatic binding. |
| 11 | Flight confirmation | `OWNER_USABLE` | Candidate/manual confirmation form; no automatic matching. |
| 12 | Station confirmation | `OWNER_USABLE` | Candidate/manual confirmation form. |
| 13 | Routine/maintenance task confirmation | `OWNER_USABLE` | Candidate/manual confirmation form. |
| 14 | Inspection result | `OWNER_USABLE` | Normal / issue result and remarks are recorded. |
| 15 | Issue fields/workflow | `PARTIAL` | Existing record fields and audit exist; no independent Issue entity/workflow. |
| 16 | Submit | `OWNER_USABLE` | Draft → submit uses existing InspectionRecord API. |
| 17 | Correction | `OWNER_USABLE` | Minimal correction UI reuses the existing endpoint and requires a reason; live correction is reserved for Owner acceptance against a deliberate test record. |
| 18 | Audit | `OWNER_USABLE` | The corrected dedicated route is production-reachable; workbench detail renders audit. |
| 19 | Query/filter | `OWNER_USABLE` | Dedicated workflow template and production route are reachable after the registration-order correction. |
| 20 | CSV/XLSX | `OWNER_USABLE` | Existing workflow exports are reachable through the dedicated production route. |
| 21 | Dashboard statistics | `OWNER_USABLE` | Existing protected dashboard/inspection metrics remain the data authority. |
| 22 | Location/map | `OWNER_USABLE` | Protected location analysis exists; coordinate detail remains intentionally limited. |
| 23 | AuthorizedUser management | `OWNER_USABLE` for admin | Existing admin-only page/API; inspector/anonymous boundaries remain server-enforced. |

## AEE Visual UX model

`STATIC_EVIDENCE_ONLY`: the AEE Visual chunk shows an operational visual page,
not an observed camera wall.  It supplies product patterns, not media protocol
facts.

1. **Page regions:** a compact left/centre/right operational view, with the
   central geographic/status focal point and surrounding contextual panels.
2. **Device navigation:** device-tree-derived status precedes drill-down;
   online/offline aggregation is visible before opening detail.
3. **Video workspace:** no visual-chunk proof that it hosts WebRTC tiles.  CHA
   therefore uses its independently proven M3 video grid instead.
4. **Tile information:** CHA keeps the proven device ID/name, connection,
   first-frame, resolution, track state, screenshot, record and close actions.
5. **State expression:** CHA explicitly carries online/offline, connecting,
   waiting-first-frame, playing, degraded, failed and closing states from M3.
6. **Multi-tile management:** AEE capacity/lifecycle evidence is absent. CHA
   retains one/four/six only and shows nine/sixteen as disabled evidence gates.
7. **Click path:** source navigator → same M3 session → add stream → first
   frame; `记` sends a same-origin context into the inspection form.
8. **Close/replace:** an individual M3 tile uses its existing stream DELETE;
   closing the workspace sends an explicit close then retains pagehide cleanup.
9. **Leak avoidance:** CHA does not add a parallel media stack. Existing M3
   close/session/pagehide resource-release behaviour remains authoritative.
10. **Suitable adoption:** source-first layout, concise status badges,
    contextual side panel and adjacent operational drill-down.
11. **Unsuitable adoption:** copying AEE UI code, treating static references as
    protocol evidence, or assuming AEE Visual grants a playback URL/capacity.

## Evidence classification and implementation decision

- **Class A:** normalized device/file metadata and business candidates remain
  CHA backend-read-only inputs.
- **Class B:** M3 Gateway → `mcs8_admin` → `openVideo` → browser MediaStream
  remains the only CHA realtime implementation in this workspace.
- **Class C:** source filtering, shared visual session orchestration,
  inspection context, record/audit and AuthorizedUser scope are CHA business
  aggregation.
- **Class D:** AEE Visual’s private route, source code and page glue remain
  reference-only.

No Architecture Escalation Evidence exists for FFmpeg, a media server, SFU,
transcoding, proxy or copied video storage.  None is introduced.

## Capacity and lifecycle guard

CHA M3 currently enforces a maximum of six active streams in one session.  The
validated media lifecycle is one M3 session → add stream → first frame → close
stream or session → release upstream media.  A visual layout can reserve 9/16
slots as a future product presentation, but it must not enable more than the
configured and evidenced stream capacity.  Raising that limit requires an AEE
vs CHA same-device capacity and resource-release record; it is not justified
by the AEE Visual static chunk.

## Required follow-up evidence

### Uploaded-video preview

`AEE VERIFICATION REQUIRED`:

- use an authorized AEE browser session and one representative RecordFileList
  video;
- perform the ordinary AEE preview action once;
- observe the SignedUrl request/response shape, content type, expiry and
  browser playability without saving a URL, Cookie or token;
- compare to CHA on the same file; classify the resulting capability before
  adding a playback adapter.

### More than six simultaneous realtime streams

`AEE VERIFICATION REQUIRED`:

- use an authorized test account and a controlled group of known-safe devices;
- prove the AEE-supported stream count, first-frame outcomes and releases;
- compare CHA session/resource metrics after selective close and page exit;
- do not lift CHA's configured cap or introduce media infrastructure until the
  evidence is recorded.
