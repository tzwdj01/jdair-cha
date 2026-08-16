from __future__ import annotations

import datetime as dt
import unittest

from app.data.store import MemoryInspectionStore
from app.data.pagination import CollectedSource
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
            "device_status": _collected(
                "device_status",
                [
                    {
                        "id": "s-1",
                        "devId": "WX1",
                        "status": 1,
                        "time": "2026-08-15 00:10:00+00:00",
                    }
                ],
            ),
            "media_files": _collected(
                "media_files",
                [
                    {
                        "id": "file-1",
                        "devId": "WX1",
                        "fType": 3,
                        "startTime": "2026-08-15 00:30:00+00:00",
                    }
                ],
            ),
        }


class _PartiallyFailingCollector:
    async def collect(self, start, end):
        del start, end
        return {
            "device_status": CollectedSource.failed(
                "device_status",
                "AEE_DATA_UPSTREAM_REJECTED",
            ),
            "media_files": _collected(
                "media_files",
                [
                    {
                        "id": "file-1",
                        "devId": "WX1",
                        "fType": 3,
                        "startTime": "2026-08-15 00:30:00+00:00",
                    }
                ],
            ),
        }


def _collected(source, rows):
    return CollectedSource(
        source=source,
        rows=tuple(rows),
        records_total=len(rows),
        pages_fetched=1,
        fetched_source_count=len(rows),
        invalid_row_count=0,
        duplicate_source_id_count=0,
        complete=True,
        quality_flags=(),
    )


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
        scheduled = await self.scheduler.run_once(start=start, end=end)

        self.assertEqual(self.collector.calls, [(start, end)])
        results = {
            item.source: item
            for item in scheduled.report.results
        }
        self.assertEqual(results["device_status"].accepted_count, 1)
        self.assertEqual(results["media_files"].accepted_count, 1)
        self.assertTrue(scheduled.report.completed)
        self.assertEqual(
            {item.source for item in scheduled.sources},
            {"device_status", "media_files"},
        )

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
        scheduled = await self.scheduler.run_recent(days=2)
        self.assertEqual(len(self.collector.calls), 1)
        start, end = self.collector.calls[0]
        self.assertEqual(end.tzinfo, UTC)
        self.assertEqual((end - start).days, 2)
        self.assertTrue(scheduled.report.completed)

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

    async def test_failed_source_is_reported_and_does_not_block_others(
        self,
    ) -> None:
        scheduler = InspectionIngestionScheduler(
            _PartiallyFailingCollector(),
            InspectionIngestor(self.store),
        )
        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)
        scheduled = await scheduler.run_once(start=start, end=end)

        results = {
            item.source: item
            for item in scheduled.report.results
        }
        self.assertEqual(
            results["device_status"].error_code,
            "AEE_DATA_UPSTREAM_REJECTED",
        )
        self.assertIn(
            "source_collection_failed",
            results["device_status"].quality_flags,
        )
        self.assertEqual(results["media_files"].accepted_count, 1)
        self.assertFalse(scheduled.report.completed)

        by_source = {
            item.source: item
            for item in scheduled.sources
        }
        self.assertEqual(by_source["device_status"].status, "error")
        self.assertEqual(
            by_source["device_status"].error_code,
            "AEE_DATA_UPSTREAM_REJECTED",
        )
        self.assertEqual(by_source["media_files"].status, "ok")

        statuses = await self.store.fetch_device_status_events(
            start=start,
            end=end,
        )
        files = await self.store.fetch_media_files(
            start=start,
            end=end,
        )
        self.assertEqual(len(statuses), 0)
        self.assertEqual(len(files), 1)


if __name__ == "__main__":
    unittest.main()
