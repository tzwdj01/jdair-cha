from __future__ import annotations

import asyncio
import time
import unittest
from types import SimpleNamespace

from app.data.store import PostgresPoolExhaustedError
from app.services.inspection_readiness import inspection_postgresql_readiness


class _Store:
    def __init__(self, result: bool = True, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    async def health_check(self) -> bool:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class InspectionPostgresqlReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_not_enabled_without_touching_stores(self) -> None:
        data_store = _Store()
        record_store = _Store()
        state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=False),
            data_store,
            record_store,
        )
        self.assertEqual(state["status"], "not_enabled")
        self.assertFalse(state["required"])
        self.assertEqual(data_store.calls, 0)
        self.assertEqual(record_store.calls, 0)

    async def test_reports_misconfigured_when_enabled_stores_are_missing(
        self,
    ) -> None:
        state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=True),
            None,
            _Store(),
        )
        self.assertEqual(state["status"], "misconfigured")
        self.assertTrue(state["required"])

    async def test_reports_ready_only_after_both_store_checks_pass(self) -> None:
        data_store = _Store()
        record_store = _Store()
        state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=True),
            data_store,
            record_store,
        )
        self.assertEqual(state["status"], "ready")
        self.assertTrue(state["required"])
        self.assertEqual(data_store.calls, 1)
        self.assertEqual(record_store.calls, 1)

    async def test_reports_unavailable_for_false_or_raised_health_check(
        self,
    ) -> None:
        false_state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=True),
            _Store(result=False),
            _Store(),
        )
        self.assertEqual(false_state["status"], "unavailable")

        raised_state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=True),
            _Store(),
            _Store(error=RuntimeError("database down")),
        )
        self.assertEqual(raised_state["status"], "unavailable")
        self.assertNotIn("database down", str(raised_state))

    async def test_reports_degraded_quickly_for_pool_busy_or_timeout(self) -> None:
        busy_state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=True),
            _Store(error=PostgresPoolExhaustedError("busy")),
            _Store(),
            health_check_timeout_seconds=0.1,
        )
        self.assertEqual(busy_state["status"], "degraded")
        self.assertNotIn("busy", str(busy_state))

        class _SlowStore:
            async def health_check(self) -> bool:
                await asyncio.sleep(0.2)
                return True

        started = time.monotonic()
        timeout_state = await inspection_postgresql_readiness(
            SimpleNamespace(inspection_store_pg_enabled=True),
            _SlowStore(),
            _Store(),
            health_check_timeout_seconds=0.02,
        )
        self.assertLess(time.monotonic() - started, 0.15)
        self.assertEqual(timeout_state["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
