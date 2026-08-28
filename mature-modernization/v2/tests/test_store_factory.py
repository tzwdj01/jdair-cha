from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.data.store import MemoryInspectionStore
from app.data.store import (
    PostgresInspectionRecordStore,
    PostgresInspectionStore,
)
from app.services.store_factory import (
    build_inspection_record_store,
    build_inspection_store,
)


def _settings(*, environment: str, mode: str) -> Settings:
    with patch.dict(
        os.environ,
        {
            "CHA_V2_ENVIRONMENT": environment,
            "CHA_V2_INSPECTION_STORE_MODE": mode,
        },
        clear=False,
    ):
        return Settings.from_env()


class StoreFactoryTests(unittest.TestCase):
    def test_production_never_returns_memory_store(self) -> None:
        settings = _settings(
            environment="production",
            mode="memory",
        )
        self.assertEqual(settings.inspection_store_mode, "memory")
        self.assertIsNone(build_inspection_store(settings))

    def test_non_production_memory_mode_returns_memory_store(self) -> None:
        settings = _settings(
            environment="development",
            mode="memory",
        )
        store = build_inspection_store(settings)
        self.assertIsInstance(store, MemoryInspectionStore)

    def test_non_production_empty_mode_returns_none(self) -> None:
        settings = _settings(
            environment="development",
            mode="",
        )
        self.assertIsNone(build_inspection_store(settings))

    def test_unknown_mode_returns_none(self) -> None:
        settings = _settings(
            environment="development",
            mode="postgres",
        )
        self.assertIsNone(build_inspection_store(settings))

    def test_production_pg_gate_disabled_returns_none(self) -> None:
        settings = _settings(
            environment="production",
            mode="",
        )
        self.assertFalse(settings.inspection_store_pg_enabled)
        self.assertIsNone(build_inspection_store(settings))
        self.assertIsNone(build_inspection_record_store(settings))

    def test_production_pg_gate_enabled_returns_pg_stores(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CHA_V2_ENVIRONMENT": "production",
                "CHA_V2_INSPECTION_STORE_PG_ENABLED": "true",
                "CHA_PG_HOST": "127.0.0.1",
                "CHA_PG_PORT": "5432",
                "CHA_PG_DATABASE": "cha_m4_rehearsal",
                "CHA_PG_USER": "cha_m4_app",
                "CHA_PG_PASSWORD": "test-pg-password",
                "CHA_PG_SSLMODE": "disable",
                "CHA_PG_SCHEMA": "inspection",
            },
            clear=False,
        ):
            settings = Settings.from_env()
            self.assertTrue(settings.inspection_store_pg_enabled)
            store = build_inspection_store(settings)
            record_store = build_inspection_record_store(settings)
        self.assertIsInstance(store, PostgresInspectionStore)
        self.assertIsInstance(record_store, PostgresInspectionRecordStore)


if __name__ == "__main__":
    unittest.main()
