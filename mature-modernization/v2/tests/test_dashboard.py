from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import Settings
from app.services.dashboard import DashboardAuthenticationError, DashboardService
from app.services.legacy import LegacyResponse


def response(payload, status: int = 200) -> LegacyResponse:
    return LegacyResponse(
        status_code=status,
        content_type="application/json",
        body=json.dumps(payload).encode(),
        latency_ms=4.2,
    )


class FakeLegacyClient:
    async def session(self, _cookie):
        return response({"authenticated": True, "username": "tester"})

    async def devices(self, _cookie):
        return response(
            [
                {
                    "devId": "WX1",
                    "name": "JDTY01",
                    "online": True,
                    "city": "北京",
                    "lng": 116.4,
                    "lat": 39.9,
                    "lastOnlineTime": "2026-08-13 22:00:00",
                },
                {
                    "devId": "WX2",
                    "name": "JDTY02",
                    "online": False,
                    "city": "上海",
                    "lng": 121.4,
                    "lat": 31.2,
                    "lastOnlineTime": "",
                },
            ]
        )

    async def video_stats(self, _cookie):
        return response({"WX1": {"count": 8, "sizeMB": 1024}})

    async def flights(self, _cookie, _date):
        return response({"total": 34, "records": []})

    async def routine_tasks(self, _cookie, _date):
        return response({"total": 43, "records": []})

    async def records(
        self,
        _cookie,
        start,
        _end,
        *,
        page=1,
        page_size=100,
    ):
        del page, page_size
        return response({"recordsTotal": int(start[8:10])})


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_aggregates_metrics_and_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "CHA_V2_DASHBOARD_STATE_DIR": temp_dir,
                "CHA_V2_DASHBOARD_INITIAL_WAIT_SECONDS": "5",
            },
            clear=False,
        ):
            service = DashboardService(FakeLegacyClient(), Settings.from_env())
            data = await service.snapshot("jdair_mcs8_session=test", days=3)

        self.assertEqual(data["summary"]["devices"]["total"], 2)
        self.assertEqual(data["summary"]["devices"]["online"], 1)
        self.assertEqual(data["summary"]["files"]["count"], 8)
        self.assertEqual(
            data["summary"]["files"]["device_coverage_rate"],
            50.0,
        )
        self.assertEqual(data["summary"]["operations"]["flights_today"], 34)
        self.assertEqual(
            data["summary"]["operations"]["routine_tasks_today"],
            43,
        )
        self.assertEqual(len(data["video_trend"]), 3)
        self.assertEqual(data["exceptions"]["offline"], 1)
        self.assertEqual(data["exceptions"]["without_recent_files"], 1)
        self.assertEqual(data["scope"]["generated_for"], "tester")
        self.assertEqual(len(data["device_trend"]), 1)

    async def test_missing_cookie_is_rejected(self) -> None:
        service = DashboardService(FakeLegacyClient(), Settings.from_env())
        with self.assertRaises(DashboardAuthenticationError):
            await service.snapshot("")


if __name__ == "__main__":
    unittest.main()
