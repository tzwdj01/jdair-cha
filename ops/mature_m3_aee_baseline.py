from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


SENSITIVE_QUERY = re.compile(
    r"(?i)((?:token|pwd|password|authorization|cookie)=)[^&\s]+"
)


def safe_browser_log(message_type: str, text: str) -> str | None:
    relevant = (
        message_type == "error"
        or "geteway:" in text
        or '"method":"joinRoom"' in text
        or '"method":"newConsumer"' in text
        or '"method":"responseConnectMedia"' in text
        or "proto \"request\" event" in text
    )
    if not relevant:
        return None
    redacted = SENSITIVE_QUERY.sub(r"\1<redacted>", text)
    return f"{message_type}: {redacted[:1000]}"


def terminate_server_tree(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(server.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()


def wait_http(url: str, timeout_seconds: float = 20) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"local realtime page did not start: {url}")


def login_cha(base_url: str, username: str, password: str) -> tuple[str, str]:
    jar = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar)
    )
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/login",
        data=json.dumps(
            {"username": username, "password": password}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError("CHA login was not accepted")
    cookie = next(
        (
            item
            for item in jar
            if item.name == "jdair_mcs8_session"
        ),
        None,
    )
    if cookie is None or not cookie.value:
        raise RuntimeError("CHA login returned no session cookie")
    return cookie.name, cookie.value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a UTF-8 M3.1 AEE baseline without storing credentials."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CHA_M3_BASE_URL", "http://127.0.0.1:18892"),
    )
    parser.add_argument(
        "--device",
        default=os.environ.get("CHA_REALTIME_DEVICE", "WXB339"),
    )
    parser.add_argument(
        "--legacy-url",
        default=os.environ.get("CHA_M3_LEGACY_URL", ""),
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("m3-aee-realtime-baseline-result.json"),
    )
    parser.add_argument(
        "--stdout-log",
        type=Path,
        default=Path("m3-aee-realtime-browser.log"),
    )
    parser.add_argument(
        "--server-log",
        type=Path,
        default=Path("m3-aee-realtime-server.log"),
    )
    parser.add_argument("--screenshot", type=Path, default=None)
    parser.add_argument(
        "--server-command",
        default=os.environ.get("CHA_M3_SERVER_COMMAND", ""),
        help="Optional command used to start the local M3.1 service.",
    )
    args = parser.parse_args()
    username = os.environ.get("CHA_LOGIN_USER", "")
    password = os.environ.get("CHA_LOGIN_PASS", "")
    if not username or not password:
        raise SystemExit(
            "CHA_LOGIN_USER and CHA_LOGIN_PASS are required for the baseline"
        )
    if not args.legacy_url:
        raise SystemExit(
            "CHA_M3_LEGACY_URL or --legacy-url is required for the baseline"
        )
    cookie_name, cookie_value = login_cha(
        args.legacy_url,
        username,
        password,
    )

    server: subprocess.Popen[bytes] | None = None
    server_handle = None
    if args.server_command:
        args.server_log.parent.mkdir(parents=True, exist_ok=True)
        server_handle = args.server_log.open("wb")
        command: str | list[str]
        if os.name == "nt":
            command = args.server_command
        else:
            command = shlex.split(args.server_command)
        server = subprocess.Popen(
            command,
            shell=False,
            stdout=server_handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    console_lines: list[str] = []
    page_errors: list[str] = []
    first: dict[str, Any] = {}
    released: dict[str, Any] = {}
    second: dict[str, Any] = {}
    first_session_closed: dict[str, Any] = {}
    fresh_session_play: dict[str, Any] = {}
    final_closed: dict[str, Any] = {}
    failure: dict[str, str] | None = None
    try:
        wait_http(args.base_url.rstrip("/") + "/api/v2/realtime")
        with sync_playwright() as playwright:
            chrome_path = Path(
                os.environ.get(
                    "CHA_M3_CHROME_PATH",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                )
            )
            launch_options: dict[str, Any] = {
                "headless": True,
                "args": [
                    "--disable-gpu",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            }
            if chrome_path.is_file():
                launch_options["executable_path"] = str(chrome_path)
            browser = playwright.chromium.launch(
                **launch_options,
            )
            context = browser.new_context(
                viewport={"width": 1600, "height": 900}
            )
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
            page.on(
                "console",
                lambda message: (
                    console_lines.append(line)
                    if (
                        line := safe_browser_log(
                            message.type,
                            message.text,
                        )
                    )
                    else None
                ),
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(
                args.base_url.rstrip("/") + "/api/v2/realtime",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.select_option("#deviceSelect", args.device)
            page.click("#startButton")
            page.wait_for_function(
                """() => {
                  const video = document.getElementById('video');
                  return Boolean(
                    video.srcObject
                    && video.readyState >= 2
                    && video.videoWidth > 0
                    && video.videoHeight > 0
                  );
                }""",
                timeout=45000,
            )
            first = page.evaluate(
                """() => {
                  const video = document.getElementById('video');
                  const track = video.srcObject?.getVideoTracks?.()[0];
                  return {
                    ready_state: video.readyState,
                    width: video.videoWidth,
                    height: video.videoHeight,
                    current_time: video.currentTime,
                    track_state: track?.readyState || null,
                    session_status:
                      document.getElementById('sessionStatus')?.innerText || '',
                    playback_status:
                      document.getElementById('playbackStatus')?.innerText || '',
                  };
                }"""
            )
            page.wait_for_function(
                """() => {
                  const value =
                    document.getElementById('heartbeatStatus')?.innerText || '';
                  return value !== '未启动' && value !== '已启动';
                }""",
                timeout=20000,
            )
            first["heartbeat_status"] = page.locator(
                "#heartbeatStatus"
            ).inner_text()
            if args.screenshot:
                page.screenshot(path=str(args.screenshot), full_page=True)

            page.click("#stopStreamButton")
            page.wait_for_function(
                "() => document.getElementById('playbackStatus').innerText === 'CLOSED'",
                timeout=20000,
            )
            released: dict[str, Any] = page.evaluate(
                """() => ({
                  session_status:
                    document.getElementById('sessionStatus')?.innerText || '',
                  playback_status:
                    document.getElementById('playbackStatus')?.innerText || '',
                  connection_status:
                    document.getElementById('connectionStatus')?.innerText || '',
                  has_src_object: Boolean(
                    document.getElementById('video').srcObject
                  ),
                })"""
            )
            page.click("#startButton")
            page.wait_for_function(
                """() => {
                  const video = document.getElementById('video');
                  return Boolean(video.srcObject && video.videoWidth > 0);
                }""",
                timeout=45000,
            )
            second = page.evaluate(
                """() => ({
                  width: document.getElementById('video').videoWidth,
                  height: document.getElementById('video').videoHeight,
                  playback_status:
                    document.getElementById('playbackStatus')?.innerText || '',
                })"""
            )
            page.click("#closeSessionButton")
            page.wait_for_function(
                "() => document.getElementById('sessionStatus').innerText === 'CLOSED'",
                timeout=20000,
            )
            first_session_closed = page.evaluate(
                """() => ({
                  session_status:
                    document.getElementById('sessionStatus')?.innerText || '',
                  playback_status:
                    document.getElementById('playbackStatus')?.innerText || '',
                  has_src_object: Boolean(
                    document.getElementById('video').srcObject
                  ),
                })"""
            )
            page.click("#startButton")
            page.wait_for_function(
                """() => {
                  const video = document.getElementById('video');
                  return Boolean(
                    video.srcObject
                    && video.readyState >= 2
                    && video.videoWidth > 0
                    && video.videoHeight > 0
                  );
                }""",
                timeout=45000,
            )
            fresh_session_play = page.evaluate(
                """() => {
                  const video = document.getElementById('video');
                  const track = video.srcObject?.getVideoTracks?.()[0];
                  return {
                    width: video.videoWidth,
                    height: video.videoHeight,
                    track_state: track?.readyState || null,
                    session_status:
                      document.getElementById('sessionStatus')?.innerText || '',
                    playback_status:
                      document.getElementById('playbackStatus')?.innerText || '',
                  };
                }"""
            )
            page.click("#closeSessionButton")
            page.wait_for_function(
                "() => document.getElementById('sessionStatus').innerText === 'CLOSED'",
                timeout=20000,
            )
            final_closed = page.evaluate(
                """() => ({
                  session_status:
                    document.getElementById('sessionStatus')?.innerText || '',
                  playback_status:
                    document.getElementById('playbackStatus')?.innerText || '',
                  has_src_object: Boolean(
                    document.getElementById('video').srcObject
                  ),
                })"""
            )
            context.close()
            browser.close()
    except Exception as exc:
        failure = {
            "type": type(exc).__name__,
            "message": SENSITIVE_QUERY.sub(
                r"\1<redacted>",
                str(exc),
            )[:500],
        }
    finally:
        if server is not None:
            terminate_server_tree(server)
        if server_handle is not None:
            server_handle.close()

    args.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    args.stdout_log.write_text(
        "\n".join(console_lines) + ("\n" if console_lines else ""),
        encoding="utf-8",
    )
    result = {
        "device": args.device,
        "first_play": first,
        "first_release": released,
        "second_play": second,
        "first_session_closed": first_session_closed,
        "fresh_session_play": fresh_session_play,
        "final_closed": final_closed,
        "failure": failure,
        "page_errors": page_errors,
        "browser_log": str(args.stdout_log),
        "server_log": str(args.server_log) if args.server_command else None,
        "screenshot": str(args.screenshot) if args.screenshot else None,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if failure:
        raise SystemExit(
            f"M3.1 realtime lifecycle validation failed: "
            f"{failure['type']}: {failure['message']}"
        )
    if page_errors:
        raise SystemExit("browser page errors were recorded")
    if (
        first["width"] <= 0
        or first["height"] <= 0
        or not first.get("heartbeat_status")
        or released["session_status"] != "READY"
        or released["playback_status"] != "CLOSED"
        or released["has_src_object"]
        or second["width"] <= 0
        or first_session_closed["has_src_object"]
        or fresh_session_play["width"] <= 0
        or fresh_session_play["track_state"] != "live"
        or final_closed["has_src_object"]
    ):
        raise SystemExit("M3.1 realtime lifecycle validation failed")


if __name__ == "__main__":
    main()
