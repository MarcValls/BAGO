from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "bago_code_forge_47_task_CODE-20260621-001.json"


class CodeForgeContractTests(unittest.TestCase):
    def test_contract_shape(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_id"], "CODE-20260621-001")
        self.assertEqual(payload["sprint"], 1)
        self.assertEqual(payload["operation"], "build_deterministic_classifier")
        self.assertIn("bago_core\\codegen\\task_classifier.py", payload["target_files"])
        self.assertIn(".bago\\core\\session_manager.py", payload["target_files"])
        self.assertIn("unsafe_or_unsupported", payload["classification_kinds"])
        self.assertIn("python -m unittest tests.test_code_forge_contract tests.test_code_forge_classifier -v", payload["validation_commands"])


if __name__ == "__main__":
    unittest.main()
