# CHA v2 modular service

This service is deployed beside the existing CHA application. It owns only
the `/api/v2/` namespace and does not replace existing `/api/*` routes.

## M2 dashboard and M3.2B realtime inspection

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
- `GET /api/v2/realtime` (formal 1/4-stream inspection page; feature-gated)
- `GET /api/v2/realtime/devices`
- `GET /api/v2/realtime/health` (coarse readiness; no AEE login)
- `GET /api/v2/realtime/diagnostics` (authenticated aggregate snapshot)
- `POST /api/v2/realtime/sessions`
- `GET /api/v2/realtime/sessions/{session_id}`
- `POST /api/v2/realtime/sessions/{session_id}/heartbeat`
- `POST /api/v2/realtime/sessions/{session_id}/streams`
- `DELETE /api/v2/realtime/sessions/{session_id}/streams/{stream_id}`
- `DELETE /api/v2/realtime/sessions/{session_id}`
- `WS /ws/v2/realtime/{session_id}/control`
- `WS /ws/v2/realtime/{session_id}/gateway`
- `WS /ws/v2/realtime/{session_id}/media`
- `GET /api/v2/docs`

M2 enables only `dashboard_v2`. It uses a narrow, read-only adapter to the
existing local service and forwards only the current browser's CHA session
cookie. It does not accept or persist user passwords. Metrics use bounded
process-local caches with stale fallback so a slow video/file source does not
block the whole dashboard. Device trend samples are stored in
`CHA_V2_DASHBOARD_STATE_DIR/device-trend.json`.

The legacy page and every legacy `/api/*` contract remain unchanged.

The committed release keeps `realtime_readonly=false`. A development or test
environment may explicitly enable it and provide AEE credentials through
environment variables. The browser receives only a CHA session cookie and
same-origin WebSocket paths. The V2 service logs in to AEE server-side, keeps
gateway and media tokens in process memory, rewrites `ConnecteInfo`, and
relays the SDK WebSockets without returning either token to browser code.
M3.2B integrates the validated Model A runtime into a formal maintenance
inspection page. One CHA session owns one AEE login, Gateway relay, media-room
connection and receive transport, with at most four independently tracked
video consumers. One active stream uses a single-tile layout; two through four
streams use a 2x2 layout. Each tile exposes first-frame, resolution, track,
close, retry and fullscreen state without rebuilding the shared AEE runtime.
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

Default abuse guards allow at most three active realtime sessions per login
session and ten session creations per 60 seconds. These values are configurable
but do not change the four-stream product limit.

Four streams are validated. Six and nine streams are not validated or
advertised. Audio, device control, screenshots and AccountPool remain disabled.

## Local test

```bash
python -m unittest discover -s tests -v
uvicorn app.main:app --host 127.0.0.1 --port 8791
```

The real-device baseline additionally reads the existing CHA URL and login
from `CHA_M3_LEGACY_URL`, `CHA_LOGIN_USER` and `CHA_LOGIN_PASS`. AEE settings
use the `CHA_V2_AEE_*` environment variables documented in `.env.example`;
none are written into the result JSON or browser/server log.
