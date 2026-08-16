from __future__ import annotations

import datetime as dt
import unittest

from app.data.device_snapshot import MCS8DeviceSnapshotProcessor
from app.data.normalization import DeviceStatusEvent, normalize_mcs8_device_snapshot
from app.data.store import MemoryInspectionStore


UTC = dt.timezone.utc


def _snapshot_rows(rows: list[dict]) -> list[dict]:
    return rows


def _build_events(
    rows: list[dict],
    *,
    observed_at: dt.datetime,
) -> tuple[DeviceStatusEvent, ...]:
    return normalize_mcs8_device_snapshot(
        _snapshot_rows(rows),
        observed_at=observed_at,
        ingested_at=observed_at,
    ).events


class MCS8DeviceSnapshotProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionStore()
        self.processor = MCS8DeviceSnapshotProcessor(self.store)

    async def test_first_snapshot_is_initial_observation(self) -> None:
        observed = dt.datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
        events = _build_events(
            [
                {"szIDNO": "WXB310", "nOnline": 1},
                {"szIDNO": "WXB358", "nOnline": 0},
            ],
            observed_at=observed,
        )
        result = await self.processor.process_snapshot(events)
        self.assertEqual(result.initial_observation_count, 2)
        self.assertEqual(result.transition_count, 0)
        self.assertEqual(len(result.events_to_store), 2)
        for event in result.events_to_store:
            self.assertIn("initial_snapshot", event.quality_flags)
            self.assertIn("mcs8_device_snapshot", event.quality_flags)
        await self.processor.store_result(result)
        stored = await self.store.fetch_device_status_events(
            start=observed - dt.timedelta(minutes=1),
            end=observed + dt.timedelta(minutes=1),
        )
        self.assertEqual(len(stored), 2)

    async def test_unchanged_snapshot_does_not_grow_rows(self) -> None:
        observed1 = dt.datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=5)
        events1 = _build_events(
            [{"szIDNO": "WXB310", "nOnline": 1}],
            observed_at=observed1,
        )
        result1 = await self.processor.process_snapshot(events1)
        await self.processor.store_result(result1)

        events2 = _build_events(
            [{"szIDNO": "WXB310", "nOnline": 1}],
            observed_at=observed2,
        )
        result2 = await self.processor.process_snapshot(events2)
        self.assertEqual(result2.initial_observation_count, 0)
        self.assertEqual(result2.transition_count, 0)
        self.assertEqual(result2.unchanged_count, 1)
        self.assertEqual(len(result2.events_to_store), 0)
        await self.processor.store_result(result2)

        stored = await self.store.fetch_device_status_events(
            start=observed1 - dt.timedelta(minutes=1),
            end=observed2 + dt.timedelta(minutes=1),
        )
        self.assertEqual(len(stored), 1)

    async def test_status_change_creates_single_observed_transition(self) -> None:
        observed1 = dt.datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=5)
        events1 = _build_events(
            [{"szIDNO": "WXB310", "nOnline": 1}],
            observed_at=observed1,
        )
        result1 = await self.processor.process_snapshot(events1)
        await self.processor.store_result(result1)

        events2 = _build_events(
            [{"szIDNO": "WXB310", "nOnline": 0}],
            observed_at=observed2,
        )
        result2 = await self.processor.process_snapshot(events2)
        self.assertEqual(result2.initial_observation_count, 0)
        self.assertEqual(result2.transition_count, 1)
        self.assertEqual(len(result2.events_to_store), 1)
        event = result2.events_to_store[0]
        self.assertIn("cha_observed_transition", event.quality_flags)
        self.assertIn("observed_by_polling", event.quality_flags)
        self.assertIn(
            "partial_transition_visibility",
            event.quality_flags,
        )
        self.assertFalse(event.online)
        await self.processor.store_result(result2)

        stored = await self.store.fetch_device_status_events(
            start=observed1 - dt.timedelta(minutes=1),
            end=observed2 + dt.timedelta(minutes=1),
        )
        self.assertEqual(len(stored), 2)

    async def test_restart_uses_latest_known_state(self) -> None:
        observed1 = dt.datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=5)
        events1 = _build_events(
            [{"szIDNO": "WXB310", "nOnline": 1}],
            observed_at=observed1,
        )
        result1 = await self.processor.process_snapshot(events1)
        await self.processor.store_result(result1)

        # simulate scheduler restart: a fresh processor reading from the store
        fresh = MCS8DeviceSnapshotProcessor(self.store)
        events2 = _build_events(
            [{"szIDNO": "WXB310", "nOnline": 1}],
            observed_at=observed2,
        )
        result2 = await fresh.process_snapshot(events2)
        self.assertEqual(result2.initial_observation_count, 0)
        self.assertEqual(result2.transition_count, 0)
        self.assertEqual(result2.unchanged_count, 1)
        self.assertEqual(len(result2.events_to_store), 0)

    async def test_mixed_devices_are_independent(self) -> None:
        observed1 = dt.datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=5)
        events1 = _build_events(
            [
                {"szIDNO": "WXB310", "nOnline": 1},
                {"szIDNO": "WXB358", "nOnline": 0},
            ],
            observed_at=observed1,
        )
        result1 = await self.processor.process_snapshot(events1)
        await self.processor.store_result(result1)

        events2 = _build_events(
            [
                {"szIDNO": "WXB310", "nOnline": 1},  # unchanged
                {"szIDNO": "WXB358", "nOnline": 1},  # changed -> online
                {"szIDNO": "WXB347", "nOnline": 0},  # new device
            ],
            observed_at=observed2,
        )
        result2 = await self.processor.process_snapshot(events2)
        self.assertEqual(result2.initial_observation_count, 1)
        self.assertEqual(result2.transition_count, 1)
        self.assertEqual(result2.unchanged_count, 1)
        await self.processor.store_result(result2)
        stored = await self.store.fetch_device_status_events(
            start=observed1 - dt.timedelta(minutes=1),
            end=observed2 + dt.timedelta(minutes=1),
        )
        self.assertEqual(len(stored), 4)


if __name__ == "__main__":
    unittest.main()
