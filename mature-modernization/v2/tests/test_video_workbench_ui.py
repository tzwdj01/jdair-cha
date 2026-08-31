from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VideoInspectionWorkbenchUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workbench = (
            ROOT / "app/templates/video_workbench.html"
        ).read_text(encoding="utf-8")
        cls.inspections = (
            ROOT / "app/templates/inspections.html"
        ).read_text(encoding="utf-8")
        cls.realtime = (
            ROOT / "app/static/realtime/realtime.js"
        ).read_text(encoding="utf-8")

    def test_workbench_reuses_existing_contracts(self) -> None:
        for expected in (
            "/api/v2/realtime?workbench=1&embed=visual",
            "/api/v2/inspection/workbench/sources",
            "/api/v2/inspections/candidates",
            "/api/v2/inspections/",
            "保存草稿",
            "提交正式记录",
            "审计轨迹",
        ):
            self.assertIn(expected, self.workbench)
        self.assertIn("/api/v2/dashboard/workbench", self.inspections)

    def test_visual_workspace_reuses_one_m3_session_for_multiple_tiles(self) -> None:
        for expected in (
            "sourceSearch",
            "sourceFilter",
            "cha-realtime-workbench-ready",
            "cha-realtime-workbench-state",
            "cha-workbench-add-device",
            "cha-workbench-close-session",
            "pendingRealtimeDevices",
            "activeDevices",
            'event.source !== byId("realtimeFrame").contentWindow',
        ):
            self.assertIn(expected, self.workbench)
        for expected in (
            "workbenchVisualEmbed",
            "queueWorkbenchDevice",
            "flushWorkbenchDevices",
            "emitWorkbenchState",
            "cha-workbench-add-device",
            "cha-workbench-close-session",
            "workbench-visual-embed",
        ):
            self.assertIn(expected, self.realtime)

    def test_capacity_guard_keeps_nine_and_sixteen_evidence_gated(self) -> None:
        self.assertIn('title="需要 AEE 同设备多路取证后才可启用"', self.workbench)
        self.assertIn('type="button" disabled title="需要 AEE 同设备多路取证后才可启用">9', self.workbench)
        self.assertIn('type="button" disabled title="需要 AEE 同设备多路取证后才可启用">16', self.workbench)
        self.assertIn("Math.min(Number(session.max_streams || 6), 6)", self.realtime)
        self.assertNotIn("maxStreams: 16", self.realtime)

    def test_workbench_exposes_existing_correction_flow_without_new_issue_system(self) -> None:
        self.assertIn('id="correctRecord"', self.workbench)
        self.assertIn('id="correctionReason"', self.workbench)
        self.assertIn('"/correct"', self.workbench)
        self.assertIn("独立 Issue 实体/关联工作流尚未实现", self.workbench)

    def test_uploaded_playback_is_honest_and_no_media_workaround_is_added(
        self,
    ) -> None:
        self.assertIn("AEE VERIFICATION REQUIRED", self.workbench)
        forbidden = ("ffmpeg", "transcod", "mediasoup", "new RTCPeerConnection")
        lowered = self.workbench.lower()
        for value in forbidden:
            self.assertNotIn(value, lowered)

    def test_realtime_embedded_context_uses_same_origin_message(self) -> None:
        self.assertIn("cha-realtime-inspection-context", self.realtime)
        self.assertIn("window.parent.postMessage", self.realtime)
        self.assertIn("window.location.origin", self.realtime)
        self.assertIn("startRequestedDevice", self.realtime)


if __name__ == "__main__":
    unittest.main()
