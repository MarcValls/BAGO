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
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
