from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
import unittest

from app.data.mcs8_auth import MCS8ServerAuthProvider
from app.data.mcs8_collector import MCS8InspectionCollector
from app.data.mcs8_adapter import MCS8ReadOnlyDataAdapter
from app.data.aee_adapter import AEEPageResult
from app.data.aee_http import AEEDataHTTPError
from app.data.store import MemoryInspectionStore
from app.services.mcs8_scheduler import (
    MCS8ProductionScheduler,
)


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class _FakeAdapter:
    def __init__(self) -> None:
        self.device_rows: list[dict] = [
            {"szIDNO": "WXB310", "nOnline": 1, "groupId": 30000002},
            {"szIDNO": "WXB358", "nOnline": 0, "groupId": 30000002},
        ]
        self.media_rows: list[dict] = []
        self.alarm_rows: list[dict] = []
        self.media_fail = False
        self.alarm_fail = False

    def list_device_snapshot(self) -> AEEPageResult:
        return AEEPageResult(
            rows=tuple(dict(r) for r in self.device_rows),
            records_total=len(self.device_rows),
            page=1,
            page_size=len(self.device_rows),
            has_more=False,
            invalid_row_count=0,
            quality_flags=("mcs8_device_snapshot",),
        )

    def list_record_files(self, **kwargs) -> AEEPageResult:
        if self.media_fail:
            raise AEEDataHTTPError(
                "MCS8_DATA_UPSTREAM_REJECTED",
                "rejected",
            )
        return self._page(self.media_rows)

    def list_alarms(self, **kwargs) -> AEEPageResult:
        if self.alarm_fail:
            raise AEEDataHTTPError(
                "MCS8_DATA_UPSTREAM_REJECTED",
                "rejected",
            )
        return self._page(self.alarm_rows)

    def _page(self, rows) -> AEEPageResult:
        return AEEPageResult(
            rows=tuple(dict(r) for r in rows),
            records_total=len(rows),
            page=1,
            page_size=max(1, len(rows)),
            has_more=False,
            invalid_row_count=0,
            quality_flags=(),
        )


class _FakeAuth(MCS8ServerAuthProvider):
    def __init__(self) -> None:
        self._token = "server-token"
        self.login_calls = 0

    @property
    def token(self) -> str | None:
        return self._token

    def invalidate(self) -> None:
        self._token = None

    def login(self) -> str:
        self.login_calls += 1
        self._token = "server-token"
        return self._token


def _build(
    adapter: _FakeAdapter,
    *,
    state_dir: str = "/tmp/mcs8-sched-test",
    auth: _FakeAuth | None = None,
    store: MemoryInspectionStore | None = None,
) -> tuple[MCS8ProductionScheduler, MemoryInspectionStore, _FakeAuth]:
    store = store or MemoryInspectionStore()
    provider = auth or _FakeAuth()
    scheduler = MCS8ProductionScheduler(
        auth=provider,
        host="mcs8.example.test",
        api_port=7712,
        store=store,
        lookback_seconds=3600,
        overlap_seconds=300,
        state_dir=state_dir,
        source_timezone=SHANGHAI,
        max_login_retries=2,
    )
    # inject a fake collector via private field for testability
    scheduler._collector = MCS8InspectionCollector(
        MCS8ReadOnlyDataAdapter(_FakeClient(adapter)),
        store,
        source_timezone=SHANGHAI,
        include_alarms=True,
    )
    return scheduler, store, provider


class _FakeClient:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self._adapter = adapter

    def get_json(self, path, *, query=None):
        del query
        if path == "/api/GetDevListByGroupId":
            return {"data": [dict(r) for r in self._adapter.device_rows]}
        if path == "/api/v1/RecordFileList":
            if self._adapter.media_fail:
                raise AEEDataHTTPError(
                    "MCS8_DATA_UPSTREAM_REJECTED",
                    "rejected",
                )
            return {
                "error": 200,
                "data": [dict(r) for r in self._adapter.media_rows],
                "recordsTotal": len(self._adapter.media_rows),
            }
        if path == "/api/v1/AlarmList":
            if self._adapter.alarm_fail:
                raise AEEDataHTTPError(
                    "MCS8_DATA_UPSTREAM_REJECTED",
                    "rejected",
                )
            return {
                "error": 200,
                "data": [dict(r) for r in self._adapter.alarm_rows],
                "recordsTotal": len(self._adapter.alarm_rows),
            }
        raise AEEDataHTTPError("MCS8_DATA_PATH_NOT_ALLOWED", "blocked")


