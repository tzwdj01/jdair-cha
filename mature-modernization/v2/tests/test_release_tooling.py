from __future__ import annotations

import unittest
from pathlib import Path


TEST_PATH = Path(__file__).resolve()


def _find_source_repository_root() -> Path | None:
    """Return the source checkout when tooling tests run outside a release tarball.

    Production packages deliberately contain application code and tests, not the
    repository-level deployment helpers.  Those helpers are tested from the
    source checkout before packaging; their source-only assertions are not
    applicable when the same test suite validates an extracted release artifact.
    """

    for candidate in (TEST_PATH.parents[1], TEST_PATH.parents[3]):
        if (candidate / "ops" / "mature_m3_final_release.sh").is_file():
            return candidate
    return None


REPO_ROOT = _find_source_repository_root()
RELEASE_SCRIPT = (
    REPO_ROOT / "ops" / "mature_m3_final_release.sh"
    if REPO_ROOT is not None
    else None
)
REHEARSAL_SCRIPT = (
    REPO_ROOT / "ops" / "mature_m3_final_release_rehearsal.sh"
    if REPO_ROOT is not None
    else None
)
PHASE6_ROLLBACK_REHEARSAL = (
    REPO_ROOT / "ops" / "mature_phase6_rollback_rehearsal.sh"
    if REPO_ROOT is not None
    else None
)
M4_PACKAGE_SCRIPT = (
    REPO_ROOT / "ops" / "mature_m4_inspection_build_package.py"
    if REPO_ROOT is not None
    else None
)
PHASE0_DEPLOY_SCRIPT = (
    REPO_ROOT / "ops" / "mature_phase0_deploy_v2.sh"
    if REPO_ROOT is not None
    else None
)
V2_ROLLBACK_SCRIPT = (
    REPO_ROOT / "ops" / "rollback-v2.sh"
    if REPO_ROOT is not None
    else None
)


@unittest.skipIf(
    REPO_ROOT is None,
    "repository-level release tooling is intentionally absent from release packages",
)
class ReleaseToolingTests(unittest.TestCase):
    def test_release_uses_configured_production_venv(self) -> None:
        assert RELEASE_SCRIPT is not None
        source = RELEASE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            'venv_python="${CHA_V2_VENV_PYTHON:-${root}/venv/bin/python}"',
            source,
        )
        self.assertIn(
            '"$venv_python" -m unittest discover -s tests -v',
            source,
        )
        self.assertIn("run_candidate_tests()", source)
        self.assertIn("CHA_*|PG*|DATABASE_URL|MCS8_*|AEE_*", source)
        self.assertIn("protected production runtime configuration", source)
        self.assertNotIn("python3 -m unittest", source)

    def test_release_rolls_back_only_after_current_switch(self) -> None:
        assert RELEASE_SCRIPT is not None
        source = RELEASE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("switched_current=false", source)
        self.assertIn("rollback_attempted=false", source)
        self.assertIn("trap - ERR", source)
        self.assertIn('switched_current=true', source)

    def test_isolated_rehearsal_covers_failure_paths(self) -> None:
        assert REHEARSAL_SCRIPT is not None
        source = REHEARSAL_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("test-failure", source)
        self.assertIn("health-failure", source)
        self.assertIn("production_paths_touched", source)
        self.assertIn("FAKE_EXPECT_TEST_ENV_SANITIZED", source)
        self.assertIn('test -z "${CHA_PG_HOST:-}"', source)
        self.assertNotIn("/opt/jdair-cha", source)

    def test_phase6_rollback_uses_bounded_live_health_retry(self) -> None:
        assert V2_ROLLBACK_SCRIPT is not None
        source = V2_ROLLBACK_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('health_attempts="${CHA_V2_HEALTH_ATTEMPTS:-12}"', source)
        self.assertIn('health_retry_seconds="${CHA_V2_HEALTH_RETRY_SECONDS:-0.5}"', source)
        self.assertIn("wait_for_live()", source)
        self.assertIn('systemctl restart "$service"', source)
        self.assertIn("/api/v2/health/live", source)
        self.assertIn("RUNNING_RELEASE", source)
        self.assertIn("RUNNING_COMMIT", source)
        self.assertIn("PACKAGE_HASH", source)
        self.assertNotIn("sleep 3", source)

    def test_phase6_rollback_rehearsal_is_disposable_and_retries_once(self) -> None:
        assert PHASE6_ROLLBACK_REHEARSAL is not None
        source = PHASE6_ROLLBACK_REHEARSAL.read_text(encoding="utf-8")
        self.assertIn("mktemp -d", source)
        self.assertIn("fake-bin", source)
        self.assertIn("FAKE_HEALTH_COUNT", source)
        self.assertIn("ROLLBACK_HEALTH_ATTEMPT=2", source)
        self.assertIn("M4_PHASE6_ROLLBACK_REHEARSAL=passed", source)
        self.assertNotIn("/opt/jdair-cha", source)

    def test_m4_package_carries_runtime_identity_and_rollback_helper(self) -> None:
        assert M4_PACKAGE_SCRIPT is not None
        source = M4_PACKAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('arcname="ops/rollback-v2.sh"', source)
        self.assertIn('tarfile.TarInfo("COMMIT")', source)
        self.assertIn("source_commit(root)", source)
        self.assertIn(
            '"status", "--porcelain", "--untracked-files=normal"',
            source,
        )
        self.assertIn("refusing to package a dirty source tree", source)

    def test_phase6_deploy_delegates_rollback_to_bounded_helper(self) -> None:
        assert PHASE0_DEPLOY_SCRIPT is not None
        source = PHASE0_DEPLOY_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("wait_for_v2_live()", source)
        self.assertIn('test -x "$release_dir/ops/rollback-v2.sh"', source)
        self.assertIn('exec "\\$(dirname "\\$0")/ops/rollback-v2.sh"', source)
        self.assertIn('printf \'%s\\n\' "$package_hash" > "$release_dir/PACKAGE_SHA256"', source)
        self.assertIn("RUNNING_RELEASE", source)
        self.assertIn("RUNNING_COMMIT", source)
        self.assertIn("PACKAGE_HASH", source)
        self.assertIn('"CHA_V2_FEATURE_INSPECTION_V2"', source)
        self.assertIn("expected_realtime_readonly", source)
        self.assertIn("expected_inspection", source)

    def test_phase6_canary_features_enable_inspection_without_disabling_realtime(
        self,
    ) -> None:
        assert REPO_ROOT is not None
        values = {}
        for line in (
            REPO_ROOT / "mature-modernization" / "v2" / "FEATURES.env"
        ).read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value

        self.assertEqual(values["CHA_V2_FEATURE_DASHBOARD_V2"], "true")
        self.assertEqual(values["CHA_V2_FEATURE_INSPECTION_V2"], "true")
        self.assertEqual(values["CHA_V2_FEATURE_REALTIME_READONLY"], "true")
        self.assertEqual(values["CHA_V2_FEATURE_REALTIME_AUDIO"], "false")
        self.assertEqual(values["CHA_V2_FEATURE_REALTIME_CONTROL"], "false")
        self.assertEqual(values["CHA_V2_FEATURE_ACCOUNT_POOL_V2"], "false")
        self.assertEqual(values["CHA_V2_FEATURE_RECORDS_V2"], "false")


if __name__ == "__main__":
    unittest.main()
