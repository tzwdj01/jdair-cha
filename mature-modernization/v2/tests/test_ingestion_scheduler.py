from __future__ import annotations

import datetime as dt
import unittest

from app.data.store import MemoryInspectionStore
from app.services.ingestion import InspectionIngestor
from app.services.ingestion_scheduler import (
    InspectionIngestionScheduler,
)


UTC = dt.timezone.utc


class _FakeCollector:
    def __init__(self) -> None:
        self.calls: list[tuple[dt.datetime, dt.datetime]] = []

    async def collect(self, start, end):
        self.calls.append((start, end))
        return {
            "device_status": [
                {
                    "id": "s-1",
                    "devId": "WX1",
                    "status": 1,
                    "time": "2026-08-15 00:10:00+00:00",
                }
            ],
            "media_files": [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": "2026-08-15 00:30:00+00:00",
                }
            ],
        }


class InspectionIngestionSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()
        self.collector = _FakeCollector()
        self.scheduler = InspectionIngestionScheduler(
            self.collector,
            InspectionIngestor(self.store),
        )

    async def test_run_once_collects_and_persists(self) -> None:
        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)
        report = await self.scheduler.run_once(start=start, end=end)

        self.assertEqual(self.collector.calls, [(start, end)])
        results = {item.source: item for item in report.results}
        self.assertEqual(results["device_status"].accepted_count, 1)
        self.assertEqual(results["media_files"].accepted_count, 1)
        self.assertTrue(report.completed)

        statuses = await self.store.fetch_device_status_events(
            start=start,
            end=end,
        )
        files = await self.store.fetch_media_files(
            start=start,
            end=end,
        )
        self.assertEqual(len(statuses), 1)
        self.assertEqual(len(files), 1)

    async def test_run_recent_uses_bounded_window(self) -> None:
        report = await self.scheduler.run_recent(days=2)
        self.assertEqual(len(self.collector.calls), 1)
        start, end = self.collector.calls[0]
        self.assertEqual(end.tzinfo, UTC)
        self.assertEqual((end - start).days, 2)
        self.assertTrue(report.completed)

    async def test_run_once_requires_aware_ordered_window(self) -> None:
        with self.assertRaises(ValueError):
            await self.scheduler.run_once(
                start=dt.datetime(2026, 8, 15, 0),
                end=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
            )
        with self.assertRaises(ValueError):
            await self.scheduler.run_once(
                start=dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
                end=dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
            )


if __name__ == "__main__":
    unittest.main()
