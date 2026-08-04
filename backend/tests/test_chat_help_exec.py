"""Tests for chat help coverage and headless slash execution."""
from __future__ import annotations

import json
import io
import contextlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        from commands import COMMAND_REGISTRY, execute

        help_text = execute("/help", object(), object())["message"]
        for name in COMMAND_REGISTRY:
            self.assertIn(f"/{name}", help_text, name)
        self.assertIn("bago exec /comando [args...]", help_text)
        self.assertIn("Modo no interactivo:", help_text)
        self.assertIn("/project [analyze|status|init|link|seed|sync]", help_text)

    def test_roadmap_command_exposes_three_iterations(self) -> None:
        from commands import execute

        result = execute("/roadmap", object(), object())
        self.assertTrue(result["ok"], msg=result["message"])
        self.assertIn("Roadmap", result["message"])
        self.assertEqual(len(result["data"]["iterations"]), 3)
        self.assertEqual(result["data"]["status"], "verified")

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
        self.assertIn("ui", payload["registered_commands"])
        self.assertEqual(set(payload["catalog_commands"]), set(payload["registered_commands"]))

    def test_headless_exec_doctor_reports_readiness(self) -> None:
        result = self._run_exec("/doctor")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("BAGO DOCTOR", result.stdout)
        self.assertIn("command_catalog", result.stdout)

    def test_headless_exec_doctor_from_home_uses_safe_fallback(self) -> None:
        env = os.environ.copy()
        env["BAGO_SESSION_MIRROR"] = "0"
        env["PYTHONPATH"] = str(REPO) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bago_core.launcher",
                "exec",
                "/doctor",
            ],
            cwd=str(Path.home()),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("BAGO DOCTOR", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_launcher_defaults_base_path_to_cwd(self) -> None:
        from bago_core import launcher

        captured: dict[str, str] = {}

        class DummyParser:
            def parse_args(self, argv: list[str]):
                return type("Args", (), {"command": None})()

        class DummyConfigManager:
            def __init__(self, base_path: str) -> None:
                captured["config_base"] = base_path

            @property
            def default_provider(self) -> str:
                return "ollama-local"

            @property
            def default_model(self) -> str:
                return "llama3.2:3b"

        def fake_build_parser(version: str, base: str, default_provider: str, default_model: str) -> DummyParser:
            captured["parser_base"] = base
            captured["default_provider"] = default_provider
            captured["default_model"] = default_model
            return DummyParser()

        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            with (
                patch.object(launcher.os, "getcwd", return_value=str(cwd)),
                patch.object(launcher, "_load_install_config", return_value={"runtime": {"default_provider": "codex", "default_model": "gpt-5.4-mini"}}),
                patch("config_manager.ConfigManager", DummyConfigManager),
                patch.object(launcher, "build_parser", side_effect=fake_build_parser),
                patch.object(launcher, "_dispatch", return_value=0),
            ):
                rc = launcher.main([])

        self.assertEqual(rc, 0)
        self.assertEqual(captured["parser_base"], str(cwd))
        self.assertEqual(captured["config_base"], str(cwd))
        self.assertEqual(captured["default_provider"], "codex")
        self.assertEqual(captured["default_model"], "gpt-5.4-mini")

    def test_launcher_profiles_uses_profile_root_helper(self) -> None:
        from bago_core import launcher

        buf = io.StringIO()
        with (
            patch.object(launcher, "_profile_root", return_value=Path(r"C:\Program Files\BAGO")) as profile_root,
            patch.object(launcher, "workspace_root", return_value=Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")),
            contextlib.redirect_stdout(buf),
        ):
            rc = launcher.cmd_profiles(type("Args", (), {})())

        self.assertEqual(rc, 0)
        self.assertIn("stable : C:\\Program Files\\BAGO", buf.getvalue())
        profile_root.assert_called_once_with("stable")

    def test_repl_uses_shared_menu_sections(self) -> None:
        import commands
        import repl

        self.assertIs(repl.MENU_SECTIONS, commands.MENU_SECTIONS)

    def test_repl_detects_directory_paths(self) -> None:
        from repl_utils import looks_like_directory_path

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(looks_like_directory_path(str(root)), root.resolve())
        self.assertIsNone(looks_like_directory_path("hola"))

    def test_renderer_exposes_rc4_response_contract_line(self) -> None:
        import renderer

        line = renderer.response_contract_line()
        self.assertIn("RC4", line)
        self.assertIn("canon mutable", line)
        self.assertIn("estado/evidencia/cambio/validación/siguiente paso", line)

    def test_renderer_prints_contract_line_before_assistant_output(self) -> None:
        import renderer

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            renderer.print_message("assistant", "respuesta técnica")
        output = buf.getvalue()
        self.assertIn("RC4", output)
        self.assertIn("respuesta técnica", output)
        self.assertLess(output.index("RC4"), output.index("respuesta técnica"))


if __name__ == "__main__":
    unittest.main()
