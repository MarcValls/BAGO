from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

from cli_bridge import build_prompt
import codex as codex_module
import copilot as copilot_module
from codex import CodexAdapter
from copilot import CopilotAdapter


def test_cli_bridge_prompt_is_single_line_and_keeps_final_user_message() -> None:
    prompt = build_prompt([{"role": "user", "content": "BAGO_BRIDGE_OK"}], "system")
    assert "\n" not in prompt
    assert "BAGO_BRIDGE_OK" in prompt


def test_codex_cli_bridge_uses_read_only_sandbox(tmp_path: Path) -> None:
    adapter = CodexAdapter({"cli_path": "codex", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.api_key = None
    with patch.object(codex_module, "run_cli", return_value="ok") as run:
        response = adapter._chat_cli([{"role": "user", "content": "hola"}], "gpt-5.4-mini", "")
    command = run.call_args.args[0]
    assert response.content == "ok"
    assert ["--sandbox", "read-only"] == command[command.index("--sandbox"):command.index("--sandbox") + 2]
    assert run.call_args.kwargs["input_text"].startswith("BAGO_PROVIDER_BRIDGE_JSON=")


def test_copilot_cli_bridge_does_not_auto_approve_tools(tmp_path: Path) -> None:
    adapter = CopilotAdapter({"cli_path": "copilot", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.token = None
    with patch.object(copilot_module, "run_cli", return_value="ok") as run:
        response = adapter._chat_cli([{"role": "user", "content": "hola"}], "gpt-5.4-mini", "")
    command = run.call_args.args[0]
    assert response.content == "ok"
    assert "--no-ask-user" in command
    assert "--allow-all" not in command
    assert "--allow-all-tools" not in command


def test_cli_failure_is_structured_and_sanitized(tmp_path: Path) -> None:
    adapter = CodexAdapter({"cli_path": "codex", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.api_key = None
    with patch.object(codex_module, "run_cli", side_effect=RuntimeError("ERROR: usage limit")):
        response = adapter.chat([{"role": "user", "content": "hola"}], "gpt-5.4-mini")
    assert response.finish_reason == "error"
    assert response.metadata["error"] is True
