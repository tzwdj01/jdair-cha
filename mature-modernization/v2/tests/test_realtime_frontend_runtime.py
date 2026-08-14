from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE_TEST = ROOT / "tests" / "realtime_runtime_test.cjs"


class RealtimeFrontendRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not available")
    def test_runtime_media_offline_normalization_and_cleanup(self) -> None:
        result = subprocess.run(
            [shutil.which("node") or "node", str(NODE_TEST)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("realtime runtime tests passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
