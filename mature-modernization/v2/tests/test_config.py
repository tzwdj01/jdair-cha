from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config as config_module
from app.config import (
    Settings,
    env_bool,
    env_positive_float_map,
    normalize_base_url,
    release_identity,
)


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
            "CHA_V2_FEATURE_INSPECTION_V2",
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
        self.assertGreater(settings.realtime_session_ttl_seconds, 0)
        self.assertGreater(settings.realtime_command_timeout_seconds, 0)
        self.assertEqual(settings.realtime_max_streams_per_session, 6)
        self.assertEqual(settings.aee_username, "")
        self.assertEqual(settings.aee_password, "")
        self.assertFalse(settings.realtime_aee_is_configured())
        self.assertFalse(settings.realtime_canary_is_configured())
        self.assertFalse(
            settings.realtime_canary_user_allowed("realtime-tester")
        )
        self.assertFalse(settings.realtime_is_configured())
        self.assertEqual(settings.mcs8_host, "")
        self.assertFalse(settings.mcs8_is_configured())
        self.assertFalse(settings.scheduler_enabled)
        self.assertEqual(settings.scheduler_period_seconds, 600)
        self.assertEqual(settings.scheduler_max_cycles, 6)

    def test_mcs8_is_configured_only_when_complete(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CHA_V2_MCS8_HOST": "mcs8.test.invalid",
                "CHA_V2_MCS8_WS_PORT": "7711",
                "CHA_V2_MCS8_API_PORT": "7712",
                "CHA_V2_MCS8_USERNAME": "test-user",
                "CHA_V2_MCS8_PASSWORD": "test-password",
            },
            clear=False,
        ):
            settings = Settings.from_env()
            self.assertTrue(settings.mcs8_is_configured())
        with patch.dict(
            os.environ,
            {"CHA_V2_MCS8_HOST": "mcs8.test.invalid"},
            clear=False,
        ):
            self.assertFalse(Settings.from_env().mcs8_is_configured())

    def test_scheduler_requires_explicit_enable(self) -> None:
        with patch.dict(
            os.environ,
            {"CHA_V2_INSPECTION_SCHEDULER_ENABLED": "true"},
            clear=False,
        ):
            self.assertTrue(Settings.from_env().scheduler_enabled)

    def test_realtime_canary_allowlist_is_explicit_and_casefolded(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "CHA_V2_REALTIME_CANARY_USERS": (
                    "realtime-tester, Internal.User "
                ),
            },
            clear=False,
        ):
            settings = Settings.from_env()
        self.assertTrue(settings.realtime_canary_is_configured())
        self.assertTrue(
            settings.realtime_canary_user_allowed("REALTIME-TESTER")
        )
        self.assertTrue(
            settings.realtime_canary_user_allowed("internal.user")
        )
        self.assertFalse(settings.realtime_canary_user_allowed("other-user"))

    def test_realtime_requires_both_aee_secrets_and_canary_users(
        self,
    ) -> None:
        complete = {
            "CHA_V2_REALTIME_CANARY_USERS": "realtime-tester",
            "CHA_V2_AEE_API_BASE_URL": "https://aee.example.test",
            "CHA_V2_AEE_ORIGIN": "https://aee.example.test",
            "CHA_V2_AEE_GATEWAY_HOST": "gateway.example.test",
            "CHA_V2_AEE_GATEWAY_PORT": "7711",
            "CHA_V2_AEE_USERNAME": "server-side-user",
            "CHA_V2_AEE_PASSWORD": "server-side-secret",
        }
        with patch.dict(os.environ, complete, clear=False):
            settings = Settings.from_env()
        self.assertTrue(settings.realtime_aee_is_configured())
        self.assertTrue(settings.realtime_canary_is_configured())
        self.assertTrue(settings.realtime_is_configured())

    def test_realtime_stream_limit_is_bounded(self) -> None:
        with patch.dict(
            os.environ,
            {"CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION": "99"},
            clear=False,
        ):
            self.assertEqual(
                Settings.from_env().realtime_max_streams_per_session,
                6,
            )

    def test_realtime_operational_limits_have_safe_defaults(self) -> None:
        settings = Settings.from_env()
        self.assertEqual(settings.realtime_max_sessions_per_owner, 3)
        self.assertEqual(settings.realtime_session_create_limit, 10)
        self.assertEqual(settings.realtime_session_create_window_seconds, 60)
        self.assertEqual(settings.realtime_max_retained_sessions, 128)
        self.assertFalse(settings.realtime_allow_missing_ws_origin)

    def test_realtime_operational_limits_fall_back_for_non_positive_values(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "CHA_V2_REALTIME_MAX_SESSIONS_PER_OWNER": "0",
                "CHA_V2_REALTIME_SESSION_CREATE_LIMIT": "-1",
                "CHA_V2_REALTIME_SESSION_CREATE_WINDOW_SECONDS": "0",
            },
            clear=False,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.realtime_max_sessions_per_owner, 3)
        self.assertEqual(settings.realtime_session_create_limit, 10)
        self.assertEqual(settings.realtime_session_create_window_seconds, 60)

    def test_base_url_is_normalized_and_validated(self) -> None:
        self.assertEqual(
            normalize_base_url("http://127.0.0.1:8790/"),
            "http://127.0.0.1:8790",
        )
        with self.assertRaises(ValueError):
            normalize_base_url("file:///etc/passwd")

    def test_positive_float_map_keeps_only_usable_thresholds(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TEST_THRESHOLDS": (
                    '{"long_no_upload_hours": 72, '
                    '"stale_location_hours": 24, '
                    '"bad": -5, "zero": 0, "bool": true}'
                )
            },
            clear=False,
        ):
            values = env_positive_float_map("TEST_THRESHOLDS")
        self.assertEqual(
            values,
            {
                "long_no_upload_hours": 72.0,
                "stale_location_hours": 24.0,
            },
        )

    def test_positive_float_map_absent_or_invalid_is_empty(self) -> None:
        with patch.dict(os.environ, {"TEST_THRESHOLDS": ""}, clear=False):
            self.assertEqual(env_positive_float_map("TEST_THRESHOLDS"), {})
        with patch.dict(
            os.environ,
            {"TEST_THRESHOLDS": "not-json"},
            clear=False,
        ):
            self.assertEqual(env_positive_float_map("TEST_THRESHOLDS"), {})
        with patch.dict(
            os.environ,
            {"TEST_THRESHOLDS": "[1,2]"},
            clear=False,
        ):
            self.assertEqual(env_positive_float_map("TEST_THRESHOLDS"), {})

    def test_release_identity_reads_runtime_markers_without_env_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            release_root = Path(raw) / "phase6-candidate"
            release_root.mkdir()
            (release_root / "COMMIT").write_text(
                "0123456789abcdef0123456789abcdef01234567\n",
                encoding="utf-8",
            )
            (release_root / "PACKAGE_SHA256").write_text(
                "package-test-hash\n",
                encoding="utf-8",
            )
            with patch.object(config_module, "RELEASE_ROOT", release_root):
                identity = release_identity()
        self.assertEqual(identity["running_release"], "phase6-candidate")
        self.assertEqual(
            identity["running_commit"],
            "0123456789abcdef0123456789abcdef01234567",
        )
        self.assertEqual(identity["package_hash"], "package-test-hash")


if __name__ == "__main__":
    unittest.main()
