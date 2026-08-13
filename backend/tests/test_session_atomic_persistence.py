from __future__ import annotations

import json


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


def test_session_manager_save_uses_complete_json_replacement(tmp_path) -> None:
    from session_manager import SessionManager

    state_root = tmp_path / "state"
    manager = SessionManager(base_path=str(tmp_path), state_root=str(state_root))
    try:
        manager.save()
        manager.total_calls += 1
        manager.save()
        session_file = state_root / "sessions" / f"{manager.session_id}.json"
        payload = json.loads(session_file.read_text(encoding="utf-8"))
        assert payload["session_id"] == manager.session_id
        assert payload["total_calls"] == 1
        assert list(session_file.parent.glob("*.tmp")) == []
    finally:
        manager.close()
