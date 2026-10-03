from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import execution_gateway as gateway_module
from execution_gateway import ExecutionGateway, ExecutionGatewayError, ExecutionContext
from tool_registry import ToolCall, ToolRegistry


@pytest.fixture(autouse=True)
def _refresh_bago_modules():
    global auth, gateway_module, ExecutionGateway, ExecutionGatewayError
    global ExecutionContext, SessionToolsMixin, ToolCall, ToolRegistry, process_adapter

    auth = importlib.import_module("authorization_boundary")
    gateway_module = importlib.import_module("execution_gateway")
    ExecutionGateway = gateway_module.ExecutionGateway
    ExecutionGatewayError = gateway_module.ExecutionGatewayError
    ExecutionContext = importlib.import_module("execution_adapter_contract").ExecutionContext
    SessionToolsMixin = importlib.import_module("session_tools_mixin").SessionToolsMixin
    tool_registry = importlib.import_module("tool_registry")
    ToolCall = tool_registry.ToolCall
    ToolRegistry = tool_registry.ToolRegistry
    process_adapter = importlib.import_module("execution_adapters.process")


class _RuntimeManager:
    def __init__(self, root: Path) -> None:
        self.session_id = "runtime-control-test"
        self.framework_root = str(root)
        self.base_path = str(root)
        self.project_root = str(root)
        self.context_revision = "revision-a"
        self.runtime = "test"
        self.config = SimpleNamespace(
            get=lambda key, default=None: "always"
            if key == "features.tool_approval_policy"
            else default
        )

    def execute_runtime_control(self, arguments=None):
        return SessionToolsMixin.execute_runtime_control(self, arguments)

    def workspace_state(self) -> dict[str, str]:
        return {"project_root": self.project_root, "context_revision": self.context_revision}


