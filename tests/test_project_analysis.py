from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".bago" / "tools"))

import project_memory  # noqa: E402


class ProjectAnalysisTests(unittest.TestCase):
    def test_analyze_data_suggests_common_checks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            (root / "package.json").write_text("{}", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "README.md").write_text("# demo\n", encoding="utf-8")

            data = project_memory.analyze_data(root)
            text = project_memory.format_analysis(data)

            self.assertIn("Stack detected:", text)
            self.assertIn("git status -sb", text)
            self.assertIn("python -m pytest -q", text)
            self.assertIn("npm test", text)
            self.assertIn("npm run build", text)
            self.assertIn("Directory snapshot:", text)


if __name__ == "__main__":
    unittest.main()
