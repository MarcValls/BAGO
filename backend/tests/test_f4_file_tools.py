#!/usr/bin/env python3
"""test_f4_file_tools.py — Tests for the 5 file manipulation tools.

Tests each tool via subprocess (as BAGO executes them) with a temp workspace:
  - file_read.py
  - file_write.py
  - file_edit.py
  - dir_list.py
  - project_scaffold.py

Each tool resolves paths against BAGO_WORKSPACE_ROOT env var.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / ".bago" / "tools"
PYTHON = sys.executable


def _ensure_tools_path() -> None:
    path = str(TOOLS_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


def _ensure_core_path() -> None:
    path = str(Path(__file__).resolve().parent.parent / ".bago" / "core")
    if path not in sys.path:
        sys.path.insert(0, path)


def _run_tool(script: str, args: list[str], workspace: str) -> dict:
    """Run a tool script with BAGO_WORKSPACE_ROOT set and return parsed JSON."""
    env = os.environ.copy()
    env["BAGO_WORKSPACE_ROOT"] = workspace
    cmd = [PYTHON, str(TOOLS_DIR / script), *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"_raw_stdout": completed.stdout, "_raw_stderr": completed.stderr, "_returncode": completed.returncode}


class TestFileRead(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="bago_test_")
        (Path(self.ws) / "hello.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_read_full_file(self):
        result = _run_tool("file_read.py", ["--path", "hello.txt"], self.ws)
        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "line1\nline2\nline3\n")
        self.assertEqual(result["total_lines"], 3)

    def test_read_with_offset_limit(self):
        result = _run_tool("file_read.py", ["--path", "hello.txt", "--offset", "1", "--limit", "1"], self.ws)
        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "line2")
        self.assertTrue(result["truncated"])

    def test_read_missing_file(self):
        result = _run_tool("file_read.py", ["--path", "nonexistent.txt"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"].lower())

    def test_read_forbidden_path(self):
        result = _run_tool("file_read.py", ["--path", ".git/config"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())

    def test_read_outside_workspace(self):
        result = _run_tool("file_read.py", ["--path", "..", "secret.txt"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("outside workspace", result["error"].lower())

    def test_read_missing_path_arg(self):
        result = _run_tool("file_read.py", [], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("missing", result["error"].lower())


class TestFileWrite(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="bago_test_")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_write_new_file(self):
        result = _run_tool("file_write.py", ["--path", "new.txt", "--content", "hello world"], self.ws)
        self.assertTrue(result["ok"])
        self.assertTrue(result["created"])
        self.assertFalse(result["overwritten"])
        self.assertEqual(result["bytes_written"], 11)
        content = (Path(self.ws) / "new.txt").read_text(encoding="utf-8")
        self.assertEqual(content, "hello world")

    def test_write_overwrites_existing(self):
        (Path(self.ws) / "existing.txt").write_text("old content", encoding="utf-8")
        result = _run_tool("file_write.py", ["--path", "existing.txt", "--content", "new content"], self.ws)
        self.assertTrue(result["ok"])
        self.assertTrue(result["overwritten"])
        self.assertFalse(result["created"])

    def test_write_creates_parent_dirs(self):
        result = _run_tool("file_write.py", ["--path", "src/components/App.tsx", "--content", "export default function App() {}"], self.ws)
        self.assertTrue(result["ok"])
        self.assertTrue((Path(self.ws) / "src" / "components" / "App.tsx").exists())

    def test_write_forbidden_path(self):
        result = _run_tool("file_write.py", ["--path", ".env", "--content", "SECRET=123"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())

    def test_write_outside_workspace(self):
        result = _run_tool("file_write.py", ["--path", "..", "escape.txt", "--content", "data"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("outside workspace", result["error"].lower())

    def test_write_missing_content(self):
        result = _run_tool("file_write.py", ["--path", "test.txt"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("missing", result["error"].lower())


class TestFileEdit(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="bago_test_")
        (Path(self.ws) / "app.tsx").write_text(
            "function oldName() { return 1 }\nfunction other() { return 2 }\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_edit_first_occurrence(self):
        result = _run_tool("file_edit.py", ["--path", "app.tsx", "--old", "oldName", "--new", "newName"], self.ws)
        self.assertTrue(result["ok"])
        self.assertEqual(result["replacements"], 1)
        content = (Path(self.ws) / "app.tsx").read_text(encoding="utf-8")
        self.assertIn("newName", content)

    def test_edit_replace_all(self):
        (Path(self.ws) / "multi.txt").write_text("foo foo foo\n", encoding="utf-8")
        result = _run_tool("file_edit.py", ["--path", "multi.txt", "--old", "foo", "--new", "bar", "--replace-all"], self.ws)
        self.assertTrue(result["ok"])
        self.assertEqual(result["replacements"], 3)
        content = (Path(self.ws) / "multi.txt").read_text(encoding="utf-8")
        self.assertEqual(content, "bar bar bar\n")

    def test_edit_old_not_found(self):
        result = _run_tool("file_edit.py", ["--path", "app.tsx", "--old", "nonexistent", "--new", "whatever"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"].lower())

    def test_edit_missing_file(self):
        result = _run_tool("file_edit.py", ["--path", "ghost.txt", "--old", "a", "--new", "b"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"].lower())

    def test_edit_forbidden_path(self):
        result = _run_tool("file_edit.py", ["--path", ".bago/secret.py", "--old", "a", "--new", "b"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())

    def test_edit_missing_args(self):
        result = _run_tool("file_edit.py", ["--path", "app.tsx"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("missing", result["error"].lower())


class TestDirList(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="bago_test_")
        (Path(self.ws) / "file_a.txt").write_text("a", encoding="utf-8")
        (Path(self.ws) / "file_b.py").write_text("b", encoding="utf-8")
        (Path(self.ws) / "subdir").mkdir()
        (Path(self.ws) / "subdir" / "child.txt").write_text("c", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_list_root(self):
        result = _run_tool("dir_list.py", ["--path", "."], self.ws)
        self.assertTrue(result["ok"])
        names = [e["name"] for e in result["entries"]]
        self.assertIn("file_a.txt", names)
        self.assertIn("file_b.py", names)
        self.assertIn("subdir", names)
        self.assertEqual(result["count"], 3)

    def test_list_recursive(self):
        result = _run_tool("dir_list.py", ["--path", ".", "--recursive"], self.ws)
        self.assertTrue(result["ok"])
        subdir_entry = [e for e in result["entries"] if e["name"] == "subdir"][0]
        self.assertIn("children", subdir_entry)
        child_names = [c["name"] for c in subdir_entry["children"]]
        self.assertIn("child.txt", child_names)

    def test_list_nonexistent_dir(self):
        result = _run_tool("dir_list.py", ["--path", "nope"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"].lower())

    def test_list_forbidden_path(self):
        result = _run_tool("dir_list.py", ["--path", "node_modules"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())

    def test_list_outside_workspace(self):
        result = _run_tool("dir_list.py", ["--path", ".."], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("outside workspace", result["error"].lower())


class TestProjectScaffold(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="bago_test_")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_scaffold_react_vite(self):
        result = _run_tool("project_scaffold.py", ["--name", "my-react-app", "--template", "react-vite"], self.ws)
        self.assertTrue(result["ok"])
        self.assertEqual(result["template"], "react-vite")
        self.assertIn("package.json", result["files_created"])
        self.assertIn("src/App.tsx", result["files_created"])
        self.assertTrue((Path(self.ws) / "my-react-app" / "package.json").exists())
        pkg = json.loads((Path(self.ws) / "my-react-app" / "package.json").read_text())
        self.assertEqual(pkg["name"], "my-react-app")

    def test_scaffold_python_fastapi(self):
        result = _run_tool("project_scaffold.py", ["--name", "my-api", "--template", "python-fastapi"], self.ws)
        self.assertTrue(result["ok"])
        self.assertIn("main.py", result["files_created"])
        main_content = (Path(self.ws) / "my-api" / "main.py").read_text()
        self.assertIn("my-api", main_content)

    def test_scaffold_python_cli(self):
        result = _run_tool("project_scaffold.py", ["--name", "my-cli", "--template", "python-cli"], self.ws)
        self.assertTrue(result["ok"])
        self.assertIn("main.py", result["files_created"])

    def test_scaffold_static_web(self):
        result = _run_tool("project_scaffold.py", ["--name", "my-site", "--template", "static-web"], self.ws)
        self.assertTrue(result["ok"])
        self.assertIn("index.html", result["files_created"])
        self.assertIn("styles.css", result["files_created"])

    def test_scaffold_list_templates(self):
        result = _run_tool("project_scaffold.py", ["--list"], self.ws)
        self.assertTrue(result["ok"])
        self.assertIn("templates", result)
        self.assertIn("react-vite", result["templates"])
        self.assertIn("python-fastapi", result["templates"])

    def test_scaffold_unknown_template(self):
        result = _run_tool("project_scaffold.py", ["--name", "test", "--template", "rust-lang"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("unknown template", result["error"].lower())

    def test_scaffold_existing_dir(self):
        (Path(self.ws) / "existing").mkdir()
        result = _run_tool("project_scaffold.py", ["--name", "existing", "--template", "react-vite"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("already exists", result["error"].lower())

    def test_scaffold_forbidden_name(self):
        result = _run_tool("project_scaffold.py", ["--name", ".git", "--template", "react-vite"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())

    def test_scaffold_missing_name(self):
        result = _run_tool("project_scaffold.py", ["--template", "react-vite"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("missing", result["error"].lower())

    def test_scaffold_default_template_is_react_vite(self):
        result = _run_tool("project_scaffold.py", ["--name", "default-tmpl"], self.ws)
        self.assertTrue(result["ok"])
        self.assertEqual(result["template"], "react-vite")


class TestToolRegistryIntegration(unittest.TestCase):
    """Verify the registry loads and exposes structured entries."""

    def test_registry_contains_file_tools(self):
        _ensure_tools_path()
        from tool_registry import REGISTRY, get_cmd_names, load_registry
        names = list(get_cmd_names())
        self.assertGreater(len(names), 0)
        self.assertEqual(load_registry(), REGISTRY)
        for expected in ["auto-heal", "secret-scan", "todo-scan"]:
            self.assertIn(expected, names, f"Missing tool: {expected}")

    def test_to_openai_has_schemas(self):
        _ensure_tools_path()
        from tool_registry import REGISTRY
        sample = REGISTRY["auto-heal"]
        self.assertIsInstance(sample.schema, dict)
        self.assertEqual(sample.cmd, "auto-heal")
        self.assertTrue(sample.description)

    def test_workspace_root_passed_to_registry(self):
        _ensure_tools_path()
        from tool_registry import load_registry
        self.assertEqual(load_registry(Path(TOOLS_DIR / "tool_registry.py")), load_registry())


class TestDevMode(unittest.TestCase):
    """Test that BAGO_DEV_MODE=1 disables forbidden path and workspace boundary checks."""

    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="bago_dev_")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _run_dev(self, script: str, args: list[str]) -> dict:
        """Run a tool with BAGO_DEV_MODE=1 set."""
        env = os.environ.copy()
        env["BAGO_WORKSPACE_ROOT"] = self.ws
        env["BAGO_DEV_MODE"] = "1"
        cmd = [PYTHON, str(TOOLS_DIR / script), *args]
        completed = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"_raw": completed.stdout, "_err": completed.stderr, "_rc": completed.returncode}

    def test_dev_read_forbidden_path(self):
        (Path(self.ws) / ".bago").mkdir()
        (Path(self.ws) / ".bago" / "config.json").write_text('{"ok": true}', encoding="utf-8")
        result = self._run_dev("file_read.py", ["--path", ".bago/config.json"])
        self.assertTrue(result["ok"], f"Dev mode should allow .bago/ reads: {result}")
        self.assertIn("true", result["content"])

    def test_dev_write_forbidden_path(self):
        (Path(self.ws) / "state").mkdir()
        result = self._run_dev("file_write.py", ["--path", "state/data.json", "--content", '{"test": 1}'])
        self.assertTrue(result["ok"], f"Dev mode should allow state/ writes: {result}")
        self.assertTrue((Path(self.ws) / "state" / "data.json").exists())

    def test_dev_edit_forbidden_path(self):
        (Path(self.ws) / ".env").write_text("OLD=value", encoding="utf-8")
        result = self._run_dev("file_edit.py", ["--path", ".env", "--old", "OLD", "--new", "NEW"])
        self.assertTrue(result["ok"], f"Dev mode should allow .env edits: {result}")
        content = (Path(self.ws) / ".env").read_text()
        self.assertIn("NEW", content)

    def test_dev_list_forbidden_path(self):
        (Path(self.ws) / "node_modules").mkdir()
        (Path(self.ws) / "node_modules" / "pkg.json").write_text("{}", encoding="utf-8")
        result = self._run_dev("dir_list.py", ["--path", "node_modules"])
        self.assertTrue(result["ok"], f"Dev mode should allow node_modules/ listing: {result}")
        self.assertEqual(result["count"], 1)

    def test_dev_scaffold_forbidden_name(self):
        result = self._run_dev("project_scaffold.py", ["--name", "state", "--template", "python-cli"])
        self.assertTrue(result["ok"], f"Dev mode should allow 'state' as project name: {result}")
        self.assertTrue((Path(self.ws) / "state" / "main.py").exists())

    def test_dev_read_outside_workspace(self):
        # In dev mode, absolute paths outside workspace should be allowed
        import tempfile as tf
        ext_dir = tf.mkdtemp(prefix="bago_ext_")
        try:
            ext_file = Path(ext_dir) / "external.txt"
            ext_file.write_text("external content", encoding="utf-8")
            result = self._run_dev("file_read.py", ["--path", str(ext_file)])
            self.assertTrue(result["ok"], f"Dev mode should allow reads outside workspace: {result}")
            self.assertIn("external content", result["content"])
        finally:
            shutil.rmtree(ext_dir, ignore_errors=True)

    def test_dev_write_outside_workspace(self):
        import tempfile as tf
        ext_dir = tf.mkdtemp(prefix="bago_ext_")
        try:
            result = self._run_dev("file_write.py", ["--path", str(Path(ext_dir) / "out.txt"), "--content", "dev write"])
            self.assertTrue(result["ok"], f"Dev mode should allow writes outside workspace: {result}")
            self.assertEqual((Path(ext_dir) / "out.txt").read_text(), "dev write")
        finally:
            shutil.rmtree(ext_dir, ignore_errors=True)

    def test_dev_mode_not_active_by_default(self):
        """Without BAGO_DEV_MODE, forbidden paths are still blocked."""
        (Path(self.ws) / ".bago").mkdir()
        (Path(self.ws) / ".bago" / "config.json").write_text('{}', encoding="utf-8")
        result = _run_tool("file_read.py", ["--path", ".bago/config.json"], self.ws)
        self.assertFalse(result["ok"])
        self.assertIn("forbidden", result["error"].lower())


class TestPathGuardDevMode(unittest.TestCase):
    """Test PathGuard respects dev_mode flag."""

    def test_pathguard_dev_mode_allows_forbidden(self):
        _ensure_core_path()
        from guardrails import PathGuard
        pg = PathGuard(dev_mode=True)
        result = pg.check("file-read", {"path": ".bago/config.json"})
        self.assertFalse(result.blocked)

    def test_pathguard_normal_mode_blocks_forbidden(self):
        _ensure_core_path()
        from guardrails import PathGuard
        pg = PathGuard(dev_mode=False)
        result = pg.check("file-read", {"path": ".bago/config.json"})
        self.assertTrue(result.blocked)

    def test_pathguard_dev_mode_empty_args(self):
        _ensure_core_path()
        from guardrails import PathGuard
        pg = PathGuard(dev_mode=True)
        result = pg.check("file-read", {})
        self.assertFalse(result.blocked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
