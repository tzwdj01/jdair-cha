from __future__ import annotations

import datetime as dt
import unittest

from app.data.aee_adapter import AEEPageResult
from app.data.aee_collector import AEEInspectionCollector
from app.data.aee_http import AEEDataHTTPError


UTC = dt.timezone.utc


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _page(self, rows, **kwargs) -> AEEPageResult:
        return AEEPageResult(
            rows=tuple(rows),
            records_total=len(rows),
            page=kwargs["page"],
            page_size=kwargs["page_size"],
            has_more=False,
            invalid_row_count=0,
            quality_flags=(),
        )

    def list_device_online(self, **kwargs) -> AEEPageResult:
        self.calls.append(("dev_online", kwargs))
        return self._page(
            [
                {
                    "id": "s-1",
                    "devId": "WX1",
                    "status": 1,
                    "time": "2026-08-15 00:10:00+00:00",
                }
            ],
            **kwargs,
        )

    def list_record_files(self, **kwargs) -> AEEPageResult:
        self.calls.append(("record_files", kwargs))
        return self._page(
            [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": "2026-08-15 00:30:00+00:00",
                }
            ],
            **kwargs,
        )

    def list_alarms(self, **kwargs) -> AEEPageResult:
        self.calls.append(("alarms", kwargs))
        return self._page(
            [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmTime": "2026-08-15 00:05:00+00:00",
                }
            ],
            **kwargs,
        )


class AEEInspectionCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.adapter = _FakeAdapter()
        self.collector = AEEInspectionCollector(
            self.adapter,
            enterprise_id="ENT-1",
            time_type=0,
            group_with_child=0,
        )
        self.start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        self.end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)

    async def test_collects_devices_and_files_without_guessing_alarms(
        self,
    ) -> None:
        collected = await self.collector.collect(
            self.start,
            self.end,
        )

        self.assertEqual(
            set(collected),
            {"device_status", "media_files"},
        )
        self.assertEqual(
            collected["device_status"].rows[0]["devId"],
            "WX1",
        )
        self.assertTrue(collected["device_status"].complete)
        called = [name for name, _ in self.adapter.calls]
        self.assertNotIn("alarms", called)
        enterprise_seen = {
            kwargs["enterprise_id"]
            for name, kwargs in self.adapter.calls
            if name == "dev_online"
        }
        self.assertEqual(enterprise_seen, {"ENT-1"})

    async def test_collects_alarms_when_selectors_provided(self) -> None:
        collector = AEEInspectionCollector(
            self.adapter,
            enterprise_id="ENT-1",
            time_type=0,
            group_with_child=0,
            include_alarms=True,
        )
        collected = await collector.collect(self.start, self.end)

        self.assertIn("alarms", collected)
        self.assertEqual(
            collected["alarms"].rows[0]["alarmType"],
            205,
        )
        alarm_kwargs = next(
            kwargs
            for name, kwargs in self.adapter.calls
            if name == "alarms"
        )
        self.assertEqual(alarm_kwargs["time_type"], 0)
        self.assertEqual(alarm_kwargs["group_with_child"], 0)

    async def test_enterprise_id_is_required(self) -> None:
        with self.assertRaises(ValueError):
            AEEInspectionCollector(
                self.adapter,
                enterprise_id=None,
                time_type=0,
                group_with_child=0,
            )
        with self.assertRaises(ValueError):
            AEEInspectionCollector(
                self.adapter,
                enterprise_id=True,
                time_type=0,
                group_with_child=0,
            )

    async def test_window_must_be_aware_and_ordered(self) -> None:
        with self.assertRaises(ValueError):
            await self.collector.collect(
                dt.datetime(2026, 8, 15, 0),
                self.end,
            )
        with self.assertRaises(ValueError):
            await self.collector.collect(
                self.end,
                self.start,
            )

    async def test_single_source_failure_does_not_block_other_sources(
        self,
    ) -> None:
        adapter = _FailingDeviceAdapter()
        collector = AEEInspectionCollector(
            adapter,
            enterprise_id="ENT-1",
            time_type=0,
            group_with_child=0,
            include_alarms=True,
        )
        collected = await collector.collect(
            self.start,
            self.end,
        )

        self.assertEqual(
            collected["device_status"].status,
            "error",
        )
        self.assertEqual(
            collected["device_status"].error_code,
            "AEE_DATA_UPSTREAM_REJECTED",
        )
        self.assertEqual(
            collected["device_status"].rows,
            (),
        )
        self.assertEqual(
            collected["media_files"].status,
            "ok",
        )
        self.assertEqual(
            collected["alarms"].status,
            "ok",
        )
        self.assertEqual(
            collected["media_files"].rows[0]["devId"],
            "WX1",
        )
        self.assertEqual(
            collected["alarms"].rows[0]["alarmType"],
            205,
        )
        called = [name for name, _ in adapter.calls]
        self.assertEqual(
            called,
            ["dev_online", "record_files", "alarms"],
        )


class _FailingDeviceAdapter(_FakeAdapter):
    def list_device_online(self, **kwargs) -> AEEPageResult:
        self.calls.append(("dev_online", kwargs))
        raise AEEDataHTTPError(
            "AEE_DATA_UPSTREAM_REJECTED",
            "simulated upstream rejection",
        )


if __name__ == "__main__":
    unittest.main()
