from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
