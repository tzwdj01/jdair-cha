from __future__ import annotations

import datetime as dt
import unittest

from app.data.store import MemoryInspectionStore
from app.services.ingestion import InspectionIngestor


UTC = dt.timezone.utc
OBSERVED = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)
INGESTED = dt.datetime(2026, 8, 15, 1, 0, 1, tzinfo=UTC)


class InspectionIngestorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()
        self.ingestor = InspectionIngestor(self.store)

    async def test_ingest_all_persists_and_reports(self) -> None:
        report = await self.ingestor.ingest_all(
            {
                "device_status": [
                    {
                        "id": "s-1",
                        "devId": "WX1",
                        "status": 1,
                        "time": "2026-08-15 00:10:00+00:00",
                    },
                    {
                        "devId": "WX2",
                        "status": "bad",
                        "time": "2026-08-15 00:20:00+00:00",
                    },
                ],
                "media_files": [
                    {
                        "id": "file-1",
                        "devId": "WX1",
                        "fType": 3,
                        "fileSize": 4096,
                        "duration": 125,
                        "startTime": "2026-08-15 00:10:00+00:00",
                    }
                ],
                "alarms": [
                    {
                        "id": "alarm-1",
                        "devId": "WX1",
                        "alarmType": 205,
                        "alarmStatus": 1,
                        "alarmTime": "2026-08-15 00:05:00+00:00",
                    }
                ],
            },
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        results = {item.source: item for item in report.results}
        self.assertEqual(results["device_status"].accepted_count, 1)
        self.assertEqual(results["device_status"].invalid_row_count, 1)
        self.assertEqual(results["media_files"].accepted_count, 1)
        self.assertEqual(results["alarms"].accepted_count, 1)
        self.assertFalse(report.completed)

        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)
        statuses = await self.store.fetch_device_status_events(
            start=start,
            end=end,
        )
        files = await self.store.fetch_media_files(
            start=start,
            end=end,
        )
        alarms = await self.store.fetch_alarm_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].device_id, "WX1")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].file_size_bytes, 4096)
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].alarm_type_code, 205)

    async def test_media_restricted_fields_omitted_by_default(self) -> None:
        result = await self.ingestor.ingest_media_files(
            [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 1,
                    "startTime": "2026-08-15 00:10:00+00:00",
                    "peopleNo": "person-1",
                    "peopleName": "Person",
                    "des": "restricted",
                }
            ],
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(result.accepted_count, 1)
        self.assertIn(
            "restricted_fields_omitted",
            result.quality_flags,
        )
        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)
        files = await self.store.fetch_media_files(
            start=start,
            end=end,
        )
        self.assertIsNone(files[0].people_no)
        self.assertIsNone(files[0].people_name)
        self.assertIsNone(files[0].description)

    async def test_ingest_all_with_empty_payload_is_complete(self) -> None:
        report = await self.ingestor.ingest_all(
            {},
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(report.results, ())
        self.assertTrue(report.completed)

    async def test_source_failure_is_reported_and_retry_is_idempotent(
        self,
    ) -> None:
        store = _FlakyMediaStore()
        ingestor = InspectionIngestor(store)
        payload = {
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
                    "fileSize": 4096,
                    "duration": 125,
                    "startTime": "2026-08-15 00:10:00+00:00",
                }
            ],
            "alarms": [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmStatus": 1,
                    "alarmTime": "2026-08-15 00:05:00+00:00",
                }
            ],
        }

        report = await ingestor.ingest_all(
            payload,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        results = {item.source: item for item in report.results}
        self.assertEqual(
            results["device_status"].error_code,
            None,
        )
        self.assertEqual(
            results["media_files"].error_code,
            "SOURCE_INGEST_FAILED",
        )
        self.assertIn(
            "source_ingest_failed",
            results["media_files"].quality_flags,
        )
        self.assertEqual(results["alarms"].error_code, None)
        self.assertFalse(report.completed)

        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 1, tzinfo=UTC)
        statuses = await store.fetch_device_status_events(
            start=start,
            end=end,
        )
        files = await store.fetch_media_files(
            start=start,
            end=end,
        )
        alarms = await store.fetch_alarm_events(
            start=start,
            end=end,
        )
        # The failed media source left no half-baked rows; the successful
        # sources were persisted cleanly.
        self.assertEqual(len(statuses), 1)
        self.assertEqual(len(files), 0)
        self.assertEqual(len(alarms), 1)

        # A retry after the transient failure completes without duplicates.
        store.fail_media = False
        retry = await ingestor.ingest_all(
            payload,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertTrue(retry.completed)
        statuses = await store.fetch_device_status_events(
            start=start,
            end=end,
        )
        files = await store.fetch_media_files(
            start=start,
            end=end,
        )
        alarms = await store.fetch_alarm_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(statuses), 1)
        self.assertEqual(len(files), 1)
        self.assertEqual(len(alarms), 1)


class _FlakyMediaStore(MemoryInspectionStore):
    """MemoryInspectionStore that simulates a transient media write failure."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_media = True

    async def upsert_media_files(self, files):
        if self.fail_media:
            raise RuntimeError("transient media write failure")
        return await super().upsert_media_files(files)


if __name__ == "__main__":
    unittest.main()
