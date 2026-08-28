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
        self.assertNotIn("/opt/jdair-cha", source)


if __name__ == "__main__":
    unittest.main()
