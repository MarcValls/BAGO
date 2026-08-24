from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".bago" / "bin" / "bago.py"


def _module():
    spec = importlib.util.spec_from_file_location("bago_runtime_status", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_status(monkeypatch, capsys, state: dict, fingerprint: dict) -> str:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: state)
    monkeypatch.setattr(module, "_git_fingerprint", lambda: fingerprint)
    monkeypatch.setattr(module, "_print_file", lambda *_args: None)
    assert module.cmd_status(None) == 0
    return capsys.readouterr().out


def test_verified_without_candidate_fingerprint_is_stale(monkeypatch, capsys) -> None:
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "note": "historical claim"},
        {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"},
    )
    assert "Status:     STALE" in output
    assert "missing candidate fingerprint" in output
    assert "Recorded note:" in output


def test_verified_with_different_candidate_is_stale(monkeypatch, capsys) -> None:
    current = {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "fingerprint": {**current, "commit": "old"}},
        current,
    )
    assert "Status:     STALE" in output
    assert "candidate drift" in output


def test_verified_with_exact_clean_candidate_remains_unverified_without_independent_receipt(monkeypatch, capsys) -> None:
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "fingerprint": current},
        current,
    )
    assert "Status:     UNVERIFIED" in output
    assert "protected state requires independent receipt verification" in output
    assert "Recorded:   VERIFIED" in output


def test_non_verified_state_does_not_require_fingerprint(monkeypatch, capsys) -> None:
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "EXECUTED"},
        {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"},
    )
    assert "Status:     EXECUTED" in output


@pytest.mark.parametrize("protected", ["VERIFIED", "VALIDATED"])
def test_manual_state_rejects_protected_evidence_states(monkeypatch, capsys, protected: str) -> None:
    module = _module()
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("protected state was persisted"))
    assert module.cmd_state(SimpleNamespace(status=protected, note="self certified")) == 2
    assert "protected evidence state" in capsys.readouterr().err


def test_manual_executed_state_is_bound_to_current_fingerprint(monkeypatch) -> None:
    module = _module()
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    saved: dict = {}
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "PREPARED"})
    monkeypatch.setattr(module, "_git_fingerprint", lambda: current)
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    assert module.cmd_state(SimpleNamespace(status="executed", note="material action")) == 0
    assert saved["status"] == "EXECUTED"
    assert saved["fingerprint"] == current


def test_manual_state_rejects_unknown_label(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "PROPOSED"})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("unknown state was persisted"))
    assert module.cmd_state(SimpleNamespace(status="BANANA", note="")) == 2
    assert "unknown or non-manual" in capsys.readouterr().err


def test_manual_state_rejects_forward_jump(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "PROPOSED"})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("jump was persisted"))
    assert module.cmd_state(SimpleNamespace(status="EXECUTED", note="")) == 2
    assert "lifecycle jump" in capsys.readouterr().err


def test_manual_lifecycle_must_start_at_proposed(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "idle"})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("invalid start was persisted"))
    assert module.cmd_state(SimpleNamespace(status="PREPARED", note="")) == 2
    assert "must start at PROPOSED" in capsys.readouterr().err


@pytest.mark.parametrize("protected", ["VERIFIED", "VALIDATED"])
def test_verify_cannot_revalidate_protected_historical_state(monkeypatch, protected: str) -> None:
    module = _module()
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    saved: dict = {}
    monkeypatch.setattr(module, "_load_state", lambda: {"status": protected, "note": "historical"})
    monkeypatch.setattr(module, "_git_fingerprint", lambda: current)
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="ok\n", stderr=""),
    )

    assert module.cmd_verify(SimpleNamespace(command=["python", "-c", "pass"])) == 0
    assert saved["status"] == "EXECUTED"
    assert saved["fingerprint"] == current
    assert "independent review" in saved["note"]