class MCS8ProductionSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cycle_runs_device_then_media_alarm(self) -> None:
        adapter = _FakeAdapter()
        adapter.media_rows = [
            {
                "id": "rec-1",
                "devId": "WXB310",
                "fType": 3,
                "startTime": "2026-08-17 09:30:00",
            }
        ]
        adapter.alarm_rows = [
            {
                "id": "alarm-1",
                "devId": "WXB358",
                "alarmType": 205,
                "alarmTime": "2026-08-17 09:35:00",
            }
        ]
        scheduler, store, _ = _build(adapter)
        observed = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)  # = 10:00 +08:00
        result = await scheduler.run_cycle(observed_at=observed)
        self.assertTrue(result.all_successful)
        by_source = {item.source: item for item in result.sources}
        self.assertEqual(by_source["device_status"].status, "ok")
        self.assertEqual(by_source["device_status"].fetched_source_count, 2)
        self.assertEqual(by_source["device_status"].stored_count, 2)
        self.assertEqual(by_source["media_files"].stored_count, 1)
        self.assertEqual(by_source["alarms"].stored_count, 1)
        self.assertEqual(len(await store.fetch_media_files(
            start=observed - dt.timedelta(hours=1),
            end=observed,
        )), 1)

    async def test_unchanged_device_cycle_does_not_grow_rows(self) -> None:
        adapter = _FakeAdapter()
        scheduler, store, _ = _build(adapter)
        observed1 = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=10)
        r1 = await scheduler.run_cycle(observed_at=observed1)
        r2 = await scheduler.run_cycle(observed_at=observed2)
        self.assertEqual(
            {i.source: i.stored_count for i in r1.sources},
            {"device_status": 2, "media_files": 0, "alarms": 0},
        )
        self.assertEqual(
            {i.source: i.stored_count for i in r2.sources},
            {"device_status": 0, "media_files": 0, "alarms": 0},
        )
        rows = await store.fetch_device_status_events(
            start=observed1 - dt.timedelta(minutes=1),
            end=observed2 + dt.timedelta(minutes=1),
        )
        self.assertEqual(len(rows), 2)

    async def test_device_snapshot_persists_locations(self) -> None:
        adapter = _FakeAdapter()
        adapter.device_rows = [
            {
                "szIDNO": "WXB310",
                "nOnline": 1,
                "groupId": 30000002,
                "nJingDu": "121.4737",
                "nWeiDu": "31.2304",
                "gpsTime": "2026-08-17 09:40:00",
                "ucMapType": 1,
            },
            {
                "szIDNO": "WXB358",
                "nOnline": 0,
                "groupId": 30000002,
                # zero sentinel coordinates -> skipped as invalid
                "nJingDu": "0",
                "nWeiDu": "0",
                "gpsTime": "2026-08-17 09:41:00",
            },
        ]
        scheduler, store, _ = _build(adapter)
        observed = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)  # = 10:00 +08:00
        result = await scheduler.run_cycle(observed_at=observed)
        self.assertTrue(result.all_successful)
        dev = next(i for i in result.sources if i.source == "device_status")
        self.assertEqual(dev.status, "ok")
        self.assertIn(
            "device_locations_stored=1",
            dev.quality_flags,
        )
        self.assertIn(
            "device_locations_invalid=1",
            dev.quality_flags,
        )
        locations = await store.fetch_device_location_events(
            start=observed - dt.timedelta(hours=1),
            end=observed,
        )
        self.assertEqual(len(locations), 1)
        event = locations[0]
        self.assertEqual(event.device_id, "WXB310")
        self.assertAlmostEqual(event.longitude, 121.4737)
        self.assertAlmostEqual(event.latitude, 31.2304)
        self.assertEqual(event.location_source, "mcs8_device_snapshot")
        self.assertEqual(event.gps_type_code, 1)
        self.assertIn("mcs8_device_snapshot", event.quality_flags)

    async def test_device_snapshot_locations_idempotent(self) -> None:
        adapter = _FakeAdapter()
        adapter.device_rows = [
            {
                "szIDNO": "WXB310",
                "nOnline": 1,
                "groupId": 30000002,
                "nJingDu": "121.4737",
                "nWeiDu": "31.2304",
                "gpsTime": "2026-08-17 09:40:00",
            }
        ]
        scheduler, store, _ = _build(adapter)
        observed1 = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=10)
        await scheduler.run_cycle(observed_at=observed1)
        r2 = await scheduler.run_cycle(observed_at=observed2)
        dev = next(i for i in r2.sources if i.source == "device_status")
        self.assertIn(
            "device_locations_stored=1",
            dev.quality_flags,
        )
        locations = await store.fetch_device_location_events(
            start=observed1 - dt.timedelta(hours=1),
            end=observed2,
        )
        # unchanged position must not inflate rows
        self.assertEqual(len(locations), 1)

    async def test_state_json_serializes_device_location_flags(self) -> None:
        adapter = _FakeAdapter()
        adapter.device_rows = [
            {
                "szIDNO": "WXB310",
                "nOnline": 1,
                "groupId": 30000002,
                "nJingDu": "121.4737",
                "nWeiDu": "31.2304",
                "gpsTime": "2026-08-17 09:40:00",
            }
        ]
        state_dir = "/tmp/mcs8-sched-test-state-json"
        scheduler, _, _ = _build(adapter, state_dir=state_dir)
        observed = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)
        await scheduler.run(period_seconds=1, max_cycles=1, stop_event=asyncio.Event())
        state = json.loads(
            (pathlib.Path(state_dir) / "scheduler_state.json")
            .read_text(encoding="utf-8")
        )
        cycle = state["1"]
        dev = next(
            s for s in cycle["sources"] if s["source"] == "device_status"
        )
        self.assertIn("device_locations_stored=1", dev["quality_flags"])

    async def test_device_transition_stored_once(self) -> None:
        adapter = _FakeAdapter()
        scheduler, store, _ = _build(adapter)
        observed1 = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)
        observed2 = observed1 + dt.timedelta(minutes=10)
        await scheduler.run_cycle(observed_at=observed1)
        adapter.device_rows[0]["nOnline"] = 0  # WXB310 offline
        r2 = await scheduler.run_cycle(observed_at=observed2)
        dev = next(i for i in r2.sources if i.source == "device_status")
        self.assertEqual(dev.stored_count, 1)
        self.assertIn(
            "cha_observed_transition",
            dev.quality_flags,
        )
        rows = await store.fetch_device_status_events(
            start=observed1 - dt.timedelta(minutes=1),
            end=observed2 + dt.timedelta(minutes=1),
        )
        self.assertEqual(len(rows), 3)

    async def test_source_isolation_media_failure(self) -> None:
        adapter = _FakeAdapter()
        adapter.media_rows = [
            {"id": "rec-1", "devId": "WXB310", "fType": 3,
             "startTime": "2026-08-17 09:30:00"}
        ]
        adapter.alarm_rows = [
            {"id": "alarm-1", "devId": "WXB358", "alarmType": 205,
             "alarmTime": "2026-08-17 09:35:00"}
        ]
        adapter.media_fail = True
        scheduler, store, _ = _build(adapter)
        observed = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)
        result = await scheduler.run_cycle(observed_at=observed)
        by_source = {item.source: item for item in result.sources}
        self.assertEqual(by_source["device_status"].status, "ok")
        self.assertEqual(by_source["media_files"].status, "error")
        self.assertEqual(by_source["media_files"].error_code, "MCS8_DATA_UPSTREAM_REJECTED")
        self.assertEqual(by_source["alarms"].status, "ok")
        self.assertFalse(result.all_successful)

    async def test_restart_uses_latest_known_device_state(self) -> None:
        adapter = _FakeAdapter()
        store = MemoryInspectionStore()
        scheduler1, store, _ = _build(adapter, store=store)
        observed1 = dt.datetime(2026, 8, 17, 2, 0, tzinfo=UTC)
        await scheduler1.run_cycle(observed_at=observed1)
        # simulate process restart: fresh scheduler over same store
        scheduler2, _, _ = _build(
            adapter,
            state_dir="/tmp/mcs8-sched-test-2",
            store=store,
        )
        observed2 = observed1 + dt.timedelta(minutes=10)
        r2 = await scheduler2.run_cycle(observed_at=observed2)
        dev = next(i for i in r2.sources if i.source == "device_status")
        self.assertEqual(dev.stored_count, 0)

    async def test_run_respects_period_and_kill_switch(self) -> None:
        adapter = _FakeAdapter()
        scheduler, _, _ = _build(adapter)
        stop = asyncio.Event()

        async def stopper():
            await asyncio.sleep(0.05)
            stop.set()

        asyncio.create_task(stopper())
        results = await scheduler.run(
            period_seconds=1,
            max_cycles=10,
            stop_event=stop,
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertLess(len(results), 10)

    async def test_run_zero_max_cycles_runs_until_stop(self) -> None:
        adapter = _FakeAdapter()
        scheduler, _, _ = _build(adapter)
        stop = asyncio.Event()

        async def stopper():
            await asyncio.sleep(0.05)
            stop.set()

        asyncio.create_task(stopper())
        results = await scheduler.run(
            period_seconds=1,
            max_cycles=0,
            stop_event=stop,
        )
        self.assertGreaterEqual(len(results), 1)

    async def test_run_logs_cycle_lifecycle_without_sensitive_values(self) -> None:
        adapter = _FakeAdapter()
        adapter.device_rows[0].update(
            {
                "nJingDu": "121.4737",
                "nWeiDu": "31.2304",
                "gpsTime": "2026-08-17 09:40:00",
            }
        )
        scheduler, _, _ = _build(adapter)
        stop = asyncio.Event()

        async def stopper() -> None:
            await asyncio.sleep(0.05)
            stop.set()

        asyncio.create_task(stopper())
        with self.assertLogs(
            "uvicorn.error.cha.inspection.mcs8_scheduler",
            level="INFO",
        ) as captured:
            results = await scheduler.run(
                period_seconds=60,
                max_cycles=0,
                stop_event=stop,
            )

        self.assertEqual(len(results), 1)
        output = "\n".join(captured.output)
        self.assertIn("scheduler_cycle_started cycle_index=1", output)
        self.assertIn("scheduler_cycle_completed cycle_index=1", output)
        self.assertIn("device_status=ok/2/2", output)
        self.assertIn("location_stored=1", output)
        self.assertIn("media_files=ok/0/0", output)
        self.assertIn("alarms=ok/0/0", output)
        self.assertIn("store_result=ok store_rows=2", output)
        self.assertIn("scheduler_waiting cycle_index=1 next_cycle_seconds=60", output)
        self.assertNotIn("server-token", output)


if __name__ == "__main__":
    unittest.main()
