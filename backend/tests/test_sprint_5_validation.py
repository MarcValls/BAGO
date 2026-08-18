from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Sprint5ValidationTests(unittest.TestCase):
    def test_public_contracts_are_flat_in_docs_contracts(self) -> None:
        required = [
            "bago_v4_runtime_contract.json",
            "bago_v4_repl_contract.md",
            "bago_v4_evidence_contract.md",
            "bago_v4_knowledge_contract.md",
            "bago_v4_governance_contract.md",
            "bago_v4_engineering_contract.md",
        ]
        for name in required:
            with self.subTest(contract=name):
                self.assertTrue((ROOT / "docs" / "contracts" / name).is_file(), name)

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

    def test_tool_registry_surface_is_present(self) -> None:
        tools = ROOT / ".bago" / "tools"
        for name in [
            "_registry_entries.py",
            "_registry_models.py",
            "_registry_paths.py",
            "_registry_taxonomy.py",
            "tool_registry.py",
        ]:
            with self.subTest(tool_surface=name):
                self.assertTrue((tools / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
