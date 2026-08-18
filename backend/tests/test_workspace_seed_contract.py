from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "docs" / "contracts" / "workspace_seed_contract.md"
MATRIX = REPO_ROOT / "docs" / "contracts" / "workspace_seed_tests.md"
INDEX = REPO_ROOT / "docs" / "contracts" / "README.md"


class WorkspaceSeedContractTests(unittest.TestCase):
    def test_contract_docs_exist(self) -> None:
        self.assertTrue(CONTRACT.is_file(), CONTRACT)
        self.assertTrue(MATRIX.is_file(), MATRIX)

    def test_contract_mentions_required_seed_terms(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8").lower()
        for needle in ("workspace seed", ".gabo", "depth 9", "working set", "receipt", "resolver_contract.json"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_test_matrix_mentions_required_gates(self) -> None:
        text = MATRIX.read_text(encoding="utf-8").lower()
        for needle in ("startup", "no .gabo", "depth 9", "deterministic", "incremental", "rollback"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_test_matrix_covers_the_canonical_seed_scenarios(self) -> None:
        text = MATRIX.read_text(encoding="utf-8").lower()
        for needle in (
            "startup_current_dir",
            "startup_other_dir",
            "seed_prompt_when_missing",
            "seed_create_gabo",
            "deep_scan_depth_9",
            "deterministic_repeat",
            "incremental_refresh",
            "ultimo snapshot valido",
            "resolver",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_contract_index_links_seed_docs(self) -> None:
        text = INDEX.read_text(encoding="utf-8").lower()
        self.assertIn("resolver_contract.json", text)
        self.assertIn("workspace_seed_contract.md", text)
        self.assertIn("workspace_seed_tests.md", text)


if __name__ == "__main__":
    unittest.main()
