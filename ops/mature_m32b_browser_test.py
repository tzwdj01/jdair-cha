from __future__ import annotations

import argparse
import http.server
import json
import os
import threading
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


class ProductHandler(http.server.BaseHTTPRequestHandler):
    root: Path

    def log_message(self, *_args: Any) -> None:
        return

    def do_GET(self) -> None:
        mapping = {
            "/api/v2/realtime/assets/realtime.css": (
                self.root
                / "mature-modernization/v2/app/static/realtime/realtime.css",
                "text/css; charset=utf-8",
            ),
            "/api/v2/realtime/assets/realtime.js": (
                self.root
                / "mature-modernization/v2/app/static/realtime/realtime.js",
                "application/javascript; charset=utf-8",
            ),
            "/api/v2/realtime/assets/multistream_runtime.js": (
                self.root
                / (
                    "mature-modernization/v2/app/static/realtime/"
                    "multistream_runtime.js"
                ),
                "application/javascript; charset=utf-8",
            ),
        }
        if self.path == "/api/v2/realtime":
            path = (
                self.root
                / "mature-modernization/v2/app/templates/m3_realtime.html"
            )
            body = (
                path.read_text(encoding="utf-8")
                .replace("{{CHA_V2_VERSION}}", "0.6.0-test")
                .replace("{{CHA_V2_BUILD}}", "m3-four-grid-browser-test")
                .encode("utf-8")
            )
            content_type = "text/html; charset=utf-8"
        elif self.path == "/api/v2/realtime/assets/mcs8Client.js":
            body = b"// mcs8Client is provided by the browser test init script."
            content_type = "application/javascript; charset=utf-8"
        elif self.path in mapping:
            path, content_type = mapping[self.path]
            body = path.read_bytes()
        else:
            body = b"not found"
            content_type = "text/plain"
            self.send_response(404)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def wait_playing(page, count: int) -> dict[str, Any]:
    page.wait_for_function(
        """expected => {
          const snapshot = window.chaRealtimeInspection?.snapshot?.();
          return snapshot
            && snapshot.streams.length === expected
            && snapshot.streams.every(item => item.status === "PLAYING");
        }""",
        arg=count,
        timeout=30000,
    )
    return page.evaluate("() => window.chaRealtimeInspection.snapshot()")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the M3.2B four-grid product browser workflow."
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("m32b-browser-result.json"),
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=Path("m32b-four-grid.png"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    ProductHandler.root = root
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ProductHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}/api/v2/realtime"

    stages: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": True}
            chrome_path = Path(
                os.getenv(
                    "CHA_M3_CHROME_PATH",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                )
            )
            if chrome_path.is_file():
                launch_options["executable_path"] = str(chrome_path)
            browser = playwright.chromium.launch(**launch_options)
            context = browser.new_context(viewport={"width": 1600, "height": 980})
            context.add_init_script(
                path=str(root / "ops/mature_m32b_mock_browser.js")
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_selector(".device-row")
            stages.append(
                {
                    "stage": "devices_loaded",
                    "device_rows": page.locator(".device-row").count(),
                }
            )

            page.evaluate(
                "() => window.chaRealtimeInspection.addDevice('WXB320')"
            )
            first = wait_playing(page, 1)
            if first["layout"] != "single":
                raise RuntimeError("one stream did not use single layout")
            stages.append({"stage": "one_stream", "snapshot": first})

            page.evaluate(
                "() => window.chaRealtimeInspection.addDevice('WXB337')"
            )
            second = wait_playing(page, 2)
            if second["layout"] != "quad":
                raise RuntimeError("two streams did not use 2x2 layout")
            stages.append({"stage": "two_streams", "snapshot": second})

            page.evaluate(
                "() => window.chaRealtimeInspection.addDevice('WXB342')"
            )
            page.wait_for_function(
                """() => window.chaRealtimeInspection.snapshot().streams
                  .some(item => item.device_id === "WXB342"
                    && item.status === "FAILED")""",
                timeout=26000,
            )
            failed = page.evaluate(
                "() => window.chaRealtimeInspection.snapshot()"
            )
            stages.append(
                {
                    "stage": "first_frame_timeout_isolated",
                    "snapshot": failed,
                }
            )

            page.evaluate(
                "() => window.chaRealtimeInspection.addDevice('WXB345')"
            )
            page.wait_for_function(
                """() => {
                  const streams = window.chaRealtimeInspection.snapshot().streams;
                  return streams.length === 4
                    && streams.filter(item => item.status === "PLAYING").length === 3
                    && streams.some(item => item.status === "FAILED");
                }""",
                timeout=30000,
            )
            page.evaluate(
                """() => {
                  const stream = window.chaRealtimeInspection.snapshot().streams
                    .find(item => item.device_id === "WXB342");
                  return window.chaRealtimeInspection.retryTile(stream.stream_id);
                }"""
            )
            four = wait_playing(page, 4)
            stages.append({"stage": "four_streams", "snapshot": four})

            page.locator('[data-action="fullscreen"]').first.click()
            page.wait_for_function("() => Boolean(document.fullscreenElement)")
            fullscreen = page.evaluate(
                """() => ({
                  entered: Boolean(document.fullscreenElement),
                  playing: window.chaRealtimeInspection.snapshot().streams
                    .every(item => item.status === "PLAYING"),
                })"""
            )
            page.evaluate("() => document.exitFullscreen()")
            page.wait_for_function("() => !document.fullscreenElement")
            if not fullscreen["playing"]:
                raise RuntimeError("fullscreen interrupted a playing stream")
            stages.append({"stage": "fullscreen", **fullscreen})

            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.screenshot), full_page=True)

            first_id = next(
                item["stream_id"]
                for item in four["streams"]
                if item["device_id"] == "WXB320"
            )
            page.evaluate(
                "streamId => window.chaRealtimeInspection.closeTile(streamId)",
                first_id,
            )
            survivors = wait_playing(page, 3)
            stages.append(
                {"stage": "single_close_survivors", "snapshot": survivors}
            )

            page.evaluate(
                "() => window.chaRealtimeInspection.addDevice('WXB320')"
            )
            reopened = wait_playing(page, 4)
            stages.append({"stage": "reopen_four", "snapshot": reopened})

            page.evaluate("() => window.__m32bControlSocket.close()")
            page.wait_for_function(
                """() => {
                  const snapshot = window.chaRealtimeInspection.snapshot();
                  return snapshot.streams.length === 4
                    && snapshot.streams.every(
                      item => item.status === "DEGRADED"
                    )
                    && !document.querySelector(
                      "#reconnectButton"
                    ).classList.contains("hidden");
                }""",
                timeout=15000,
            )
            degraded = page.evaluate(
                "() => window.chaRealtimeInspection.snapshot()"
            )
            stages.append(
                {"stage": "control_disconnect_degraded", "snapshot": degraded}
            )
            page.locator("#reconnectButton").click()
            try:
                reconnected = wait_playing(page, 4)
            except Exception as error:
                diagnostic = page.evaluate(
                    """() => ({
                      snapshot: window.chaRealtimeInspection.snapshot(),
                      notice: document.querySelector("#globalNotice")
                        ?.textContent,
                      reconnectHidden: document.querySelector(
                        "#reconnectButton"
                      )?.classList.contains("hidden"),
                    })"""
                )
                raise RuntimeError(
                    f"explicit reconnect failed: {diagnostic}"
                ) from error
            stages.append(
                {"stage": "explicit_reconnect", "snapshot": reconnected}
            )

            page.evaluate(
                "() => window.chaRealtimeInspection.closeSession()"
            )
            page.wait_for_function(
                """() => {
                  const snapshot = window.chaRealtimeInspection.snapshot();
                  return !snapshot.session_id && snapshot.streams.length === 0;
                }""",
                timeout=15000,
            )
            stages.append(
                {
                    "stage": "session_closed",
                    "snapshot": page.evaluate(
                        "() => window.chaRealtimeInspection.snapshot()"
                    ),
                }
            )

            page.evaluate(
                "() => window.chaRealtimeInspection.addDevice('WXB320')"
            )
            wait_playing(page, 1)
            page.reload(wait_until="networkidle")
            cleanup_count = page.evaluate(
                "() => Number(sessionStorage.getItem('m32bCleanupCount') || 0)"
            )
            if cleanup_count < 1:
                raise RuntimeError("pagehide cleanup was not attempted")
            stages.append(
                {
                    "stage": "pagehide_cleanup",
                    "cleanup_count": cleanup_count,
                }
            )
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    result = {
        "status": "PASS" if not errors else "FAIL",
        "stages": stages,
        "page_errors": errors,
        "screenshot": str(args.screenshot),
    }
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise SystemExit("M3.2B browser test failed")


if __name__ == "__main__":
    main()
