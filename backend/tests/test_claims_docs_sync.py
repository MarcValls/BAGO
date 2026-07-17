from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CLAIMS = ROOT / "docs" / "CLAIMS.md"


class ClaimsDocsSyncTests(unittest.TestCase):
    def test_readme_status_rows_point_to_canonical_docs(self) -> None:
        readme = README.read_text(encoding="utf-8").lower()
        claims = CLAIMS.read_text(encoding="utf-8").lower()

        self.assertIn("current product status", readme)
        self.assertIn("the stable mvp is intentionally small", readme)
        self.assertIn("post-mvp or experimental", readme)
        self.assertIn("docs/claims.md", readme)
        self.assertIn("docs/testing.md", readme)
        self.assertIn("docs/mvp.md", readme)
        self.assertIn("docs/support_matrix.md", readme)
        self.assertIn("docs/security.md", readme)
        self.assertIn("docs/ui_canonical_contract.md", readme)

        for label in [
            "| persistent session |",
            "| provider/model switch |",
            "| ollama local startup |",
            "| evidence bundles |",
            "| security validation |",
            "| react ui |",
        ]:
            with self.subTest(label=label):
                self.assertNotIn(label, readme)

        self.assertIn("bago has a functional cli", claims)
        self.assertIn("bago install/update/uninstall flow is supported", claims)
        self.assertIn("bago security validation is executable", claims)
        self.assertNotIn("python ", claims)

    def test_readme_experimental_rows_match_claims_boundaries(self) -> None:
        readme = README.read_text(encoding="utf-8").lower()
        claims = CLAIMS.read_text(encoding="utf-8").lower()

        expected = {
            "rl policy layer": "docs/mvp.md",
            "agents and autopilot": "docs/mvp.md",
            "cloud multiprovider completeness": "docs/support_matrix.md",
        }

        for label, docref in expected.items():
            with self.subTest(label=label):
                self.assertIn(label, readme)
                self.assertIn(docref, readme)

        self.assertIn("c++ runtime", readme)
        self.assertIn("experimental", readme)
        self.assertIn("advanced knowledge/embedding store", readme)
        self.assertIn("stable mvp", readme)


if __name__ == "__main__":
    unittest.main()
