from __future__ import annotations

import json
import builtins


def test_context_store_rewrites_remain_valid_and_leave_no_temp_files(tmp_path) -> None:
    from context_store import ContextStore

    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("primero")
    store.append_response("segundo")
    assert store.mark_good()
    store.record_tokens("local", "test", 2, 3)
    store.compress_history(target_messages=1)

    session_dir = tmp_path / "sessions" / store.sid
    for name in ("meta.json", "tokens.json"):
        assert isinstance(json.loads((session_dir / name).read_text(encoding="utf-8")), dict)
    for name in ("context.jsonl", "timeline.jsonl"):
        for line in (session_dir / name).read_text(encoding="utf-8").splitlines():
            assert isinstance(json.loads(line), dict)
    assert list(session_dir.glob("*.tmp")) == []


def test_session_manager_save_uses_only_canonical_json_replacement(tmp_path, monkeypatch) -> None:
    from session_manager import SessionManager

    state_root = tmp_path / "state"
    manager = SessionManager(base_path=str(tmp_path), state_root=str(state_root))
    original_import = builtins.__import__
    session_db_imports = []

    def reject_session_db_import(name, *args, **kwargs):
        if name == "session_db":
            session_db_imports.append(name)
            raise AssertionError("SessionDB is retired; session JSON is canonical")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_session_db_import)
    try:
        first_save = manager.save()
        assert first_save["session_json_persisted"] is True
        assert first_save["session_json_receipt"]
        assert "session_db_indexed" not in first_save
        manager.total_calls += 1
        manager.save()
        session_file = state_root / "sessions" / f"{manager.session_id}.json"
        payload = json.loads(session_file.read_text(encoding="utf-8"))
        assert payload["session_id"] == manager.session_id
        assert payload["total_calls"] == 1
        assert list(session_file.parent.glob("*.tmp")) == []
        assert session_db_imports == []
    finally:
        manager.close()
