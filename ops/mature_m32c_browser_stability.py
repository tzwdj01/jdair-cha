from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from mature_m32b_browser_test import ProductHandler, wait_playing


def metric_map(session) -> dict[str, float]:
    result = session.send("Performance.getMetrics")
    return {
        item["name"]: item["value"]
        for item in result.get("metrics", [])
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exercise repeated M3 realtime browser lifecycles."
    )
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("m32c-browser-stability-result.json"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    ProductHandler.root = root
    server = ProductHandler.server = None
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProductHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}/api/v2/realtime"

    samples: list[dict[str, Any]] = []
    page_errors: list[str] = []
    console_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            launch: dict[str, Any] = {"headless": True}
            chrome_path = Path(
                os.getenv(
                    "CHA_M3_CHROME_PATH",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                )
            )
            if chrome_path.is_file():
                launch["executable_path"] = str(chrome_path)
            browser = playwright.chromium.launch(**launch)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.add_init_script(
                path=str(root / "ops/mature_m32b_mock_browser.js")
            )
            context.add_init_script(
                "window.__m32bSkipFirstFrameTimeout = true;"
            )
            page = context.new_page()
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text)
                    if message.type == "error"
                    else None
                ),
            )
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_selector(".device-row")
            cdp = context.new_cdp_session(page)
            cdp.send("Performance.enable")
            cdp.send("HeapProfiler.enable")

            devices = ("WXB320", "WXB337", "WXB342", "WXB345")
            for cycle in range(1, args.cycles + 1):
                for device_id in devices:
                    page.evaluate(
                        "id => window.chaRealtimeInspection.addDevice(id)",
                        device_id,
                    )
                wait_playing(page, 4)
                before_close = page.evaluate(
                    "() => window.chaRealtimeInspection.snapshot()"
                )
                page.evaluate(
                    "() => window.chaRealtimeInspection.closeSession()"
                )
                page.wait_for_function(
                    """() => {
                      const value = window.chaRealtimeInspection.snapshot();
                      return !value.session_id && value.streams.length === 0;
                    }""",
                    timeout=15000,
                )
                cdp.send("HeapProfiler.collectGarbage")
                after = metric_map(cdp)
                runtime = page.evaluate("() => ({...window.__m32bMetrics})")
                browser_objects = page.evaluate(
                    """() => ({
                      liveDomNodes: document.querySelectorAll("*").length,
                      clientHandlers: window.__m32bClient?.handlers?.size || 0,
                      clientStreams: window.__m32bClient?.streams?.size || 0,
                    })"""
                )
                if runtime["tracksActive"] != 0:
                    raise RuntimeError(
                        f"cycle {cycle} retained media tracks: {runtime}"
                    )
                if runtime["clientsActive"] != 0:
                    raise RuntimeError(
                        f"cycle {cycle} retained SDK clients: {runtime}"
                    )
                if runtime["socketsActive"] != 0:
                    raise RuntimeError(
                        f"cycle {cycle} retained control sockets: {runtime}"
                    )
                if browser_objects["clientHandlers"] != 0:
                    raise RuntimeError(
                        f"cycle {cycle} retained SDK listeners: "
                        f"{browser_objects}"
                    )
                if browser_objects["clientStreams"] != 0:
                    raise RuntimeError(
                        f"cycle {cycle} retained consumer records: "
                        f"{browser_objects}"
                    )
                samples.append(
                    {
                        "cycle": cycle,
                        "playing_streams": len(before_close["streams"]),
                        "heap_used_bytes": int(
                            after.get("JSHeapUsedSize", 0)
                        ),
                        "nodes": int(after.get("Nodes", 0)),
                        "runtime": runtime,
                        "browser_objects": browser_objects,
                    }
                )

            heap = [item["heap_used_bytes"] for item in samples]
            nodes = [item["nodes"] for item in samples]
            if heap and heap[-1] > heap[0] + 4 * 1024 * 1024:
                raise RuntimeError(f"heap trend exceeded guardrail: {heap}")
            if nodes and nodes[-1] > nodes[0] + 200:
                raise RuntimeError(f"DOM node trend exceeded guardrail: {nodes}")
            live_nodes = [
                item["browser_objects"]["liveDomNodes"] for item in samples
            ]
            if live_nodes and len(set(live_nodes)) != 1:
                raise RuntimeError(
                    f"live DOM node count changed after cleanup: {live_nodes}"
                )
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    result = {
        "status": (
            "PASS" if not page_errors and not console_errors else "FAIL"
        ),
        "cycles": args.cycles,
        "samples": samples,
        "page_errors": page_errors,
        "console_errors": console_errors,
    }
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit("M3.2C browser stability failed")


if __name__ == "__main__":
    main()
