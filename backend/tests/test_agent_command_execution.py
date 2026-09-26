from __future__ import annotations

import importlib.util
import builtins
import sys
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[1] / ".bago" / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

import agent_command_execution

AGENT_GATEWAY_PATH = AGENTS_DIR / "agent_gateway.py"
_GATEWAY_SPEC = importlib.util.spec_from_file_location(
    "agent_gateway_command_execution_under_test", AGENT_GATEWAY_PATH,
)
assert _GATEWAY_SPEC is not None and _GATEWAY_SPEC.loader is not None
agent_gateway = importlib.util.module_from_spec(_GATEWAY_SPEC)
sys.modules[_GATEWAY_SPEC.name] = agent_gateway
_GATEWAY_SPEC.loader.exec_module(agent_gateway)


def _manager(tmp_path: Path):
    framework = tmp_path / "runtime"
    launcher = framework / "bago_core" / "launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# launcher\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return type("Manager", (), {
        "framework_root": framework,
        "base_path": workspace,
        "session_id": "agent-test-session",
    })()


def test_agent_command_is_bound_to_exact_launcher_session_and_consumed_permit(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    monkeypatch.setattr(agent_command_execution.sys.stdin, "isatty", lambda: True)
    calls = []

    def execute(request, *, confirmation_text, manager):
        calls.append((request, confirmation_text, manager))
        return (
            {"executed": True, "exit_code": 0, "stdout": "ok", "stderr": ""},
            {"state": "consumed"},
        )

    from bago_core import cli_execution
    monkeypatch.setattr(cli_execution, "execute_cli_effect", execute)
    result = agent_command_execution.execute_agent_command(
        ["status", "--json"], intent="status", manager=manager,
    )

    request, confirmation, used_manager = calls[0]
    assert result["stdout"] == "ok"
    assert request.effect_id == "process.execute"
    assert request.actor_kind == "user"
    assert request.principal_id == "interactive-local-user"
    assert request.session_id == manager.session_id
    assert request.source_surface == "cli.agent.dispatch"
    assert request.target["python_module"] == "bago_core.launcher"
    assert request.target["python_root"] == str(manager.framework_root.resolve())
    assert request.arguments == {"argv": ["status", "--json"]}
    assert "bago status --json" in confirmation
    assert used_manager is manager


def test_agent_command_consumes_tty_permit_before_gateway_process_spawn(tmp_path, monkeypatch):
    import authorization_boundary
    import execution_adapters.process as process_adapter

    manager = _manager(tmp_path)
    monkeypatch.setattr(agent_command_execution.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(authorization_boundary, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(builtins, "input", lambda _prompt: "s")
    spawns = []

    def run(command, **kwargs):
        spawns.append((command, kwargs))
        return type("Completed", (), {"returncode": 0, "stdout": "status-ok", "stderr": ""})()

    monkeypatch.setattr(process_adapter.subprocess, "run", run)
    result = agent_command_execution.execute_agent_command(
        ["status", "--json"], intent="status", manager=manager,
    )

    assert result["effect_id"] == "process.execute"
    assert result["executed"] is True
    assert result["stdout"] == "status-ok"
    assert len(spawns) == 1
    command, kwargs = spawns[0]
    assert command[1:3] == ["-m", "bago_core.launcher"]
    assert command[-2:] == ["status", "--json"]
    assert kwargs["shell"] is False
    assert kwargs["stdin"] is process_adapter.subprocess.DEVNULL


def test_agent_command_fails_before_authorization_without_manager_or_tty(tmp_path, monkeypatch):
    calls = []
    from bago_core import cli_execution
    monkeypatch.setattr(cli_execution, "execute_cli_effect", lambda *a, **k: calls.append((a, k)))

    with pytest.raises(RuntimeError, match="active SessionManager"):
        agent_command_execution.execute_agent_command(["status"], intent="status", manager=None)

    manager = _manager(tmp_path)
    monkeypatch.setattr(agent_command_execution.sys.stdin, "isatty", lambda: False)
    with pytest.raises(RuntimeError, match="TTY approval"):
        agent_command_execution.execute_agent_command(["status"], intent="status", manager=manager)
    assert calls == []


def test_agent_command_rejects_invalid_argv_before_authorization(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    monkeypatch.setattr(agent_command_execution.sys.stdin, "isatty", lambda: True)
    calls = []
    from bago_core import cli_execution
    monkeypatch.setattr(cli_execution, "execute_cli_effect", lambda *a, **k: calls.append((a, k)))

    with pytest.raises(ValueError, match="invalid argument"):
        agent_command_execution.execute_agent_command(["status", "\x00bad"], intent="status", manager=manager)
    assert calls == []


def test_local_adapter_routes_fixed_intent_argv_through_gateway_interface(monkeypatch):
    calls = []
    manager = object()
    monkeypatch.setattr(
        agent_gateway, "execute_agent_command",
        lambda argv, **kwargs: calls.append((argv, kwargs)) or {"exit_code": 0, "stdout": "ok", "stderr": ""},
    )
    request = agent_gateway.AgentRequest(
        intent="status", payload={"args": ["--json"]}, execution_manager=manager,
    )

    result = agent_gateway.LocalAdapter().execute(request)

    assert result.success is True
    assert calls == [(["status", "--json"], {"intent": "status", "manager": manager, "timeout": 30})]


def test_ollama_cannot_supply_or_expand_executable_argv(monkeypatch):
    adapter = agent_gateway.OllamaAdapter()
    monkeypatch.setattr(adapter, "health", lambda: True)
    monkeypatch.setattr(adapter, "_call_ollama", lambda prompt, timeout: "bago db migrate")
    calls = []
    monkeypatch.setattr(agent_gateway, "execute_agent_command", lambda *a, **k: calls.append((a, k)))

    result = adapter.execute(agent_gateway.AgentRequest(intent="status"))

    assert result.success is False
    assert "bloqueada antes del proceso" in result.error
    assert calls == []


def test_ollama_direct_uses_only_canonical_local_intent_command(monkeypatch):
    adapter = agent_gateway.OllamaAdapter()
    monkeypatch.setattr(adapter, "health", lambda: True)
    monkeypatch.setattr(adapter, "_call_ollama", lambda prompt, timeout: "direct")
    calls = []
    monkeypatch.setattr(
        agent_gateway, "execute_agent_command",
        lambda argv, **kwargs: calls.append((argv, kwargs)) or {"exit_code": 0, "stdout": "ok", "stderr": ""},
    )
    manager = object()

    result = adapter.execute(agent_gateway.AgentRequest(
        intent="status", payload={"args": ["--json"]}, execution_manager=manager,
    ))

    assert result.success is True
    assert calls == [(["status", "--json"], {"intent": "status", "manager": manager, "timeout": 30})]
