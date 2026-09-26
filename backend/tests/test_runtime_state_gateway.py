from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from execution_adapter_contract import ExecutionGatewayError
from bago_core.server_effects import ensure_runtime_state_dirs


BACKEND = Path(__file__).resolve().parents[1]
RUNTIME_PATH = BACKEND / ".bago" / "core" / "runtime.py"
_SPEC = importlib.util.spec_from_file_location("bago_runtime_state_gateway_test", RUNTIME_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_RUNTIME = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RUNTIME)


def test_ensure_state_dir_materializes_only_canonical_subdirectories(tmp_path, monkeypatch):
    root = tmp_path / ".bago" / "state"
    monkeypatch.setenv("BAGO_ROOT", str(tmp_path))
    monkeypatch.setenv("BAGO_STATE_DIR", str(root))

    assert _RUNTIME.ensure_state_dir() == root.resolve()
    assert all((root / name).is_dir() for name in ("sessions", "changes", "evidences"))


def test_runtime_state_example_seed_uses_owner_and_never_overwrites(tmp_path, monkeypatch):
    from pathlib import Path

    app_root = tmp_path / "app"
    example_root = app_root / ".bago" / "state.example"
    example_root.mkdir(parents=True)
    template = {"schema": 1, "initialized": True}
    (example_root / "global_state.json").write_text(json.dumps(template), encoding="utf-8")
    (example_root / "sessions").mkdir()
    (example_root / "sessions" / "default.json").write_text('{"session": "default"}', encoding="utf-8")
    state_root = app_root / ".bago" / "state"
    monkeypatch.setenv("BAGO_ROOT", str(app_root))
    monkeypatch.setenv("BAGO_STATE_DIR", str(state_root))

    assert _RUNTIME.init_state_from_example() is True
    assert json.loads((state_root / "global_state.json").read_text(encoding="utf-8")) == template
    assert (state_root / "sessions" / "default.json").read_text(encoding="utf-8") == '{"session": "default"}'

    replacement = '{"schema": 1, "user": "preserve"}'
    (state_root / "global_state.json").write_text(replacement, encoding="utf-8")
    assert _RUNTIME.init_state_from_example() is False
    assert (state_root / "global_state.json").read_text(encoding="utf-8") == replacement


def test_runtime_state_owner_rejects_noncanonical_root_before_creation(tmp_path, monkeypatch):
    canonical_root = tmp_path / "canonical" / ".bago" / "state"
    outside_root = tmp_path / "outside" / ".bago" / "state"
    monkeypatch.setenv("BAGO_ROOT", str(tmp_path / "canonical"))
    monkeypatch.setenv("BAGO_STATE_DIR", str(canonical_root))

    with pytest.raises(ExecutionGatewayError) as blocked:
        ensure_runtime_state_dirs(outside_root)

    assert blocked.value.code == "runtime_state_root_invalid"
    assert not outside_root.exists()
