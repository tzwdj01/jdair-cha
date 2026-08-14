from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RealtimeProductUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (
            ROOT / "app/templates/m3_realtime.html"
        ).read_text(encoding="utf-8")
        cls.css = (
            ROOT / "app/static/realtime/realtime.css"
        ).read_text(encoding="utf-8")
        cls.app_js = (
            ROOT / "app/static/realtime/realtime.js"
        ).read_text(encoding="utf-8")
        cls.runtime_js = (
            ROOT / "app/static/realtime/multistream_runtime.js"
        ).read_text(encoding="utf-8")

    def test_formal_page_has_device_list_and_video_grid(self) -> None:
        self.assertIn("实时视频监察", self.html)
        self.assertIn('id="deviceList"', self.html)
        self.assertIn('id="videoGrid"', self.html)
        self.assertIn('id="videoTileTemplate"', self.html)
        self.assertIn('id="closeSessionButton"', self.html)
        self.assertIn("multistream_runtime.js", self.html)

    def test_only_validated_one_four_and_six_layouts_are_advertised(self) -> None:
        self.assertIn("1 / 4 / 6 路布局", self.html)
        self.assertIn(".video-grid.single", self.css)
        self.assertIn(".video-grid.quad", self.css)
        self.assertIn(".video-grid.six", self.css)
        self.assertIn("最多 6 路", self.html)
        self.assertNotIn("9 路", self.html)

    def test_video_is_muted_and_audio_remains_receive_only(self) -> None:
        self.assertIn("<video autoplay muted playsinline>", self.html)
        self.assertIn("<audio autoplay muted>", self.html)
        self.assertIn("requestFullscreen", self.app_js)
        self.assertIn("captureFrame", self.app_js)
        self.assertIn("openAudio", self.app_js)
        self.assertIn("openAudio", self.runtime_js)
        self.assertNotIn("getUserMedia", self.app_js)
        self.assertNotIn("getUserMedia", self.runtime_js)
        self.assertNotIn("startSendAudio", self.app_js)
        self.assertNotIn("startSendAudio", self.runtime_js)

    def test_product_uses_single_multistream_runtime(self) -> None:
        self.assertIn(
            "new window.ChaRealtimeMultiStreamRuntime",
            self.app_js,
        )
        self.assertNotIn("new window.mcs8Client", self.app_js)
        self.assertEqual(self.runtime_js.count("new window.mcs8Client()"), 1)
        self.assertIn("handleControlCommand", self.runtime_js)
        self.assertIn("closeStream(streamId)", self.runtime_js)

    def test_failure_retry_close_and_page_cleanup_are_wired(self) -> None:
        self.assertIn("retryTile", self.app_js)
        self.assertIn("closeTile", self.app_js)
        self.assertIn("markSharedConnectionAbnormal", self.app_js)
        self.assertIn('window.addEventListener("pagehide"', self.app_js)
        self.assertIn("keepalive: true", self.app_js)
        self.assertIn("stream_limit_reached", self.app_js)
        self.assertIn("duplicate_device", self.app_js)


if __name__ == "__main__":
    unittest.main()
