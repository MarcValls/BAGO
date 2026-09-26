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
    runtime = tmp_path / "runtime"
    framework = runtime / ".bago"
    launcher = runtime / "bago_core" / "launcher.py"
    launcher.parent.mkdir(parents=True)
    framework.mkdir(parents=True)
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
    assert request.target["python_root"] == str(manager.framework_root.resolve().parent)
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
    assert command[1:4] == ["-P", "-m", "bago_core.launcher"]
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
    assert calls == [(["node", "status", "--json"], {"intent": "status", "manager": manager, "timeout": 30})]


def test_local_adapter_rejects_workspace_override_arguments():
    for override in ("--root=C:/other-workspace", "--roo=C:/other-workspace", "--base=C:/other-workspace"):
        request = agent_gateway.AgentRequest(intent="scan", payload={"args": [override]})
        with pytest.raises(ValueError, match="cannot override"):
            agent_gateway.LocalAdapter.command_argv(request)


def test_local_adapter_health_uses_real_launcher_path():
    assert agent_gateway.LocalAdapter().health() is True


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
    assert calls == [(["node", "status", "--json"], {"intent": "status", "manager": manager, "timeout": 30})]


def test_public_bago_agent_dispatch_forwards_only_gateway_arguments(monkeypatch):
    from bago_core.commands import cmd_tools
    from bago_core.parsers import build_parser

    calls = []
    gateway = type("Gateway", (), {
        "main": staticmethod(lambda argv: calls.append(argv) or 0),
    })()
    monkeypatch.setattr(
        "bago_core.resolver.load_module_from_path",
        lambda name, path: gateway,
    )

    parser = build_parser("test", str(Path(__file__).resolve().parents[1]), "local", "model")
    args = parser.parse_args([
        "agent", "dispatch", "task_create", "--adapter", "ollama",
        "--arg", "title", "--arg=--priority", "--arg", "high",
        "--timeout", "45", "--dry-run", "--json",
    ])
    result = cmd_tools.cmd_agent(args)

    assert result == 0
    assert calls == [[
        "dispatch", "task_create", "--adapter", "ollama",
        "--arg=title", "--arg=--priority", "--arg=high",
        "--dry-run", "--json", "--timeout", "45",
    ]]


def test_public_bago_agent_dispatch_cannot_override_active_session_workspace(capsys):
    from argparse import Namespace
    from bago_core.commands import cmd_tools

    result = cmd_tools.cmd_agent(Namespace(
        root="C:/other-workspace", agent_cmd="dispatch", intent="status",
    ))

    assert result == 2
    assert "lo determina la sesión activa" in capsys.readouterr().err


def test_agent_gateway_cli_blocks_dispatch_without_tty_before_loading_session(monkeypatch, capsys):
    monkeypatch.setattr(agent_gateway.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        "bago_core.user_state_paths.state_root",
        lambda: (_ for _ in ()).throw(AssertionError("session state must not load")),
    )

    result = agent_gateway.main(["dispatch", "status"])

    assert result == 1
    assert "TTY interactivo" in capsys.readouterr().err


def test_agent_gateway_loads_command_authority_from_static_file():
    import inspect

    assert Path(inspect.getsourcefile(agent_gateway.execute_agent_command)).resolve() == (
        AGENTS_DIR / "agent_command_execution.py"
    ).resolve()


def test_agent_gateway_blocks_unsupported_adapter_intent_before_execution(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_gateway.AgentGateway, "_emit_event", lambda *args, **kwargs: None)
    adapter = type("Adapter", (), {
        "name": "cloud",
        "capability": lambda self: type("Capability", (), {"supported_intents": ["status"]})(),
        "execute": lambda self, request: calls.append(request),
    })()
    monkeypatch.setattr(agent_gateway.AdapterRegistry, "get", lambda _name: adapter)

    result = agent_gateway.AgentGateway().dispatch(
        agent_gateway.AgentRequest(intent="context", source={"adapter": "cloud"}),
    )

    assert result.success is False
    assert "no admite" in result.error
    assert calls == []


def test_cloud_adapter_mutating_intent_is_blocked_before_health_or_execute(monkeypatch):
    cloud = agent_gateway.CloudAdapter(url="https://cloud.invalid")
    calls = []
    monkeypatch.setattr(agent_gateway.AgentGateway, "_emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(cloud, "health", lambda: calls.append("health") or True)
    monkeypatch.setattr(cloud, "execute", lambda request: calls.append("execute"))
    monkeypatch.setattr(agent_gateway.AdapterRegistry, "get", lambda _name: cloud)

    result = agent_gateway.AgentGateway().dispatch(
        agent_gateway.AgentRequest(intent="task_create", source={"adapter": "cloud"}),
    )

    assert result.success is False
    assert "no puede ejecutar intents mutables" in result.error
    assert calls == []


def test_agent_gateway_cli_does_not_offer_remote_command_adapters():
    with pytest.raises(SystemExit) as exc:
        agent_gateway.main(["dispatch", "status", "--adapter", "cloud"])

    assert exc.value.code == 2


def test_intent_registry_matches_contract_and_every_prefix_parses():
    import json
    from bago_core.parsers import build_parser

    contract_path = AGENTS_DIR / "agent_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    schema_intents = set(contract["definitions"]["AgentRequest"]["properties"]["intent"]["enum"])
    assert schema_intents == set(agent_gateway.ALL_ALLOWED_INTENTS)
    schema_adapters = set(contract["definitions"]["AgentRequest"]["properties"]["source"]["properties"]["adapter"]["enum"])
    assert schema_adapters == set(agent_gateway.AdapterRegistry.all())

    parser = build_parser("test", str(Path(__file__).resolve().parents[1]), "local", "model")
    abbreviated_override = parser.parse_args(["project", "init", "--roo=C:/outside"])
    assert abbreviated_override.root == "C:/outside"
    with pytest.raises(ValueError, match="cannot override"):
        agent_gateway.LocalAdapter.command_argv(agent_gateway.AgentRequest(
            intent="project_init", payload={"args": ["--roo=C:/outside"]},
        ))
    suffixes = {
        "task_create": ["example task"],
        "task_done": ["brief-id"],
        "task_handoff": ["brief-id", "--from", "agent-a", "--to", "agent-b"],
    }
    for intent, (prefix, _risk) in agent_gateway._INTENT_TO_CMD.items():
        parser.parse_args([*prefix, *suffixes.get(intent, [])])
