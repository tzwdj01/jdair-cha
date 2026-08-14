# CHA v2 modular service

This service is deployed beside the existing CHA application. It owns only
the `/api/v2/` namespace and does not replace existing `/api/*` routes.

## M2 dashboard and M3.2A realtime session model

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
- `GET /api/v2/realtime` (M3.1 single-stream verification page; feature-gated)
- `GET /api/v2/realtime/devices`
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
M3.2A keeps one native AEE login, Gateway relay, media-room connection and
receive transport per CHA session, while allowing independently tracked video
streams up to `CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION` (default `4`, based on
the completed real-device validation). Closing one stream must receive a
targeted browser `closeVideo` acknowledgement; an unconfirmed partial close
degrades only that stream and preserves the other streams. The existing page
is intentionally still single-stream. The reusable
`multistream_runtime.js` is infrastructure for M3.2B, not a polished
multi-picture UI. Audio and device control remain disabled.

## Local test

```bash
python -m unittest discover -s tests -v
uvicorn app.main:app --host 127.0.0.1 --port 8791
```

The real-device baseline additionally reads the existing CHA URL and login
from `CHA_M3_LEGACY_URL`, `CHA_LOGIN_USER` and `CHA_LOGIN_PASS`. AEE settings
use the `CHA_V2_AEE_*` environment variables documented in `.env.example`;
none are written into the result JSON or browser/server log.
