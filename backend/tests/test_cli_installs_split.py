"""FASE 6.4 tests for the cli_installs split.

Verifies that the four new modules (facts/discovery/summary/cli) are
importable, that the facade re-exports the public surface, and that the
end-to-end `python -m bago_core.cli_installs --plain` produces valid JSON.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


class CliInstallsSplitTests(unittest.TestCase):

    def test_facts_module(self) -> None:
        from bago_core import cli_installs_facts
        self.assertTrue(callable(cli_installs_facts.pid_alive))
        self.assertTrue(callable(cli_installs_facts.short_sig))
        self.assertTrue(callable(cli_installs_facts.read_version))
        self.assertTrue(callable(cli_installs_facts.read_tag))
        self.assertTrue(callable(cli_installs_facts.supervisor_state))
        # pid 0 must always be false
        self.assertFalse(cli_installs_facts.pid_alive(0))

    def test_discovery_module(self) -> None:
        from bago_core import cli_installs_discovery
        self.assertTrue(callable(cli_installs_discovery._scan))
        self.assertTrue(callable(cli_installs_discovery._classify))
        items = cli_installs_discovery._scan()
        self.assertIsInstance(items, list)
        # Each item has at minimum path/exists/mode/description.
        for it in items[:1]:
            self.assertIn("path", it)
            self.assertIn("exists", it)
            self.assertIn("mode", it)

    def test_summary_module(self) -> None:
        from bago_core.cli_installs_summary import summary
        out = summary([{"exists": True, "supervisor_alive": False,
                        "has_supervisor": True}])
        self.assertEqual(out["total_paths"], 1)
        self.assertEqual(out["existing"], 1)
        self.assertEqual(out["with_supervisor"], 1)
        self.assertEqual(out["with_supervisor_alive"], 0)
        self.assertIn("scanned_at", out)

    def test_cli_module(self) -> None:
        from bago_core import cli_installs_cli
        self.assertTrue(callable(cli_installs_cli.main))
        # Smoke: --help works.
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), \
             self.assertRaises(SystemExit) as cm:
            cli_installs_cli.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_facade_reexports(self) -> None:
        from bago_core import cli_installs
        # Facade must re-export both legacy names and the new submodules.
        self.assertTrue(callable(cli_installs.main))
        self.assertTrue(callable(cli_installs._scan))
        self.assertTrue(callable(cli_installs.summary))
        self.assertTrue(callable(cli_installs.pid_alive))

    def test_module_invocation_json_valid(self) -> None:
        r = subprocess.run(
            [sys.executable, "-m", "bago_core.cli_installs", "--plain"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        d = json.loads(r.stdout)
        self.assertIn("summary", d)
        self.assertIn("installations", d)
        self.assertIsInstance(d["installations"], list)

    def test_install_roles_support_writer_and_illustrator(self) -> None:
        from bago_core import cli_installs_discovery
        from bago_core import install_roles

        self.assertIn("writer", install_roles.ROLES)
        self.assertIn("illustrator", install_roles.ROLES)

        with TemporaryDirectory() as td:
            root = Path(td)
            selection_path = root / "install_selection.json"
            writer_root = root / "writer"
            illustrator_root = root / "illustrator"
            writer_root.mkdir()
            illustrator_root.mkdir()

            payload = {
                "version": 1,
                "updated_at": "",
                "roles": {
                    "writer": {
                        "path": str(writer_root),
                        "label": "Escritor",
                        "updated_at": "2026-06-30T00:00:00+00:00",
                    },
                    "illustrator": {
                        "path": str(illustrator_root),
                        "label": "Ilustrador",
                        "updated_at": "2026-06-30T00:00:00+00:00",
                    },
                },
                "selection_file": str(selection_path),
            }

            with patch.object(install_roles, "selection_file", return_value=selection_path), \
                 patch.object(cli_installs_discovery, "load_selection", return_value=payload):
                install_roles.set_role("writer", writer_root, strict=False)
                install_roles.set_role("illustrator", illustrator_root, strict=False)
                selected = install_roles.role_paths(install_roles.load_selection())
                self.assertEqual(selected["writer"], str(writer_root.resolve()))
                self.assertEqual(selected["illustrator"], str(illustrator_root.resolve()))

                scanned = cli_installs_discovery._scan()
                writer_item = next(item for item in scanned if item["description"] == "Seleccion writer")
                illustrator_item = next(item for item in scanned if item["description"] == "Seleccion illustrator")
                self.assertIn("writer", writer_item["selection_roles"])
                self.assertIn("illustrator", illustrator_item["selection_roles"])
                self.assertTrue(writer_item["selected_writer"])
                self.assertTrue(illustrator_item["selected_illustrator"])


if __name__ == "__main__":
    unittest.main()
