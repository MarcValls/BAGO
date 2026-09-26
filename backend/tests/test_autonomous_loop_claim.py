from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / ".bago" / "core"
BACKEND = CORE.parents[1]
sys.path[:0] = [str(CORE), str(BACKEND)]
_SPEC = importlib.util.spec_from_file_location("autonomous_loop_claim_test", CORE / "autonomous_loop.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)


def test_autonomous_loop_uses_shared_execution_claim_not_lock_file(monkeypatch, tmp_path: Path) -> None:
    paths = __import__("bago_core.user_state_paths", fromlist=["state_root"])
    monkeypatch.setattr(paths, "state_root", lambda: tmp_path / "canonical-state")
    first = _MODULE._LoopLock()
    second = _MODULE._LoopLock()

    assert first.acquire()
    assert first.renew()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()
    assert (tmp_path / "canonical-state" / "execution_claims.sqlite3").is_file()
    assert not (CORE / "state" / "autonomous.lock").exists()


def test_autonomous_loop_no_longer_has_direct_lock_file_materializers() -> None:
    import sys as _sys
    sys.path.insert(0, str(CORE.parent / "tools"))
    import effect_sink_inventory as inventory

    findings = inventory.scan_python(CORE / "autonomous_loop.py")
    source = (CORE / "autonomous_loop.py").read_text(encoding="utf-8")
    assert "_LOCK_FILE" not in source
    assert "_acquire_unix" not in source and "_acquire_windows" not in source
    assert not any(item.effect_id in {"filesystem.write", "filesystem.delete"} for item in findings)


def test_autonomous_inbox_and_state_write_use_bounded_server_state_effect(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(_MODULE, "_STATE_DIR", state)
    monkeypatch.setattr(_MODULE, "_INBOX_FILE", state / "inbox.json")
    monkeypatch.setattr(_MODULE, "_ASTATE_FILE", state / "autonomous_state.json")

    _MODULE._atomic_write(_MODULE._INBOX_FILE, {"tasks": [{"id": "INB-test", "status": "pending"}]})
    assert json.loads((_MODULE._INBOX_FILE).read_text(encoding="utf-8")) == {
        "tasks": [{"id": "INB-test", "status": "pending"}]
    }

    try:
        _MODULE._atomic_write(state / "other.json", {"unexpected": True})
    except ValueError as exc:
        assert "two approved resources" in str(exc)
    else:
        raise AssertionError("Autonomous state helper accepted a third persistence target")
