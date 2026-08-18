from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

import cli_bridge
from cli_bridge import build_prompt
import codex as codex_module
import copilot as copilot_module
from codex import CodexAdapter
from copilot import CopilotAdapter


def test_cli_bridge_prompt_is_single_line_and_keeps_final_user_message() -> None:
    prompt = build_prompt([{"role": "user", "content": "BAGO_BRIDGE_OK"}], "system")
    assert "\n" not in prompt
    assert "BAGO_BRIDGE_OK" in prompt


def test_codex_cli_bridge_uses_approved_workspace(tmp_path: Path) -> None:
    adapter = CodexAdapter({"cli_path": "codex", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.api_key = None
    with patch.object(codex_module, "run_cli", return_value="ok") as run:
        response = adapter._chat_cli([{"role": "user", "content": "hola"}], "gpt-5.4-mini", "")
    command = run.call_args.args[0]
    assert response.content == "ok"
    assert "--approve-for-me" in command
    assert "--sandbox" not in command
    assert run.call_args.kwargs["input_text"].startswith("BAGO_PROVIDER_BRIDGE_JSON=")


def test_copilot_cli_bridge_does_not_auto_approve_tools(tmp_path: Path) -> None:
    adapter = CopilotAdapter({"cli_path": "copilot", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.token = None
    with patch.object(adapter, "_configured_mcp_servers", return_value=["memory"]), patch.object(copilot_module, "run_cli", return_value="ok") as run:
        response = adapter._chat_cli([{"role": "user", "content": "hola"}], "gpt-5.4-mini", "")
    command = run.call_args.args[0]
    assert response.content == "ok"
    assert "--no-ask-user" in command
    assert "--allow-all" not in command
    assert "--allow-all-tools" not in command
    assert command[command.index("--mode") + 1] == "plan"
    assert "--deny-tool=shell(*)" in command
    assert "--deny-tool=write" in command
    assert command[command.index("--disable-mcp-server") + 1] == "memory"


def test_copilot_cli_bridge_uses_temporary_attachment_for_long_prompts(tmp_path: Path) -> None:
    adapter = CopilotAdapter({"cli_path": "copilot", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.token = None
    attached: list[Path] = []

    def fake_run(command, cwd, timeout):
        path = Path(command[command.index("--attachment") + 1])
        assert path.exists()
        assert "BAGO_PROVIDER_BRIDGE_JSON=" in path.read_text(encoding="utf-8")
        attached.append(path)
        return "ok"

    with patch.object(copilot_module, "run_cli", side_effect=fake_run):
        response = adapter._chat_cli([{"role": "user", "content": "x" * 25000}], "gpt-5.4-mini", "")

    assert response.content == "ok"
    assert response.metadata["prompt_transport"] == "attachment"
    assert attached and not attached[0].exists()


def test_cli_failure_is_structured_and_sanitized(tmp_path: Path) -> None:
    adapter = CodexAdapter({"cli_path": "codex", "cli_authenticated": True, "base_path": str(tmp_path)})
    adapter.api_key = None
    with patch.object(codex_module, "run_cli", side_effect=RuntimeError("ERROR: usage limit")):
        response = adapter.chat([{"role": "user", "content": "hola"}], "gpt-5.4-mini")
    assert response.finish_reason == "error"
    assert response.metadata["error"] is True


def test_cli_failure_hides_bridge_payload_and_keeps_usage_limit() -> None:
    result = subprocess.CompletedProcess(
        args=["codex"],
        returncode=1,
        stdout='BAGO_PROVIDER_BRIDGE_JSON={"messages":["previous error"]}',
        stderr="ERROR: You've hit your usage limit.",
    )
    with patch.object(cli_bridge.subprocess, "run", return_value=result):
        try:
            cli_bridge.run_cli(["codex"], ROOT, timeout=1)
        except RuntimeError as exc:
            assert "usage limit" in str(exc)
            assert "BAGO_PROVIDER_BRIDGE_JSON" not in str(exc)
        else:
            raise AssertionError("run_cli must raise for a failing command")
