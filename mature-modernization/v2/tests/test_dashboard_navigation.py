from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION_ASSET = ROOT / "app/static/dashboard/navigation.js"
TEMPLATES = (
    ROOT / "app/templates/m2_dashboard.html",
    ROOT / "app/templates/inspection.html",
    ROOT / "app/templates/video_workbench.html",
    ROOT / "app/templates/inspections.html",
    ROOT / "app/templates/authorized_users.html",
)


class DashboardNavigationTests(unittest.TestCase):
    def test_all_owner_dashboard_pages_use_one_navigation_asset(self) -> None:
        for template in TEMPLATES:
            html = template.read_text(encoding="utf-8")
            self.assertIn(
                '/api/v2/dashboard/assets/navigation.js',
                html,
                template.name,
            )
            self.assertIn(
                'data-cha-dashboard-nav',
                html,
                template.name,
            )

    def test_primary_navigation_lists_the_owner_business_routes(self) -> None:
        source = NAVIGATION_ASSET.read_text(encoding="utf-8")
        expected = {
            "监察总览": "/api/v2/dashboard",
            "视频监察": "/api/v2/dashboard/workbench",
            "监察记录": "/api/v2/dashboard/inspections",
            "设备运行": "/api/v2/dashboard/devices",
            "视频上传": "/api/v2/dashboard/media",
            "监察使用": "/api/v2/dashboard/realtime",
            "告警异常": "/api/v2/dashboard/alarms",
            "航班/任务": "/api/v2/dashboard/tasks",
            "设备定位": "/api/v2/dashboard/map",
            "数据质量": "/api/v2/dashboard/data-quality",
        }
        for label, href in expected.items():
            self.assertIn(label, source)
            self.assertIn(href, source)
        self.assertNotIn('href: "/api/v2/realtime"', source)

    def test_user_management_link_requires_existing_admin_api(self) -> None:
        source = NAVIGATION_ASSET.read_text(encoding="utf-8")
        self.assertIn('/api/v2/inspections/authorized-users', source)
        self.assertIn('if (!response.ok) return;', source)
        self.assertIn('/api/v2/dashboard/users', source)
        self.assertIn('The server remains the authority', source)

    def test_main_serves_the_data_free_navigation_asset(self) -> None:
        source = (ROOT / "app/main.py").read_text(encoding="utf-8")
        self.assertIn('/api/v2/dashboard/assets/navigation.js', source)
        self.assertIn('dashboard_navigation_asset_path', source)
        self.assertIn('media_type="application/javascript"', source)


if __name__ == "__main__":
    unittest.main()
