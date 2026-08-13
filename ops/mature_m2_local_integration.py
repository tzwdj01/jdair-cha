from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path


def wait_for_health(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise RuntimeError("local v2 service did not become healthy")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    v2_root = root / "mature-modernization" / "v2"
    python = root / "mature-modernization" / ".venv-v2" / "Scripts" / "python.exe"
    with tempfile.TemporaryDirectory(prefix="cha-m2-state-") as state_dir:
        env = os.environ.copy()
        env.update(
            {
                "CHA_V2_FEATURE_DASHBOARD_V2": "true",
                "CHA_V2_LEGACY_BASE_URL": "http://cha.jdair.top",
                "CHA_V2_LEGACY_TIMEOUT_SECONDS": "25",
                "CHA_V2_ALLOWED_HOSTS": "127.0.0.1,localhost",
                "CHA_V2_DASHBOARD_STATE_DIR": state_dir,
            }
        )
        process = subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18891",
            ],
            cwd=v2_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            wait_for_health("http://127.0.0.1:18891/api/v2/health")
            cookie_jar = CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar)
            )
            login_request = urllib.request.Request(
                "http://cha.jdair.top/api/login",
                data=json.dumps(
                    {
                        "username": os.environ["CHA_LOGIN_USER"],
                        "password": os.environ["CHA_LOGIN_PASS"],
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(login_request, timeout=60) as login_response:
                login_payload = json.loads(login_response.read())
            if not login_payload.get("ok"):
                raise RuntimeError("CHA login was not accepted")
            cookie_header = "; ".join(
                f"{cookie.name}={cookie.value}" for cookie in cookie_jar
            )
            if not cookie_header:
                raise RuntimeError("CHA login returned no session cookie")

            page_request = urllib.request.Request(
                "http://127.0.0.1:18891/api/v2/dashboard",
                headers={"Cookie": cookie_header},
            )
            with opener.open(page_request, timeout=30) as page_response:
                page_status = page_response.status
                page_text = page_response.read().decode("utf-8")
            if page_status != 200 or "CHA 态势总览" not in page_text:
                raise RuntimeError("dashboard page contract failed")

            attempts = []
            for attempt in range(1, 4):
                started = time.perf_counter()
                overview_url = (
                    "http://127.0.0.1:18891/api/v2/dashboard/overview?"
                    + urllib.parse.urlencode({"days": 3})
                )
                overview_request = urllib.request.Request(
                    overview_url,
                    headers={"Cookie": cookie_header},
                )
                with opener.open(overview_request, timeout=60) as response:
                    payload = json.loads(response.read())
                if not payload.get("ok"):
                    raise RuntimeError("dashboard API returned ok=false")
                snapshot = payload["data"]
                unavailable = [
                    item["name"]
                    for item in snapshot["freshness"]
                    if item["status"] == "unavailable"
                ]
                attempts.append(
                    {
                        "attempt": attempt,
                        "elapsed_ms": round(
                            (time.perf_counter() - started) * 1000,
                            1,
                        ),
                        "devices": snapshot["summary"]["devices"],
                        "files": snapshot["summary"]["files"]["count"],
                        "flights": snapshot["summary"]["operations"][
                            "flights_today"
                        ],
                        "routines": snapshot["summary"]["operations"][
                            "routine_tasks_today"
                        ],
                        "trend_points": len(snapshot["video_trend"]),
                        "unavailable": unavailable,
                    }
                )
                if not unavailable:
                    break
                time.sleep(10)

            result = {
                "page_status": page_status,
                "attempts": attempts,
            }
            print(json.dumps(result, ensure_ascii=False))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps(
                {"error": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise
