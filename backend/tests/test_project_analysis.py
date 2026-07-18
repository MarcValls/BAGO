from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = (REPO / "release_version.txt").read_text(encoding="utf-8").strip()

import project_memory  # noqa: E402
from bago_core.parsers import build_parser  # noqa: E402


class ProjectAnalysisTests(unittest.TestCase):
    def test_find_project_root_requires_project_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertIsNone(project_memory.find_project_root(root))
            (root / ".gabo").mkdir()
            self.assertEqual(project_memory.find_project_root(root), root.resolve())

    def test_analyze_data_suggests_common_checks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text("{}", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "README.md").write_text("# demo\n", encoding="utf-8")

            data = project_memory.analyze_data(root)
            text = project_memory.format_analysis(data)

            self.assertIn("Stack detected:", text)
            self.assertIn("python -m pytest -q", text)
            self.assertIn("npm test", text)
            self.assertIn("npm run build", text)
            self.assertIn("Directory snapshot:", text)
            self.assertNotIn("No se detecta .git", text)

    def test_project_parser_accepts_root_after_analyze(self) -> None:
        parser = build_parser(EXPECTED_VERSION, str(REPO), "ollama-local", "llama3.2:3b")
        args = parser.parse_args(["project", "analyze", "--root", str(REPO)])
        self.assertEqual(args.command, "project")
        self.assertEqual(args.project_cmd, "analyze")
        self.assertEqual(args.root, str(REPO))

    def test_project_parser_accepts_root_before_analyze(self) -> None:
        parser = build_parser(EXPECTED_VERSION, str(REPO), "ollama-local", "llama3.2:3b")
        args = parser.parse_args(["project", "--root", str(REPO), "analyze"])
        self.assertEqual(args.command, "project")
        self.assertEqual(args.project_cmd, "analyze")
        self.assertEqual(args.root, str(REPO))

    def test_project_parser_accepts_root_on_all_subcommands(self) -> None:
        parser = build_parser(EXPECTED_VERSION, str(REPO), "ollama-local", "llama3.2:3b")
        for cmd in ("init", "status", "link"):
            with self.subTest(cmd=cmd):
                after = parser.parse_args(["project", cmd, "--root", str(REPO)])
                before = parser.parse_args(["project", "--root", str(REPO), cmd])
                self.assertEqual(after.command, "project")
                self.assertEqual(after.project_cmd, cmd)
                self.assertEqual(after.root, str(REPO))
                self.assertEqual(before.command, "project")
                self.assertEqual(before.project_cmd, cmd)
                self.assertEqual(before.root, str(REPO))


if __name__ == "__main__":
    unittest.main()
