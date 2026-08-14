from __future__ import annotations

import unittest
from pathlib import Path


TEST_PATH = Path(__file__).resolve()
REPO_ROOT = next(
    candidate
    for candidate in (TEST_PATH.parents[1], TEST_PATH.parents[3])
    if (candidate / "ops" / "mature_m3_final_release.sh").is_file()
)
RELEASE_SCRIPT = REPO_ROOT / "ops" / "mature_m3_final_release.sh"
REHEARSAL_SCRIPT = (
    REPO_ROOT / "ops" / "mature_m3_final_release_rehearsal.sh"
)


class ReleaseToolingTests(unittest.TestCase):
    def test_release_uses_configured_production_venv(self) -> None:
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
        source = RELEASE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("switched_current=false", source)
        self.assertIn("rollback_attempted=false", source)
        self.assertIn("trap - ERR", source)
        self.assertIn('switched_current=true', source)

    def test_isolated_rehearsal_covers_failure_paths(self) -> None:
        source = REHEARSAL_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("test-failure", source)
        self.assertIn("health-failure", source)
        self.assertIn("production_paths_touched", source)
        self.assertNotIn("/opt/jdair-cha", source)


if __name__ == "__main__":
    unittest.main()
