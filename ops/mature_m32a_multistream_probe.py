from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


SENSITIVE = re.compile(
    r"(?i)((?:token|pwd|password|authorization|cookie)=)[^&\s]+"
)


def wait_http(url: str, timeout_seconds: float = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"probe server did not start: {url}")


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


def stream_snapshot(page, device_id: str) -> dict[str, Any]:
    snapshot = page.evaluate("() => window.m32aProbe.snapshot()")
    return next(
        item
        for item in snapshot["streams"]
        if item["device_id"] == device_id
    )


def assert_playing(page, expected: list[str]) -> None:
    snapshot = page.evaluate("() => window.m32aProbe.snapshot()")
    by_device = {item["device_id"]: item for item in snapshot["streams"]}
    for device_id in expected:
        item = by_device[device_id]
        if item["status"] != "PLAYING" or item["track_state"] != "live":
            raise RuntimeError(f"{device_id} was not independently PLAYING")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run isolated progressive AEE multi-stream validation."
    )
    parser.add_argument(
        "--devices",
        default=os.getenv("CHA_M32A_DEVICES", ""),
        help="Comma-separated, explicitly approved online device IDs.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:18893")
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("m32a-aee-multistream-result.json"),
    )
    parser.add_argument(
        "--browser-log",
        type=Path,
        default=Path("m32a-aee-multistream-browser.log"),
    )
    parser.add_argument(
        "--server-log",
        type=Path,
        default=Path("m32a-aee-multistream-server.log"),
    )
    parser.add_argument(
        "--observe-seconds",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--audio-device",
        default="",
        help="Optionally validate receive-only audio on one selected device.",
    )
    parser.add_argument(
        "--python",
        default=os.getenv("CHA_M32A_PYTHON", ""),
        help="Python executable with the locked M3 runtime dependencies.",
    )
    args = parser.parse_args()
    devices = [item.strip() for item in args.devices.split(",") if item.strip()]
    if not devices:
        raise SystemExit("at least one explicitly approved device is required")
    if len(devices) > 9:
        devices = devices[:9]
    if args.audio_device and args.audio_device not in devices:
        raise SystemExit("--audio-device must also be present in --devices")

    root = Path(__file__).resolve().parents[1]
    v2 = root / "mature-modernization" / "v2"
    port = int(args.base_url.rsplit(":", 1)[1])
    python_executable = args.python or str(
        root
        / "mature-modernization"
        / ".venv-m3"
        / "Scripts"
        / "python.exe"
    )
    if not Path(python_executable).is_file():
        python_executable = os.sys.executable
    env = os.environ.copy()
    env["CHA_M32A_DEVICES"] = ",".join(devices)
    env.setdefault("CHA_V2_ALLOWED_HOSTS", "127.0.0.1,localhost")
    args.server_log.parent.mkdir(parents=True, exist_ok=True)
    server_handle = args.server_log.open("wb")
    server = subprocess.Popen(
        [
            python_executable,
            "-m",
            "uvicorn",
            "mature_m32a_probe_app:app",
            "--app-dir",
            str(root / "ops"),
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
    failure: dict[str, str] | None = None
    final_release: dict[str, Any] = {}
    process_samples: list[dict[str, Any]] = []
    try:
        wait_http(args.base_url + "/probe")
        with sync_playwright() as playwright:
            chrome_path = Path(
                os.getenv(
                    "CHA_M3_CHROME_PATH",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                )
            )
            options: dict[str, Any] = {
                "headless": True,
                "args": [
                    "--disable-gpu",
                    "--autoplay-policy=no-user-gesture-required",
                    "--enable-precise-memory-info",
                ],
            }
            if chrome_path.is_file():
                options["executable_path"] = str(chrome_path)
            browser = playwright.chromium.launch(**options)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            cdp.send("Performance.enable")
            page.on(
                "console",
                lambda message: console.append(
                    SENSITIVE.sub(
                        r"\1<redacted>",
                        f"{message.type}: {message.text}",
                    )[:1200]
                ),
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(args.base_url + "/probe", wait_until="domcontentloaded")
            initialized = page.evaluate(
                "() => window.m32aProbe.initialize()"
            )
            stages.append({"stage": "connected", "snapshot": initialized})

            active: list[str] = []
            targets = list(range(1, len(devices) + 1))

            for target_count in targets:
                while len(active) < target_count:
                    device_id = devices[len(active)]
                    opened = page.evaluate(
                        "(device) => window.m32aProbe.openDevice(device)",
                        device_id,
                    )
                    active.append(device_id)
                    assert_playing(page, active)
                    stages.append(
                        {
                            "stage": f"open_{len(active)}",
                            "device_id": device_id,
                            "stream": opened,
                            "browser": page.evaluate(
                                "() => window.m32aProbe.snapshot()"
                            ),
                            "server": page.evaluate(
                                "() => window.m32aProbe.serverMetrics()"
                            ),
                        }
                    )

                survivor_checkpoints = {
                    item for item in (4, 6, 9, len(devices)) if item >= 2
                }
                if target_count in survivor_checkpoints:
                    close_id = active[0]
                    survivor = active[1:]
                    closed = page.evaluate(
                        "(device) => window.m32aProbe.closeDevice(device)",
                        close_id,
                    )
                    assert_playing(page, survivor)
                    stages.append(
                        {
                            "stage": f"close_{close_id}_with_{len(survivor)}_survivors",
                            "closed": closed,
                            "survivors": [
                                stream_snapshot(page, item) for item in survivor
                            ],
                            "browser": page.evaluate(
                                "() => window.m32aProbe.snapshot()"
                            ),
                            "server": page.evaluate(
                                "() => window.m32aProbe.serverMetrics()"
                            ),
                        }
                    )
                    reopened = page.evaluate(
                        "(device) => window.m32aProbe.openDevice(device)",
                        close_id,
                    )
                    assert_playing(page, active)
                    stages.append(
                        {
                            "stage": f"reopen_{close_id}",
                            "stream": reopened,
                            "browser": page.evaluate(
                                "() => window.m32aProbe.snapshot()"
                            ),
                            "server": page.evaluate(
                                "() => window.m32aProbe.serverMetrics()"
                            ),
                        }
                    )

            if args.audio_device:
                audio = page.evaluate(
                    "(device) => window.m32aProbe.probeAudio(device)",
                    args.audio_device,
                )
                assert_playing(page, active)
                stages.append(
                    {
                        "stage": "audio_receive_only",
                        "audio": audio,
                        "browser": page.evaluate(
                            "() => window.m32aProbe.snapshot()"
                        ),
                        "server": page.evaluate(
                            "() => window.m32aProbe.serverMetrics()"
                        ),
                    }
                )

            if args.observe_seconds > 0:
                deadline = time.monotonic() + args.observe_seconds
                while time.monotonic() < deadline:
                    assert_playing(page, active)
                    browser_metrics = page.evaluate(
                        "() => window.m32aProbe.snapshot().browser"
                    )
                    cdp_metrics = {
                        item["name"]: item["value"]
                        for item in cdp.send("Performance.getMetrics")[
                            "metrics"
                        ]
                    }
                    browser_metrics.update(
                        {
                            "task_duration_seconds": cdp_metrics.get(
                                "TaskDuration"
                            ),
                            "script_duration_seconds": cdp_metrics.get(
                                "ScriptDuration"
                            ),
                            "layout_duration_seconds": cdp_metrics.get(
                                "LayoutDuration"
                            ),
                            "nodes": cdp_metrics.get("Nodes"),
                        }
                    )
                    process = subprocess.run(
                        [
                            "powershell",
                            "-NoProfile",
                            "-Command",
                            (
                                f"$p=Get-Process -Id {server.pid};"
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
                    server_metrics = (
                        json.loads(process.stdout)
                        if process.returncode == 0 and process.stdout.strip()
                        else {}
                    )
                    process_samples.append(
                        {
                            "at_ms": round(time.time() * 1000),
                            "browser": browser_metrics,
                            "cha_probe_server": server_metrics,
                        }
                    )
                    time.sleep(min(5, max(1, args.observe_seconds)))

            for device_id in list(reversed(active)):
                closed = page.evaluate(
                    "(device) => window.m32aProbe.closeDevice(device)",
                    device_id,
                )
                remaining = [item for item in active if item != device_id]
                assert_playing(page, remaining)
                active.remove(device_id)
                stages.append(
                    {
                        "stage": f"final_close_{device_id}",
                        "closed": closed,
                        "remaining": [
                            stream_snapshot(page, item) for item in remaining
                        ],
                        "browser": page.evaluate(
                            "() => window.m32aProbe.snapshot()"
                        ),
                        "server": page.evaluate(
                            "() => window.m32aProbe.serverMetrics()"
                        ),
                    }
                )

            final_release = page.evaluate(
                "() => window.m32aProbe.closeSession()"
            )
            context.close()
            browser.close()
    except Exception as exc:
        failure = {
            "type": type(exc).__name__,
            "message": SENSITIVE.sub(r"\1<redacted>", str(exc))[:800],
        }
    finally:
        terminate_tree(server)
        server_handle.close()

    args.browser_log.write_text(
        "\n".join(console) + ("\n" if console else ""),
        encoding="utf-8",
    )
    result = {
        "devices": devices,
        "validated_max_streams": max(
            (
                len(
                    [
                        stream
                        for stream in stage.get("browser", {}).get("streams", [])
                        if stream.get("status") == "PLAYING"
                    ]
                )
                for stage in stages
            ),
            default=0,
        ),
        "stages": stages,
        "performance_samples": process_samples,
        "final_release": final_release,
        "page_errors": page_errors,
        "failure": failure,
        "logs": {
            "browser": str(args.browser_log),
            "server": str(args.server_log),
        },
    }
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if failure or page_errors:
        raise SystemExit("M3.2A isolated probe failed")


if __name__ == "__main__":
    main()
