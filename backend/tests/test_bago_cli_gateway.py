from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / ".bago" / "bin" / "bago.py"


def _module():
    spec = importlib.util.spec_from_file_location("bago_cli_gateway_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_handoff_and_state_writes_use_the_shared_gateway(tmp_path, monkeypatch):
    module = _module()
    bago_root = tmp_path / ".bago"
    monkeypatch.setattr(module, "BAGO_ROOT", bago_root)
    monkeypatch.setattr(module, "PROJECT_STATE_FILE", bago_root / "state" / "PROJECT_STATE.json")
    monkeypatch.setattr(module, "ACTIVE_HANDOFF", bago_root / "runtime" / "ACTIVE_HANDOFF.md")

    module._save_project_state({"lifecycle": "EXECUTED"})
    module._write_handoff("gateway-owned handoff")

    state = json.loads(module.PROJECT_STATE_FILE.read_text(encoding="utf-8"))
    handoff = module.ACTIVE_HANDOFF.read_text(encoding="utf-8")
    assert state["lifecycle"] == "EXECUTED"
    assert "gateway-owned handoff" in handoff


def test_git_head_uses_the_read_only_process_inspection_gateway(monkeypatch):
    module = _module()
    calls = []

    def inspect(executable, argv, *, cwd, manager, timeout):
        calls.append((executable, argv, Path(cwd), manager.base_path, timeout))
        return {"exit_code": 0, "stdout": "0123456789abcdef\n"}

    monkeypatch.setattr("bago_core.server_effects.inspect_process", inspect)

    assert module._git_sha() == "0123456789ab"
    assert calls[0][0:2] == ("git", ["rev-parse", "HEAD"])
    assert calls[0][2] == Path(calls[0][3])


def test_verify_builds_a_permit_bound_pytest_process_request(monkeypatch, tmp_path):
    module = _module()
    captured = {}

    def execute(request, *, confirmation_text, manager):
        captured.update(request=request, confirmation_text=confirmation_text, manager=manager)
        return {"exit_code": 0, "stdout": "tests passed\n", "stderr": ""}

    monkeypatch.setattr("bago_core.cli_execution.execute_cli_effect", execute)

    result = module._execute_verify_command(["pytest", "-q", "tests"], tmp_path)

    request = captured["request"]
    assert request.effect_id == "process.execute"
    assert request.source_surface == "cli.bago.verify"
    assert request.target["cwd"] == str(tmp_path)
    assert request.target["executable"] == sys.executable
    assert request.arguments["argv"] == ["-m", "pytest", "-q", "tests"]
    assert captured["manager"].base_path == str(tmp_path)
    assert "pytest" in captured["confirmation_text"]
    assert result.returncode == 0 and result.stdout == "tests passed\n"


def test_verify_rejects_arbitrary_python_code_before_gateway(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(
        "bago_core.cli_execution.execute_cli_effect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must be rejected pre-effect")),
    )

    try:
        module._execute_verify_command(["python", "-c", "print('no')"], tmp_path)
    except ValueError as exc:
        assert "only pytest" in str(exc)
    else:
        raise AssertionError("arbitrary Python code must be rejected")
