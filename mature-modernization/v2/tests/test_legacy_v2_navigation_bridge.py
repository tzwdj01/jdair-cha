from __future__ import annotations

import ast
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LEGACY_SOURCE = (
    REPOSITORY_ROOT
    / "releases"
    / "20260812212342-layout-redesign-phase5"
    / "mcs8_web_panel.py"
)


@unittest.skipUnless(
    LEGACY_SOURCE.exists(),
    "root Legacy source is intentionally absent from a V2 release archive",
)
class LegacyV2NavigationBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = LEGACY_SOURCE.read_text(encoding="utf-8")

    def test_legacy_exposes_a_plain_link_to_the_v2_data_center(self) -> None:
        self.assertIn(
            '<a class="v2-data-center-link" href="/api/v2/dashboard"',
            self.source,
        )
        self.assertIn(
            ">监察数据中心</a>",
            self.source,
        )

    def test_bridge_does_not_replace_the_legacy_session_model(self) -> None:
        self.assertIn('SESSION_COOKIE = "jdair_mcs8_session"', self.source)
        self.assertIn("def mcs8_ws_login(username: str, password: str)", self.source)
        self.assertIn('if parsed.path == "/api/login":', self.source)
        self.assertNotIn("authorized_users", self.source)

    def test_legacy_workbench_exposes_maintenance_realtime_tab(self) -> None:
        for expected in (
            'id="tabRealtime"',
            ">实时视频 <span id=\"realtimeLaunchCount\">0</span></button>",
            'id="realtimeModal"',
            "维修部实时设备",
            "/api/v2/realtime?workbench=1&embed=visual&scope=maintenance_wxb",
            "maintenanceRealtimeDevices",
            "/^WXB/i",
            "!!device.online",
            "cha-workbench-add-device",
            "cha-workbench-close-session",
            "event.origin !== location.origin",
            "event.source !== frame?.contentWindow",
            "已验证最多 6 路同时播放",
            'data-realtime-device="${esc(deviceId)}"',
        ):
            self.assertIn(expected, self.source)

        self.assertNotIn(
            'onclick="addLegacyRealtimeDevice(',
            self.source,
        )

    def test_legacy_realtime_tab_reuses_v2_without_media_workarounds(self) -> None:
        self.assertIn("M3 原生 AEE/MCS8 WebRTC 链路", self.source)
        self.assertIn("不复制视频、不增加转码服务", self.source)
        self.assertIn("releaseLegacyRealtimeFrame", self.source)
        self.assertIn("closeRealtimeSession", self.source)

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_legacy_inline_realtime_javascript_has_valid_syntax(self) -> None:
        module = ast.parse(self.source)
        html = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "HTML"
                for target in node.targets
            )
        )
        scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
        self.assertEqual(len(scripts), 1)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".js",
            delete=False,
        ) as handle:
            handle.write(scripts[0])
            script_path = Path(handle.name)
        try:
            result = subprocess.run(
                ["node", "--check", str(script_path)],
                check=False,
                text=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            script_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
