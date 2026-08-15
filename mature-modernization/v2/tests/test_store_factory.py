from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.data.store import MemoryInspectionStore
from app.services.store_factory import build_inspection_store


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


if __name__ == "__main__":
    unittest.main()