def test_runtime_control_uses_gateway_and_returns_receipt(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("webbrowser.open", lambda _url: True)
    approvals = []
    original_approve_cli_native = auth.AuthorizationBoundary.approve_cli_native_challenge

    def observe_native_approval(boundary, **kwargs):
        assert "terminal_confirmed" not in kwargs
        approvals.append((boundary, kwargs))
        return original_approve_cli_native(boundary, **kwargs)

    monkeypatch.setattr(
        auth.AuthorizationBoundary, "approve_cli_native_challenge", observe_native_approval,
    )

    def confirm_once(challenge):
        assert challenge["effect_id"] == "process.execute"
        assert challenge["target"]["operation"] == "launch_manager_server"
        assert challenge["operation_fingerprint"]
        boundary, kwargs = approvals[-1]
        with pytest.raises(auth.AuthorizationError) as replay:
            original_approve_cli_native(boundary, **kwargs)
        assert replay.value.code == "authorization_challenge_not_pending"
        return True

    prompts = []
    def capture_prompt(challenge):
        prompts.append(challenge)
        return confirm_once(challenge)

    monkeypatch.setattr(auth, "confirm_strong_challenge", capture_prompt)
    monkeypatch.setattr(
        process_adapter.ProcessExecutionEffectAdapter,
        "_launch_manager_server",
        staticmethod(lambda _request: {
            "executed": True,
            "process_id": 98765,
            "receipt_id": "process-execute:approved",
        }),
    )
    result = json.loads(_RuntimeManager(root).execute_runtime_control({"action": "start_and_open"}))

    assert len(prompts) == 1
    assert prompts[0]["effect_id"] == "process.execute"
    assert prompts[0]["target"]["operation"] == "launch_manager_server"
    assert prompts[0]["operation_fingerprint"]
    assert result["gateway_owned"] is True
    assert result["effect_id"] == "process.execute"
    assert result["receipt_id"] == "process-execute:approved"
    assert result["browser_opened"] is True
    assert result["process_id"] == 98765
    with pytest.raises(auth.AuthorizationError) as replay:
        original_approve_cli_native(approvals[0][0], **approvals[0][1])
    assert replay.value.code == "authorization_challenge_not_pending"


def test_runtime_control_tty_and_autoapproval_do_not_replace_native_decision(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    prompts = []
    launches = []
    monkeypatch.setattr(
        auth,
        "confirm_strong_challenge",
        lambda challenge: prompts.append(challenge) or False,
    )
    monkeypatch.setattr(
        process_adapter.ProcessExecutionEffectAdapter,
        "_launch_manager_server",
        staticmethod(lambda request: launches.append(request) or {"executed": True}),
    )
    registry = ToolRegistry(workspace_root=root)
    registry.manager = _RuntimeManager(root)

    result = registry.execute_model_call(
        ToolCall("runtime-auto", "runtime-control", {"action": "start"})
    )

    assert result.ok is False
    assert result.blocked is True
    assert len(prompts) == 1
    assert prompts[0]["operation_fingerprint"]
    assert launches == []


def test_runtime_control_rejects_non_tty_without_native_or_process_dispatch(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        auth.AuthorizationBoundary,
        "approve_cli_challenge",
        lambda *_args, **_kwargs: pytest.fail("runtime-control must use native approval API"),
    )
    monkeypatch.setattr(
        auth,
        "confirm_strong_challenge",
        lambda _challenge: pytest.fail("non-TTY must not prompt or approve"),
    )
    launches = []
    monkeypatch.setattr(
        process_adapter.ProcessExecutionEffectAdapter,
        "_launch_manager_server",
        staticmethod(lambda request: launches.append(request) or {"executed": True}),
    )
    registry = ToolRegistry(workspace_root=root)
    registry.manager = _RuntimeManager(root)

    result = registry.execute_model_call(
        ToolCall("runtime-nontty", "runtime-control", {"action": "start"})
    )

    assert result.ok is False
    assert result.blocked is True
    assert launches == []


def test_runtime_control_tool_blocks_when_gateway_execution_fails(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    registry = ToolRegistry(workspace_root=root)
    registry.manager = _RuntimeManager(root)
    registry.manager.framework_root = str(tmp_path / "missing-runtime-root")
    result = registry.execute_model_call(ToolCall("runtime-failure", "runtime-control", {"action": "start"}))

    assert result.ok is False
    assert result.blocked is True
    assert result.block_reason == "runtime_control_gateway_rejected"
    assert "WinError 2" in result.content or "No existe" in result.content


def test_runtime_control_permit_cannot_be_reused_for_a_different_target(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = root / "bago_core" / "launcher.py"
    ui = root / "ui-react" / "dist"
    manager = _RuntimeManager(root)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    digest = hashlib.sha256(launcher.read_bytes()).hexdigest()

    def make_request(port: int):
        from execution_request import build_execution_request
        target = {"operation": "launch_manager_server", "cwd": str(root), "python_root": str(root),
                  "python_module_sha256": digest, "host": "127.0.0.1", "port": port, "ui_dist": str(ui)}
        return build_execution_request(
            effect_id="process.execute", actor_kind="user", principal_id="interactive-local-user",
            session_id=manager.session_id, source_surface="cli.manager.launch", target=target,
            arguments={"argv": ["--base-path", str(root), "serve", "--host", "127.0.0.1", "--port", str(port), "--ui-dist", str(ui)]},
            scope="workspace", world_state_authority=manager,
        )

    boundary = auth.AuthorizationBoundary()
    authorized = make_request(8765)
    alternate = make_request(8766)
    challenge = boundary.create_challenge(authorized, interaction_id="target-binding")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="target-binding",
        session_id=manager.session_id, channel="ui-react",
    )["permit"]["token"]
    with pytest.raises(Exception) as error:
        ExecutionGateway(boundary).execute(permit_token=permit, request=alternate, context=ExecutionContext(manager=manager))

    assert error.value.code in {"authorization_world_state_stale", "execution_world_state_stale", "authorization_permit_operation_mismatch"}


def test_runtime_control_permit_is_invalid_after_world_state_changes(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = root / "bago_core" / "launcher.py"
    ui = root / "ui-react" / "dist"
    manager = _RuntimeManager(root)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    digest = hashlib.sha256(launcher.read_bytes()).hexdigest()
    from execution_request import build_execution_request

    request = build_execution_request(
        effect_id="process.execute", actor_kind="user", principal_id="interactive-local-user",
        session_id=manager.session_id, source_surface="cli.manager.launch",
        target={"operation": "launch_manager_server", "cwd": str(root), "python_root": str(root),
                "python_module_sha256": digest, "host": "127.0.0.1", "port": 8765, "ui_dist": str(ui)},
        arguments={"argv": ["--base-path", str(root), "serve", "--host", "127.0.0.1", "--port", "8765", "--ui-dist", str(ui)]},
        scope="workspace", world_state_authority=manager,
    )
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="state-binding")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="state-binding",
        session_id=manager.session_id, channel="ui-react",
    )["permit"]["token"]
    manager.context_revision = "revision-b"

    with pytest.raises(ExecutionGatewayError) as error:
        ExecutionGateway(boundary).execute(
            permit_token=permit, request=request, context=ExecutionContext(manager=manager),
        )

    assert error.value.code == "execution_world_state_stale"
