# CHA v2 modular service

This service is deployed beside the existing CHA application. It owns only
the `/api/v2/` namespace and does not replace existing `/api/*` routes.

## M2 dashboard preview

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
- `GET /api/v2/docs`

M2 enables only `dashboard_v2`. It uses a narrow, read-only adapter to the
existing local service and forwards only the current browser's CHA session
cookie. It does not accept or persist user passwords. Metrics use bounded
process-local caches with stale fallback so a slow video/file source does not
block the whole dashboard. Device trend samples are stored in
`CHA_V2_DASHBOARD_STATE_DIR/device-trend.json`.

The legacy page and every legacy `/api/*` contract remain unchanged.

## Local test

```bash
python -m unittest discover -s tests -v
uvicorn app.main:app --host 127.0.0.1 --port 8791
```
