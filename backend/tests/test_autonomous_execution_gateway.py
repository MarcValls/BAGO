from __future__ import annotations

import builtins
import importlib
import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace

CORE = Path(__file__).resolve().parents[1] / ".bago" / "core"
BACKEND = CORE.parents[1]
sys.path[:0] = [str(CORE), str(BACKEND)]
SPEC = importlib.util.spec_from_file_location("autonomous_gateway_test", CORE / "autonomous_loop.py")
LOOP = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(LOOP)


def _request(tool: str, effect_id: str):
    from execution_request import build_execution_request

    identity = "a" * 64
    return build_execution_request(
        effect_id=effect_id,
        actor_kind="system" if effect_id == "autonomous.observe" else "user",
        principal_id=f"bago-autonomous:{identity}" if effect_id == "autonomous.observe" else "interactive-local-user",
        session_id=f"autonomous-loop:{identity}",
        source_surface="server.autonomous_loop.tool" if effect_id == "autonomous.observe" else "cli.autonomous_loop.tool",
        target={
            "tool": tool, "timeout_seconds": 30.0,
            "backend_root": str(BACKEND.resolve()), "python_executable": sys.executable,
        },
        arguments={"extra_args": []}, scope="session" if effect_id == "autonomous.observe" else "workspace",
    )


def test_read_only_autonomous_tool_uses_server_policy_owner(monkeypatch) -> None:
    from execution_adapter_contract import ExecutionContext
    from execution_gateway import ExecutionGateway

    adapter_module = importlib.import_module("execution_adapters.autonomous")
    calls = []
    monkeypatch.setattr(adapter_module.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(returncode=0, stdout="health ok", stderr=""))
    request = _request("health", "autonomous.observe")
    result, authorization = ExecutionGateway().execute_server_owned(request=request, context=ExecutionContext())

    assert authorization["kind"] == "server_policy"
    assert result["returncode"] == 0
    assert calls[0][0][0][-1] == "health"
    assert calls[0][1]["shell"] is False


def test_mutating_tool_requires_cli_challenge_approval_and_consumed_permit(monkeypatch, tmp_path: Path) -> None:
    auth = importlib.import_module("authorization_boundary")
    adapter_module = importlib.import_module("execution_adapters.autonomous")
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr(builtins, "input", lambda _prompt: "s")
    calls = []
    monkeypatch.setattr(adapter_module.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(returncode=0, stdout="repair complete", stderr=""))

    code, output = LOOP._run_tool("heal", timeout=30, unsafe=True)
    assert code == 0
    assert output == "repair complete"
    assert len(calls) == 1
    assert calls[0][0][0][-1] == "heal"


def test_mutating_tool_is_denied_without_unsafe_or_tty(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    code, output = LOOP._run_tool("heal", unsafe=True)
    assert code == -1
    assert "interactive terminal approval" in output

    code, output = LOOP._run_tool("heal", unsafe=False)
    assert code == -1
    assert "requires --unsafe" in output


def test_cli_channel_cannot_be_claimed_through_interactive_http_approval() -> None:
    from authorization_boundary import AuthorizationBoundary, AuthorizationError

    try:
        AuthorizationBoundary().approve_challenge(
            challenge_id="unused", interaction_id="unused", session_id="unused", channel="cli",
        )
    except AuthorizationError as exc:
        assert exc.code == "authorization_user_origin_unverified"
    else:
        raise AssertionError("HTTP-style approval accepted a CLI channel claim")
