from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


SENSITIVE = re.compile(
    r"(?i)((?:token|pwd|password|authorization|cookie)=)[^&\s]+"
)


def redact(value: object) -> str:
    return SENSITIVE.sub(r"\1<redacted>", str(value))[:1200]


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()


def wait_http(url: str, timeout_seconds: float = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status in {200, 404}:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"local M3.2B service did not start: {url}")


def login_and_devices(
    base_url: str,
    username: str,
    password: str,
) -> tuple[str, str, list[dict[str, Any]]]:
    jar = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar)
    )
    login = urllib.request.Request(
        base_url.rstrip("/") + "/api/login",
        data=json.dumps(
            {"username": username, "password": password}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(login, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError("CHA login was not accepted")
    cookie = next(
        (item for item in jar if item.name == "jdair_mcs8_session"),
        None,
    )
    if cookie is None or not cookie.value:
        raise RuntimeError("CHA login returned no session cookie")
    with opener.open(
        base_url.rstrip("/") + "/api/devices",
        timeout=30,
    ) as response:
        devices = json.loads(response.read().decode("utf-8"))
    if not isinstance(devices, list):
        raise RuntimeError("CHA device list was invalid")
    return cookie.name, cookie.value, devices


def process_sample(pid: int) -> dict[str, Any]:
    if os.name != "nt":
        return {}
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"$p=Get-Process -Id {pid};"
                "[pscustomobject]@{"
                "cpu=$p.CPU;"
                "working_set=$p.WorkingSet64;"
                "private_memory=$p.PrivateMemorySize64"
                "}|ConvertTo-Json -Compress"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the formal M3.2B product page with real AEE video."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("CHA_M32B_BASE_URL", "http://127.0.0.1:18895"),
    )
    parser.add_argument(
        "--legacy-url",
        default=os.getenv("CHA_M32B_LEGACY_URL", ""),
    )
    parser.add_argument(
        "--devices",
        default=os.getenv("CHA_M32B_DEVICES", ""),
    )
    parser.add_argument(
        "--observe-seconds",
        type=int,
        default=int(os.getenv("CHA_M32B_OBSERVE_SECONDS", "600")),
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("m32b-real-product-result.json"),
    )
    parser.add_argument(
        "--browser-log",
        type=Path,
        default=Path("m32b-real-product-browser.log"),
    )
    parser.add_argument(
        "--server-log",
        type=Path,
        default=Path("m32b-real-product-server.log"),
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=Path("m32b-real-four-grid.png"),
    )
    args = parser.parse_args()

    username = os.getenv("CHA_LOGIN_USER", "")
    password = os.getenv("CHA_LOGIN_PASS", "")
    if not username or not password or not args.legacy_url:
        raise SystemExit(
            "CHA_LOGIN_USER, CHA_LOGIN_PASS and CHA_M32B_LEGACY_URL are required"
        )
    required_aee = [
        "CHA_V2_AEE_API_BASE_URL",
        "CHA_V2_AEE_ORIGIN",
        "CHA_V2_AEE_GATEWAY_HOST",
        "CHA_V2_AEE_USERNAME",
        "CHA_V2_AEE_PASSWORD",
    ]
    missing = [name for name in required_aee if not os.getenv(name)]
    if missing:
        raise SystemExit("missing AEE environment: " + ", ".join(missing))

    cookie_name, cookie_value, catalog = login_and_devices(
        args.legacy_url,
        username,
        password,
    )
    requested = [
        item.strip() for item in args.devices.split(",") if item.strip()
    ]
    online = [
        str(item.get("devId") or "")
        for item in catalog
        if isinstance(item, dict)
        and item.get("online")
        and item.get("devId")
    ]
    devices = requested or online[:4]
    if len(devices) < 4:
        raise SystemExit("four explicitly safe online devices are required")
    devices = devices[:4]
    unavailable = [item for item in devices if item not in online]
    if unavailable:
        raise SystemExit(
            "requested devices are not currently online: "
            + ", ".join(unavailable)
        )

    root = Path(__file__).resolve().parents[1]
    v2 = root / "mature-modernization" / "v2"
    python = (
        root
        / "mature-modernization"
        / ".venv-m3"
        / "Scripts"
        / "python.exe"
    )
    if not python.is_file():
        python = Path(os.sys.executable)
    port = int(args.base_url.rsplit(":", 1)[1])
    env = os.environ.copy()
    env.update(
        {
            "CHA_V2_FEATURE_REALTIME_READONLY": "true",
            "CHA_V2_FEATURE_REALTIME_AUDIO": "false",
            "CHA_V2_FEATURE_REALTIME_CONTROL": "false",
            "CHA_V2_FEATURE_ACCOUNT_POOL_V2": "false",
            "CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION": "4",
            "CHA_V2_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "CHA_V2_LEGACY_BASE_URL": args.legacy_url.rstrip("/"),
        }
    )
    args.server_log.parent.mkdir(parents=True, exist_ok=True)
    server_handle = args.server_log.open("wb")
    server = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            str(v2),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=v2,
        env=env,
        stdout=server_handle,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    console: list[str] = []
    page_errors: list[str] = []
    stages: list[dict[str, Any]] = []
    performance: list[dict[str, Any]] = []
    failure: dict[str, str] | None = None
    final_session: dict[str, Any] = {}
    try:
        wait_http(args.base_url.rstrip("/") + "/api/v2/realtime")
        with sync_playwright() as playwright:
            launch: dict[str, Any] = {
                "headless": True,
                "args": [
                    "--disable-gpu",
                    "--autoplay-policy=no-user-gesture-required",
                    "--enable-precise-memory-info",
                ],
            }
            chrome = Path(
                os.getenv(
                    "CHA_M3_CHROME_PATH",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                )
            )
            if chrome.is_file():
                launch["executable_path"] = str(chrome)
            browser = playwright.chromium.launch(**launch)
            context = browser.new_context(viewport={"width": 1600, "height": 980})
            context.add_cookies(
                [
                    {
                        "name": cookie_name,
                        "value": cookie_value,
                        "url": args.base_url.rstrip("/") + "/",
                        "httpOnly": True,
                        "sameSite": "Lax",
                    }
                ]
            )
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            cdp.send("Performance.enable")
            page.on(
                "console",
                lambda message: console.append(
                    f"{message.type}: {redact(message.text)}"
                ),
            )
            page.on("pageerror", lambda error: page_errors.append(redact(error)))
            page.goto(
                args.base_url.rstrip("/") + "/api/v2/realtime",
                wait_until="networkidle",
                timeout=30000,
            )
            page.wait_for_selector(".device-row")

            for index, device_id in enumerate(devices, start=1):
                started = round(time.time() * 1000)
                page.evaluate(
                    "device => window.chaRealtimeInspection.addDevice(device)",
                    device_id,
                )
                page.wait_for_function(
                    """device => {
                      const item = window.chaRealtimeInspection.snapshot().streams
                        .find(stream => stream.device_id === device);
                      return item?.status === "PLAYING"
                        && item?.track_state === "live";
                    }""",
                    arg=device_id,
                    timeout=45000,
                )
                snapshot = page.evaluate(
                    "() => window.chaRealtimeInspection.snapshot()"
                )
                stream = next(
                    item
                    for item in snapshot["streams"]
                    if item["device_id"] == device_id
                )
                stages.append(
                    {
                        "stage": f"open_{index}",
                        "device_id": device_id,
                        "first_frame_latency_ms": (
                            stream["first_frame_at"] - started
                        ),
                        "snapshot": snapshot,
                    }
                )

            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.screenshot), full_page=True)

            deadline = time.monotonic() + max(0, args.observe_seconds)
            while time.monotonic() < deadline:
                snapshot = page.evaluate(
                    "() => window.chaRealtimeInspection.snapshot()"
                )
                if (
                    len(snapshot["streams"]) != 4
                    or any(
                        item["status"] != "PLAYING"
                        or item["track_state"] != "live"
                        for item in snapshot["streams"]
                    )
                ):
                    raise RuntimeError("four-stream product page became unstable")
                metrics = {
                    item["name"]: item["value"]
                    for item in cdp.send("Performance.getMetrics")["metrics"]
                }
                performance.append(
                    {
                        "at_ms": round(time.time() * 1000),
                        "browser": {
                            "heap_used_bytes": page.evaluate(
                                "() => performance.memory?.usedJSHeapSize ?? null"
                            ),
                            "heap_total_bytes": page.evaluate(
                                "() => performance.memory?.totalJSHeapSize ?? null"
                            ),
                            "task_duration_seconds": metrics.get("TaskDuration"),
                            "nodes": metrics.get("Nodes"),
                        },
                        "cha_server": process_sample(server.pid),
                    }
                )
                time.sleep(min(5, max(1, args.observe_seconds)))

            before_close = page.evaluate(
                "() => window.chaRealtimeInspection.snapshot()"
            )
            target = next(
                item
                for item in before_close["streams"]
                if item["device_id"] == devices[0]
            )
            page.evaluate(
                "id => window.chaRealtimeInspection.closeTile(id)",
                target["stream_id"],
            )
            page.wait_for_function(
                """device => {
                  const streams = window.chaRealtimeInspection.snapshot().streams;
                  return streams.length === 3
                    && !streams.some(item => item.device_id === device)
                    && streams.every(item => item.status === "PLAYING"
                      && item.track_state === "live");
                }""",
                arg=devices[0],
                timeout=20000,
            )
            stages.append(
                {
                    "stage": "single_close",
                    "device_id": devices[0],
                    "snapshot": page.evaluate(
                        "() => window.chaRealtimeInspection.snapshot()"
                    ),
                }
            )

            reopened_started = round(time.time() * 1000)
            page.evaluate(
                "device => window.chaRealtimeInspection.addDevice(device)",
                devices[0],
            )
            page.wait_for_function(
                """() => {
                  const streams = window.chaRealtimeInspection.snapshot().streams;
                  return streams.length === 4
                    && streams.every(item => item.status === "PLAYING"
                      && item.track_state === "live");
                }""",
                timeout=45000,
            )
            reopened = page.evaluate(
                "() => window.chaRealtimeInspection.snapshot()"
            )
            reopened_stream = next(
                item
                for item in reopened["streams"]
                if item["device_id"] == devices[0]
            )
            stages.append(
                {
                    "stage": "reopen",
                    "device_id": devices[0],
                    "first_frame_latency_ms": (
                        reopened_stream["first_frame_at"] - reopened_started
                    ),
                    "snapshot": reopened,
                }
            )

            session_id = reopened["session_id"]
            page.evaluate(
                "() => window.chaRealtimeInspection.closeSession()"
            )
            page.wait_for_function(
                """() => {
                  const state = window.chaRealtimeInspection.snapshot();
                  return !state.session_id && state.streams.length === 0;
                }""",
                timeout=30000,
            )
            final_session = page.evaluate(
                """async id => {
                  const response = await fetch(`/api/v2/realtime/sessions/${id}`);
                  return (await response.json()).data;
                }""",
                session_id,
            )
            stages.append(
                {
                    "stage": "session_closed",
                    "snapshot": page.evaluate(
                        "() => window.chaRealtimeInspection.snapshot()"
                    ),
                    "server_session": final_session,
                }
            )
            context.close()
            browser.close()
    except Exception as exc:
        failure = {
            "type": type(exc).__name__,
            "message": redact(exc),
        }
    finally:
        terminate_tree(server)
        server_handle.close()

    args.browser_log.write_text(
        "\n".join(console) + ("\n" if console else ""),
        encoding="utf-8",
    )
    result = {
        "status": (
            "PASS"
            if not failure
            and not page_errors
            and final_session.get("status") == "CLOSED"
            else "FAIL"
        ),
        "devices": devices,
        "observe_seconds": args.observe_seconds,
        "stages": stages,
        "performance_samples": performance,
        "final_session": final_session,
        "page_errors": page_errors,
        "failure": failure,
        "files": {
            "browser_log": str(args.browser_log),
            "server_log": str(args.server_log),
            "screenshot": str(args.screenshot),
        },
    }
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit("M3.2B real product validation failed")


if __name__ == "__main__":
    main()
