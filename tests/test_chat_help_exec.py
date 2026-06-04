"""Tests for chat help coverage and headless slash execution."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class ChatHelpExecTests(unittest.TestCase):

    def _run_exec(self, *command: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as td:
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bago_core.launcher",
                    "--base-path",
                    td,
                    "exec",
                    *command,
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=60,
            )

    def test_help_mentions_all_registered_slash_commands(self) -> None:
        sys.path.insert(0, str(REPO / ".bago" / "chat"))
        from commands import COMMAND_REGISTRY, execute

        help_text = execute("/help", object(), object())["message"]
        for name in COMMAND_REGISTRY:
            self.assertIn(f"/{name}", help_text, name)
        self.assertIn("bago exec /comando [args...]", help_text)
        self.assertIn("Modo no interactivo:", help_text)

    def test_headless_exec_invokes_help(self) -> None:
        result = self._run_exec("/help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Comandos disponibles", result.stdout)
        self.assertIn("Modo no interactivo:", result.stdout)

    def test_headless_exec_menu_falls_back_to_text(self) -> None:
        result = self._run_exec("/menu")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Comandos disponibles", result.stdout)

    def test_headless_exec_exports_command_catalog_json(self) -> None:
        result = self._run_exec("/commands", "json")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "bago.command_catalog.v1")
        self.assertEqual(payload["headless_entrypoint"], "bago exec /comando [args...]")
        self.assertIn("help", payload["registered_commands"])
        self.assertIn("doctor", payload["catalog_commands"])

    def test_headless_exec_doctor_reports_readiness(self) -> None:
        result = self._run_exec("/doctor")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("BAGO DOCTOR", result.stdout)
        self.assertIn("command_catalog", result.stdout)

    def test_repl_uses_shared_menu_sections(self) -> None:
        sys.path.insert(0, str(REPO / ".bago" / "chat"))
        import commands
        import repl

        self.assertIs(repl.MENU_SECTIONS, commands.MENU_SECTIONS)


if __name__ == "__main__":
    unittest.main()
