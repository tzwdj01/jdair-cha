from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import Settings, env_bool, normalize_base_url


class ConfigTests(unittest.TestCase):
    def test_env_bool_accepts_only_explicit_true_values(self) -> None:
        with patch.dict(os.environ, {"TEST_FLAG": "enabled"}, clear=False):
            self.assertTrue(env_bool("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "off"}, clear=False):
            self.assertFalse(env_bool("TEST_FLAG", True))

    def test_features_are_disabled_by_default(self) -> None:
        names = [
            "CHA_V2_FEATURE_DASHBOARD_V2",
            "CHA_V2_FEATURE_REALTIME_READONLY",
            "CHA_V2_FEATURE_REALTIME_AUDIO",
            "CHA_V2_FEATURE_REALTIME_CONTROL",
            "CHA_V2_FEATURE_ACCOUNT_POOL_V2",
            "CHA_V2_FEATURE_RECORDS_V2",
        ]
        with patch.dict(os.environ, {name: "" for name in names}, clear=False):
            features = Settings.from_env().public_features()
        self.assertEqual(set(features.values()), {False})

    def test_legacy_requirement_tracks_compatible_features(self) -> None:
        with patch.dict(
            os.environ,
            {"CHA_V2_FEATURE_DASHBOARD_V2": "true"},
            clear=False,
        ):
            self.assertTrue(Settings.from_env().legacy_is_required())

    def test_dashboard_runtime_defaults_are_positive(self) -> None:
        settings = Settings.from_env()
        self.assertGreater(settings.dashboard_device_ttl_seconds, 0)
        self.assertGreater(settings.dashboard_video_ttl_seconds, 0)
        self.assertGreater(settings.dashboard_initial_wait_seconds, 0)
        self.assertTrue(settings.dashboard_state_dir)

    def test_base_url_is_normalized_and_validated(self) -> None:
        self.assertEqual(
            normalize_base_url("http://127.0.0.1:8790/"),
            "http://127.0.0.1:8790",
        )
        with self.assertRaises(ValueError):
            normalize_base_url("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
