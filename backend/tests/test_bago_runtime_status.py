from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_verified_with_exact_clean_candidate_remains_verified(monkeypatch, capsys) -> None:
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "fingerprint": current},
        current,
    )
    assert "Status:     VERIFIED" in output
    assert "Recorded:" not in output


def test_non_verified_state_does_not_require_fingerprint(monkeypatch, capsys) -> None:
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "EXECUTED"},
        {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"},
    )
    assert "Status:     EXECUTED" in output
