from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[1]

import project_memory  # noqa: E402
import commands  # noqa: E402


class ProjectSeedRuntimeTests(unittest.TestCase):
    def test_seed_project_writes_canonical_gabo_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")

            report = project_memory.seed_project(root, depth=3, ref=root)

            self.assertEqual(Path(report["root"]), root.resolve())
            self.assertTrue((root / ".gabo" / "workspace.json").is_file())
            self.assertTrue((root / ".gabo" / "link.json").is_file())
            self.assertTrue((root / ".gabo" / "live.json").is_file())
            self.assertTrue((root / ".gabo" / "tree.json").is_file())
            self.assertTrue((root / ".gabo" / "index.md").is_file())
            self.assertTrue((root / ".gabo" / "seed.meta.json").is_file())
            self.assertTrue((root / ".gabo" / "context" / "index.json").is_file())
            self.assertTrue((root / ".gabo" / "context" / "repository_map.json").is_file())
            self.assertTrue((root / ".gabo" / "context" / "working_set.json").is_file())

            meta = json.loads((root / ".gabo" / "seed.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["seed_depth"], 3)
            self.assertGreaterEqual(meta["files_scanned"], 2)
            self.assertGreaterEqual(meta["files_indexed"], 2)
            self.assertGreaterEqual(meta["symbols_indexed"], 1)
            self.assertGreaterEqual(meta["working_set_size"], 1)

    def test_project_command_seed_routes_to_seed_surface(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")

            def fake_load_tool_module(name: str, filename: str):
                return SimpleNamespace(
                    resolve_project_root=lambda value, allow_fallback_cwd=False: root,
                    seed_project=lambda project_root, depth=3, ref=None: project_memory.seed_project(project_root, depth=depth, ref=ref or project_root),
                )

            class DummyMgr:
                def rebind_project_root(self, _root):
                    return None

            original = commands._load_tool_module
            commands._load_tool_module = fake_load_tool_module
            try:
                result = commands.cmd_project(DummyMgr(), SimpleNamespace(), ["seed", str(root)])
            finally:
                commands._load_tool_module = original

            self.assertTrue(result["ok"], msg=result["message"])
            self.assertIn("Seeded workspace", result["message"])
            self.assertTrue((root / ".gabo" / "seed.meta.json").is_file())

    def test_project_command_seed_skips_rebind_when_root_is_already_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")

            class DummyMgr:
                project_root = root
                base_path = root

                def rebind_project_root(self, _root):
                    raise AssertionError("rebind_project_root should not run for the active root")

            def fake_load_tool_module(name: str, filename: str):
                return SimpleNamespace(
                    resolve_project_root=lambda value, allow_fallback_cwd=False: root,
                    seed_project=lambda project_root, depth=3, ref=None: project_memory.seed_project(project_root, depth=depth, ref=ref or project_root),
                )

            original = commands._load_tool_module
            commands._load_tool_module = fake_load_tool_module
            try:
                result = commands.cmd_project(DummyMgr(), SimpleNamespace(), ["seed", str(root)])
            finally:
                commands._load_tool_module = original

            self.assertTrue(result["ok"], msg=result["message"])
            self.assertTrue((root / ".gabo" / "workspace.json").is_file())

    def test_terminal_bago_exec_can_seed_project(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "bago_core.launcher",
                "--base-path",
                str(REPO),
                "exec",
                "/project",
                "seed",
            ],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stdout + "\n" + proc.stderr)
        self.assertIn("Seeded workspace at:", proc.stdout)
        self.assertIn("Working set size:", proc.stdout)
        self.assertTrue((REPO / ".gabo" / "seed.meta.json").is_file())


if __name__ == "__main__":
    unittest.main()
