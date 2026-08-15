# CHA v2 modular service

This service is deployed beside the existing CHA application. It owns only
the `/api/v2/` namespace and does not replace existing `/api/*` routes.

## M2 dashboard and M3 Final realtime inspection

- `GET /api/v2/health`
- `GET /api/v2/health/live`
- `GET /api/v2/health/ready`
- `GET /api/v2/health/upstreams`
- `GET /api/v2/system/version`
- `GET /api/v2/system/features`
- `GET /api/v2/dashboard` (independent dashboard page)
- `GET /api/v2/dashboard/overview`
- `GET /api/v2/dashboard/device-trend`
- `GET /api/v2/dashboard/video-trend`
- `GET /api/v2/dashboard/geography`
- `GET /api/v2/dashboard/coverage`
- `GET /api/v2/dashboard/exceptions`
- `GET /api/v2/dashboard/freshness`
- `GET /api/v2/realtime` (formal 1/4/6-stream inspection page; feature-gated)
- `GET /api/v2/realtime/devices`
- `GET /api/v2/realtime/health` (coarse readiness; no AEE login)
- `GET /api/v2/realtime/diagnostics` (authenticated aggregate snapshot)
- `POST /api/v2/realtime/sessions`
- `GET /api/v2/realtime/sessions/{session_id}`
- `POST /api/v2/realtime/sessions/{session_id}/heartbeat`
- `POST /api/v2/realtime/sessions/{session_id}/streams`
- `POST /api/v2/realtime/sessions/{session_id}/streams/{stream_id}/audio`
- `DELETE /api/v2/realtime/sessions/{session_id}/streams/{stream_id}/audio`
- `DELETE /api/v2/realtime/sessions/{session_id}/streams/{stream_id}`
- `DELETE /api/v2/realtime/sessions/{session_id}`
- `WS /ws/v2/realtime/{session_id}/control`
- `WS /ws/v2/realtime/{session_id}/gateway`
- `WS /ws/v2/realtime/{session_id}/media`
- `GET /api/v2/docs`
- `GET /api/v2/inspection/devices`
- `GET /api/v2/inspection/media`
- `GET /api/v2/inspection/realtime`
- `GET /api/v2/inspection/alarms`
- `GET /api/v2/inspection/locations`
- `GET /api/v2/inspection/devices/{device_id}/timeline`
- `GET /api/v2/inspection/data-quality`
- `GET /api/v2/dashboard/devices`
- `GET /api/v2/dashboard/media`
- `GET /api/v2/dashboard/realtime`
- `GET /api/v2/dashboard/alarms`
- `GET /api/v2/dashboard/data-quality`

M2 enables only `dashboard_v2`. It uses a narrow, read-only adapter to the
existing local service and forwards only the current browser's CHA session
cookie. It does not accept or persist user passwords. Metrics use bounded
process-local caches with stale fallback so a slow video/file source does not
block the whole dashboard. Device trend samples are stored in
`CHA_V2_DASHBOARD_STATE_DIR/device-trend.json`.

The M4 inspection API is registered but gated by
`CHA_V2_FEATURE_INSPECTION_V2` (default off). When enabled without a wired
`InspectionStore` it returns `503 store_not_configured`; with a store it
returns deterministic metrics computed from durable inspection-history rows.
No store is wired in the default release, so production behavior is unchanged.
The first-batch four-tab pages under `/api/v2/dashboard/{devices,media,
realtime,alarms}` consume only the inspection API and show honest
“数据源未接入/待验证” states when no history is available.
The realtime inspection endpoint also returns the current runtime snapshot
(active sessions/streams, Gateway/Media connections) when the realtime session
manager is wired; runtime state stays separate from durable history.

For local development/testing only, a non-production deployment may set
`CHA_V2_INSPECTION_STORE_MODE=memory` to wire the process-local memory store
end-to-end (realtime view sink → store → inspection service → API → pages).
The memory store loses history on restart and is never enabled in production;
production keeps this empty until a durable PostgreSQL store is rehearsed.

