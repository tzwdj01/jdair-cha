# CHA v2 foundation service

This service is deployed beside the existing CHA application. It owns only
the `/api/v2/` namespace and does not replace existing `/api/*` routes.

## Foundation endpoints

- `GET /api/v2/health`
- `GET /api/v2/health/live`
- `GET /api/v2/health/ready`
- `GET /api/v2/health/upstreams`
- `GET /api/v2/system/version`
- `GET /api/v2/system/features`
- `GET /api/v2/dashboard/overview` (feature gated)
- `GET /api/v2/docs`

All business feature flags are disabled by default. The first dashboard
contract uses a narrow, read-only adapter to the existing local service and
forwards only the current browser's CHA session cookie.

## Local test

```bash
python -m unittest discover -s tests -v
uvicorn app.main:app --host 127.0.0.1 --port 8791
```
