from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[1]

import project_memory  # noqa: E402
import commands  # noqa: E402
import authorization_boundary as auth  # noqa: E402
import handlers_command  # noqa: E402


class ProjectSeedRuntimeTests(unittest.TestCase):
    def test_seed_project_writes_canonical_gabo_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")

            report = project_memory._execute_cli_project_write(
                root, "seed", arguments={"depth": 3, "ref": str(root)},
            )

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
                project_root = root
                session_id = "project-seed-session"

                def rebind_project_root(self, _root):
                    raise AssertionError("project.write must not rebind before authorization")

            original = commands._load_tool_module
            original_state_root = auth.state_root
            commands._load_tool_module = fake_load_tool_module
            auth.state_root = lambda: root.parent / f".{root.name}-authorization"
            try:
                result = commands.execute_local_cli(
                    f'/project seed "{root}"',
                    DummyMgr(),
                    SimpleNamespace(),
                )
            finally:
                commands._load_tool_module = original
                auth.state_root = original_state_root

            self.assertTrue(result["ok"], msg=result["message"])
            self.assertIn("Seeded workspace", result["message"])
            self.assertTrue((root / ".gabo" / "seed.meta.json").is_file())

    def test_http_project_command_cannot_mint_direct_user_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# unchanged\n", encoding="utf-8")

            class DummyMgr:
                project_root = root
                session_id = "project-http-session"
                provider = "test"
                model = "test"

                def status(self):
                    return {"project_root": str(self.project_root)}

            class FakeContext:
                session_mgr = DummyMgr()
                switch_engine = SimpleNamespace()

                def __init__(self):
                    self.response = None

                def channel(self, _body):
                    return "http"

                def timed_call(self, callback):
                    return callback(), 0

                def json_safe(self, value):
                    return value

                def record_shadow(self, **_kwargs):
                    return None

                def send_json(self, status, payload):
                    self.response = (status, payload)

            def snapshot():
                return {
                    path.relative_to(root).as_posix(): (
                        "dir" if path.is_dir() else path.read_bytes()
                    )
                    for path in root.rglob("*")
                }

            context = FakeContext()
            before = snapshot()
            import request_context
            original_build_context = request_context.build_context
            request_context.build_context = lambda _handler: context
            try:
                handlers_command.handle(
                    SimpleNamespace(),
                    {
                        "command": f"/project init {root}",
                        "invocation_source": "interactive_tty",
                    },
                )
            finally:
                request_context.build_context = original_build_context

            self.assertEqual(context.response[0], 200)
            self.assertFalse(context.response[1]["ok"])
            self.assertIn("autorización explícita", context.response[1]["message"])
            self.assertEqual(snapshot(), before)
            self.assertFalse((root / ".bago").exists())
            self.assertFalse((root / ".gabo").exists())

    def test_project_command_seed_skips_rebind_when_root_is_already_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")

            class DummyMgr:
                project_root = root
                base_path = root
                session_id = "project-seed-active-session"

                def rebind_project_root(self, _root):
                    raise AssertionError("rebind_project_root should not run for the active root")

            def fake_load_tool_module(name: str, filename: str):
                return SimpleNamespace(
                    resolve_project_root=lambda value, allow_fallback_cwd=False: root,
                    seed_project=lambda project_root, depth=3, ref=None: project_memory.seed_project(project_root, depth=depth, ref=ref or project_root),
                )

            original = commands._load_tool_module
            original_state_root = auth.state_root
            commands._load_tool_module = fake_load_tool_module
            auth.state_root = lambda: root.parent / f".{root.name}-authorization"
            try:
                result = commands.execute_local_cli(
                    f'/project seed "{root}"',
                    DummyMgr(),
                    SimpleNamespace(),
                )
            finally:
                commands._load_tool_module = original
                auth.state_root = original_state_root

            self.assertTrue(result["ok"], msg=result["message"])
            self.assertTrue((root / ".gabo" / "workspace.json").is_file())

    def test_terminal_bago_exec_can_seed_project(self) -> None:
        env = dict(os.environ)
        with tempfile.TemporaryDirectory() as auth_td:
            env["BAGO_STATE_ROOT"] = str(Path(auth_td) / "authorization")
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
                env=env,
            )

        self.assertEqual(proc.returncode, 0, msg=proc.stdout + "\n" + proc.stderr)
        self.assertIn("Seeded workspace at:", proc.stdout)
        self.assertIn("Working set size:", proc.stdout)
        self.assertTrue((REPO / ".gabo" / "seed.meta.json").is_file())


if __name__ == "__main__":
    unittest.main()
