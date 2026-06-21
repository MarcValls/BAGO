from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Sprint5ValidationTests(unittest.TestCase):
    def test_snapshot_leakage_script_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "test_no_snapshot_leakage.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_test_suite_size_is_sane(self) -> None:
        tests = [p for p in ROOT.rglob("test_*.py") if ".pytest_cache" not in p.parts]
        self.assertGreaterEqual(len(tests), 20)

    def test_manifest_and_registry_alignment(self) -> None:
        manifest = json.loads((ROOT / ".bago" / "tools.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["tool_count"], 170)
        self.assertEqual(len(manifest["tools"]), 170)


if __name__ == "__main__":
    unittest.main()