`InspectionIngestor` is the write-side ingestion seam: collected
DevOnlineList / RecordFileList / AlarmList rows are normalized and persisted
into the store with accepted/invalid counts and quality flags. It is
source-agnostic and does not depend on AEE authentication, which remains a
separate unverified prerequisite.

`InspectionIngestionScheduler` orchestrates collect → normalize → persist with
an explicit window and a source-agnostic `RowCollector` protocol, testable with
fake collectors.

The data-quality diagnostic reports store coverage, freshness and quality
flags per historical table plus source-system distribution; it reports only
rows that actually exist and never infers missing data.

The legacy page and every legacy `/api/*` contract remain unchanged.

The committed release keeps `realtime_readonly=false`. A development or test
environment may explicitly enable it and provide AEE credentials through
environment variables. The browser receives only a CHA session cookie and
same-origin WebSocket paths. The V2 service logs in to AEE server-side, keeps
gateway and media tokens in process memory, rewrites `ConnecteInfo`, and
relays the SDK WebSockets without returning either token to browser code.
M3 Final integrates the validated Model A runtime into a formal maintenance
inspection page. One CHA session owns one AEE login, Gateway relay, media-room
connection and receive transport, with at most six independently tracked
video consumers. The final validated limit is six: one active stream uses a
single-tile layout, two through four streams use 2x2, and five through six use
3x2. Each tile exposes first-frame, resolution, track, close, retry, fullscreen
and local screenshot without rebuilding the shared AEE runtime.
An unconfirmed partial close degrades only the target stream. Shared
Gateway/Media/control failures are visible and offer an explicit whole-session
reconnect instead of an unbounded reconnect loop.

M3.2C adds bounded process-local operational telemetry without introducing a
monitoring-server dependency. Diagnostics expose aggregate gauges, counters
and duration summaries only; they do not expose session identifiers, device
identifiers, AEE credentials, upstream URLs or ConnecteInfo. Realtime lifecycle
logs correlate `session_id`, `stream_id`, `device_id`, event, status, duration,
error and release mode. Control, Gateway and Media WebSockets require an
allowed Origin and a valid unexpired session lease. CLOSED leases cannot be
replayed.

Production activation additionally requires an explicit comma-separated
`CHA_V2_REALTIME_CANARY_USERS` allowlist. Usernames are taken from the existing
CHA login session. An empty or missing allowlist denies every authenticated
user; it never means "all users". The realtime page, product APIs and all three
Control/Gateway/Media WebSocket endpoints enforce the same Canary decision.
Health reports only boolean `enabled`, `aee_configured`, `canary_configured`
and combined `configured` states and never exposes users or credentials.

All AEE connection settings and credentials are read only from
`CHA_V2_AEE_*` environment variables. Health checks validate configuration
presence without logging in to AEE. AEE login starts only when an authorized
Canary user creates a realtime session.

Default abuse guards allow at most three active realtime sessions per login
session and ten session creations per 60 seconds. These values are configurable
but do not change the four-stream product limit.

Six streams are validated on one AEE account/session. Nine streams are not
validated or advertised. Receive-only audio is technically validated, limited
to one user-enabled stream at a time, and remains disabled by default in
`FEATURES.env`. Device control and AccountPool remain disabled; screenshot is
local-only and never uploads media to the service.

## Local test

```bash
python -m unittest discover -s tests -v
uvicorn app.main:app --host 127.0.0.1 --port 8791
```

The guarded final-release helper uses
`/opt/jdair-cha/v2/venv/bin/python` by default. Run
`ops/mature_m3_final_release_rehearsal.sh` before a production retry; its
success, pre-switch test-failure and post-switch health-failure scenarios use
only an isolated temporary release tree.

The real-device baseline additionally reads the existing CHA URL and login
from `CHA_M3_LEGACY_URL`, `CHA_LOGIN_USER` and `CHA_LOGIN_PASS`. AEE settings
use the `CHA_V2_AEE_*` environment variables documented in `.env.example`;
none are written into the result JSON or browser/server log.
