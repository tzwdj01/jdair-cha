from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


BASE_URL = "http://cha.jdair.top"


def open_json(
    opener: urllib.request.OpenerDirector,
    path: str,
    *,
    timeout: int = 60,
) -> tuple[int, dict]:
    with opener.open(BASE_URL + path, timeout=timeout) as response:
        return response.status, json.loads(response.read())


def main() -> None:
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    login_request = urllib.request.Request(
        BASE_URL + "/api/login",
        data=json.dumps(
            {
                "username": os.environ["CHA_LOGIN_USER"],
                "password": os.environ["CHA_LOGIN_PASS"],
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(login_request, timeout=60) as response:
        login_payload = json.loads(response.read())
    if not login_payload.get("ok"):
        raise SystemExit("CHA login failed")

    with opener.open(BASE_URL + "/api/v2/dashboard", timeout=30) as response:
        page_status = response.status
        page = response.read().decode("utf-8")
    if page_status != 200 or "CHA 态势总览" not in page:
        raise SystemExit("M2 dashboard page failed")

    attempts = []
    snapshot = None
    for attempt in range(1, 5):
        started = time.perf_counter()
        path = "/api/v2/dashboard/overview?" + urllib.parse.urlencode(
            {"days": 3}
        )
        status, payload = open_json(opener, path)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        if status != 200 or not payload.get("ok"):
            raise SystemExit("M2 dashboard API failed")
        snapshot = payload["data"]
        unavailable = [
            item["name"]
            for item in snapshot["freshness"]
            if item["status"] == "unavailable"
        ]
        attempts.append(
            {
                "attempt": attempt,
                "elapsed_ms": elapsed_ms,
                "unavailable": unavailable,
            }
        )
        if not unavailable:
            break
        time.sleep(10)

    if snapshot is None:
        raise SystemExit("M2 snapshot missing")

    endpoint_checks = {}
    for endpoint in (
        "device-trend",
        "video-trend",
        "geography",
        "coverage",
        "exceptions",
        "freshness",
    ):
        started = time.perf_counter()
        status, payload = open_json(
            opener,
            f"/api/v2/dashboard/{endpoint}",
        )
        endpoint_checks[endpoint] = {
            "status": status,
            "ok": bool(payload.get("ok")),
            "elapsed_ms": round(
                (time.perf_counter() - started) * 1000,
                1,
            ),
        }

    result = {
        "page_status": page_status,
        "attempts": attempts,
        "summary": snapshot["summary"],
        "trend_points": len(snapshot["video_trend"]),
        "geography_rows": len(snapshot["geography"]),
        "map_points": len(snapshot["map_points"]),
        "exception_total": snapshot["exceptions"]["total"],
        "freshness": [
            {
                "name": item["name"],
                "status": item["status"],
                "cache_hit": item["cache_hit"],
                "latency_ms": item["latency_ms"],
            }
            for item in snapshot["freshness"]
        ],
        "endpoint_checks": endpoint_checks,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
