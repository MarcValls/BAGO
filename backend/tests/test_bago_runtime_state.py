from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".bago" / "bin" / "bago.py"
SPEC = importlib.util.spec_from_file_location("bago_runtime_state", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_state_change_preserves_and_invalidates_previous_verification(monkeypatch):
    old_commit = "a" * 40
    new_commit = "b" * 40
    state = {
        "status": "EXECUTED",
        "fingerprint": {"commit": old_commit},
        "last_verification": {"commit": old_commit, "command": "old check"},
    }
    saved: list[dict] = []
    monkeypatch.setattr(MODULE, "_load_state", lambda: state)
    monkeypatch.setattr(MODULE, "_save_state", lambda value: saved.append(value.copy()))
    monkeypatch.setattr(MODULE, "_git_fingerprint", lambda: {"commit": new_commit, "branch": "main"})

    assert MODULE.cmd_state(argparse.Namespace(status="EXECUTED", note="new candidate")) == 0
    assert "last_verification" not in state
    assert state["history"]["continuity"]["last_verification"]["commit"] == old_commit
    assert state["history"]["continuity"]["superseded_by"] == new_commit
    assert saved and saved[0]["commit"] == new_commit
