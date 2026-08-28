from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path

from app.data.aee_adapter import AEEPageResult, AEEReadOnlyDataAdapter
from app.data.aee_collector import AEEInspectionCollector
from app.data.aee_http import AEEDataHTTPError
from app.data.normalization import (
    normalize_alarm_events,
    normalize_device_status_events,
    normalize_media_files,
)
from app.data.pagination import CollectedSource
from app.data.store import MemoryInspectionStore
from app.services.ingestion import InspectionIngestor
from app.services.ingestion_scheduler import InspectionIngestionScheduler


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
UTC = dt.timezone.utc
OBSERVED = dt.datetime(2026, 8, 16, 4, 30, tzinfo=SHANGHAI)
INGESTED = OBSERVED + dt.timedelta(seconds=1)


def _load(name: str) -> list[dict]:
    with (FIXTURES / name).open(encoding="utf-8") as handle:
        return json.load(handle)["rows"]


class AEELiveFixtureNormalizationTests(unittest.TestCase):
    def test_dev_online_status_zero_is_offline(self) -> None:
        result = normalize_device_status_events(
            _load("aee_dev_online_list_samples.json"),
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        by_id = {item.source_record_id: item for item in result.events}
        self.assertTrue(by_id["dev-online-1"].online)
        self.assertFalse(by_id["dev-online-3"].online)
        self.assertFalse(by_id["dev-online-4"].online)
        self.assertNotIn(
            "non_online_status_map_partial",
            result.quality_flags,
        )

    def test_record_file_fixture_normalizes_kinds_and_units(self) -> None:
        result = normalize_media_files(
            _load("aee_record_file_list_samples.json"),
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        by_id = {item.source_record_id: item for item in result.files}
        video = by_id["rec-1"]
        self.assertEqual(video.media_kind, "video")
        self.assertEqual(video.file_size_bytes, 187109839)
        self.assertEqual(video.duration_seconds, 301)
        self.assertEqual(
            video.created_at_source,
            dt.datetime(2026, 8, 15, 20, 11, 33, tzinfo=UTC),
        )
        self.assertEqual(
            video.end_at_source,
            dt.datetime(2026, 8, 15, 20, 16, 33, tzinfo=UTC),
        )
        self.assertEqual(
            video.uploaded_at_source,
            dt.datetime(2026, 8, 15, 20, 19, 33, tzinfo=UTC),
        )
        audio = by_id["rec-2"]
        self.assertEqual(audio.media_kind, "audio")
        imported = by_id["rec-3"]
        self.assertEqual(imported.list_type_code, 1)

    def test_alarm_fixture_preserves_raw_codes(self) -> None:
        result = normalize_alarm_events(
            _load("aee_alarm_list_samples.json"),
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(result.invalid_row_count, 0)
        by_id = {item.source_record_id: item for item in result.events}
        self.assertEqual(by_id["alarm-1"].alarm_type_code, 205)
        self.assertEqual(by_id["alarm-1"].deal_status_code, 0)
        self.assertEqual(by_id["alarm-4"].alarm_type_code, 206)
        self.assertIsNone(by_id["alarm-1"].alarm_status_code)


class _FixtureHTTPClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def get_json(self, path, *, query=None):
        return self.payload


class AEEAdapterLiveEnvelopeTests(unittest.TestCase):
    def test_error_200_envelope_is_success(self) -> None:
        payload = {
            "error": 200,
            "data": [{"id": "1", "devId": "WX1"}],
            "recordsTotal": 1,
        }
        adapter = AEEReadOnlyDataAdapter(_FixtureHTTPClient(payload))
        result = adapter.list_device_online(
            start=dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
            end=dt.datetime(2026, 8, 15, 8, tzinfo=UTC),
            source_timezone=SHANGHAI,
            enterprise_id=20_000_000,
        )
        self.assertEqual(result.rows[0]["devId"], "WX1")
        self.assertFalse(result.has_more)

    def test_error_333_auth_empty_is_bounded(self) -> None:
        adapter = AEEReadOnlyDataAdapter(
            _FixtureHTTPClient({"error": 333, "data": [], "msg": None})
        )
        with self.assertRaises(AEEDataHTTPError) as raised:
            adapter.list_device_online(
                start=dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
                end=dt.datetime(2026, 8, 15, 8, tzinfo=UTC),
                source_timezone=SHANGHAI,
                enterprise_id=20_000_000,
            )
        self.assertEqual(
            raised.exception.code,
            "AEE_DATA_UPSTREAM_REJECTED",
        )


class _FixtureAdapter:
    def __init__(self) -> None:
        self.dev_rows = _load("aee_dev_online_list_samples.json")
        self.file_rows = _load("aee_record_file_list_samples.json")
        self.alarm_rows = _load("aee_alarm_list_samples.json")
        self.calls: list[str] = []

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
        self.calls.append("dev_online")
        return self._page(self.dev_rows, **kwargs)

    def list_record_files(self, **kwargs) -> AEEPageResult:
        self.calls.append("record_files")
        return self._page(self.file_rows, **kwargs)

    def list_alarms(self, **kwargs) -> AEEPageResult:
        self.calls.append("alarms")
        return self._page(self.alarm_rows, **kwargs)


class OneShotIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_oneshot_ingestion_from_live_fixtures(self) -> None:
        store = MemoryInspectionStore()
        adapter = _FixtureAdapter()
        collector = AEEInspectionCollector(
            adapter,
            enterprise_id=20_000_000,
            source_timezone=SHANGHAI,
            time_type=0,
            group_with_child=0,
            include_alarms=True,
        )
        scheduler = InspectionIngestionScheduler(
            collector,
            InspectionIngestor(store, source_timezone=SHANGHAI),
        )
        # The source window is defined in Shanghai local time (the same window
        # used for the live DevOnlineList/RecordFileList/AlarmList requests).
        source_start = dt.datetime(2026, 8, 13, 0, tzinfo=SHANGHAI)
        source_end = dt.datetime(2026, 8, 16, 23, 59, 59, tzinfo=SHANGHAI)
        scheduled = await scheduler.run_once(
            start=source_start,
            end=source_end,
        )

        results = {
            item.source: item
            for item in scheduled.report.results
        }
        self.assertEqual(results["device_status"].accepted_count, 5)
        self.assertEqual(results["media_files"].accepted_count, 3)
        self.assertEqual(results["alarms"].accepted_count, 4)
        self.assertEqual(results["device_status"].invalid_row_count, 0)
        self.assertTrue(scheduled.report.completed)
        self.assertEqual(
            {item.source for item in scheduled.sources},
            {"device_status", "media_files", "alarms"},
        )
        self.assertTrue(all(item.complete for item in scheduled.sources))

        # Normalized events are stored in UTC; query with the UTC equivalent
        # of the same source window so the local-day boundary is preserved.
        fetch_start = source_start.astimezone(UTC)
        fetch_end = source_end.astimezone(UTC)
        statuses = await store.fetch_device_status_events(
            start=fetch_start,
            end=fetch_end,
        )
        files = await store.fetch_media_files(
            start=fetch_start,
            end=fetch_end,
        )
        alarms = await store.fetch_alarm_events(
            start=fetch_start,
            end=fetch_end,
        )
        self.assertEqual(len(statuses), 5)
        self.assertEqual(len(files), 3)
        self.assertEqual(len(alarms), 4)
        self.assertEqual(
            set(adapter.calls),
            {"dev_online", "record_files", "alarms"},
        )

        # Re-running the same one-shot window must be idempotent: the store
        # keys by source identity (status/alarm latest-wins, media source-ID
        # upsert), so stored rows must not duplicate.
        adapter.calls.clear()
        await scheduler.run_once(
            start=source_start,
            end=source_end,
        )
        statuses_again = await store.fetch_device_status_events(
            start=fetch_start,
            end=fetch_end,
        )
        files_again = await store.fetch_media_files(
            start=fetch_start,
            end=fetch_end,
        )
        alarms_again = await store.fetch_alarm_events(
            start=fetch_start,
            end=fetch_end,
        )
        self.assertEqual(len(statuses_again), len(statuses))
        self.assertEqual(len(files_again), len(files))
        self.assertEqual(len(alarms_again), len(alarms))


if __name__ == "__main__":
    unittest.main()
