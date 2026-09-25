from __future__ import annotations

import ast
import os
from pathlib import Path

import effect_sink_inventory as inventory
import pytest
from bago_core import instance_lock
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_adapters.process import ProcessExecutionEffectAdapter
from execution_request import build_execution_request


def test_bago_instance_lock_rejects_a_live_pid_and_releases(tmp_path, monkeypatch):
    lock_path = tmp_path / "bago.lock"
    monkeypatch.setattr(instance_lock, "ensure_user_roots", lambda: None)
    monkeypatch.setattr(instance_lock, "bago_lock_file", lambda: lock_path)

    acquired, claimed_path, existing_pid = instance_lock.acquire_bago_lock()
    assert acquired is True
    assert claimed_path == lock_path
    assert existing_pid is None
    assert lock_path.read_text(encoding="utf-8").splitlines()[0] == str(os.getpid())

    acquired_again, _, existing_pid = instance_lock.acquire_bago_lock()
    assert acquired_again is False
    assert existing_pid == os.getpid()

    instance_lock.release_bago_lock(lock_path)
    assert not lock_path.exists()


def test_bago_instance_lock_reclaims_a_dead_pid(tmp_path, monkeypatch):
    lock_path = tmp_path / "bago.lock"
    lock_path.write_text("999999999\n0\n", encoding="utf-8")
    monkeypatch.setattr(instance_lock, "ensure_user_roots", lambda: None)
    monkeypatch.setattr(instance_lock, "bago_lock_file", lambda: lock_path)
    monkeypatch.setattr(instance_lock, "is_pid_alive", lambda _pid: False)

    acquired, _, existing_pid = instance_lock.acquire_bago_lock()

    assert acquired is True
    assert existing_pid is None
    assert lock_path.read_text(encoding="utf-8").splitlines()[0] == str(os.getpid())


def test_instance_lock_is_server_internal_and_acquired_only_by_cli_serve():
    lock_path = inventory.REPO_ROOT / "backend" / "bago_core" / "instance_lock.py"
    command_path = inventory.REPO_ROOT / "backend" / "bago_core" / "commands" / "cmd_content.py"
    findings = inventory.scan_python(lock_path)
    assert findings
    assert all(item.binding_class == "authority_internal" for item in findings)
    assert inventory.scan_python(command_path) == []

    callers = []
    for path in inventory._iter_files([inventory.REPO_ROOT / "backend"]):
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"acquire_bago_lock", "release_bago_lock"}
            ):
                callers.append(path.resolve())

    assert callers
    assert set(callers) == {command_path.resolve()}


def test_manager_server_spawn_requires_exact_consumed_gateway_permit(tmp_path, monkeypatch):
    import hashlib

    runtime_root = Path(__file__).resolve().parents[1]
    module_file = runtime_root / "bago_core" / "launcher.py"
    ui_dist = tmp_path / "ui-dist"
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text("ok", encoding="utf-8")
    argv = ["--base-path", str(tmp_path), "serve", "--host", "127.0.0.1", "--port", "8765", "--ui-dist", str(ui_dist)]
    request = build_execution_request(
        effect_id="process.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="cli-manager-test",
        source_surface="cli.manager.launch",
        target={
            "operation": "launch_manager_server",
            "cwd": str(tmp_path),
            "python_root": str(runtime_root),
            "python_module_sha256": hashlib.sha256(module_file.read_bytes()).hexdigest(),
            "host": "127.0.0.1",
            "port": 8765,
            "ui_dist": str(ui_dist),
        },
        arguments={"argv": argv},
        scope="workspace",
    )
    authorization = {
        "state": "consumed",
        "effect_id": request.effect_id,
        "operation_fingerprint": request.fingerprint,
        "session_id": request.session_id,
    }
    spawned = []

    class _Process:
        pid = 2468

    monkeypatch.setattr(ProcessExecutionEffectAdapter.__module__ + ".subprocess.Popen", lambda *a, **kw: (spawned.append((a, kw)) or _Process()))
    result = ProcessExecutionEffectAdapter().execute(
        request, ExecutionContext(services={"_authorization": authorization})
    )
    assert result["process_id"] == 2468
    assert result["executed"] is True
    assert len(spawned) == 1

    bad_target = dict(request.target, host="0.0.0.0")
    bad_request = build_execution_request(
        effect_id=request.effect_id,
        actor_kind=request.actor_kind,
        principal_id=request.principal_id,
        session_id=request.session_id,
        source_surface=request.source_surface,
        target=bad_target,
        arguments=request.arguments,
        scope=request.scope,
    )
    bad_authorization = dict(authorization, operation_fingerprint=bad_request.fingerprint)
    with pytest.raises(ExecutionGatewayError, match="loopback policy"):
        ProcessExecutionEffectAdapter().execute(
            bad_request, ExecutionContext(services={"_authorization": bad_authorization})
        )
    assert len(spawned) == 1
