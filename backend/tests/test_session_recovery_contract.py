from __future__ import annotations

import json
from types import SimpleNamespace

from session_registry import active_session_id, archive_session, list_session_summaries, mark_active_session, rename_session, restore_active_session, restore_session, session_archived


class FakeStore:
    def __init__(self, root, session_id):
        self.root = root
        self.session_id = session_id
        self.meta = {}

    def update_meta(self, patch):
        self.meta.update(patch)
        path = self.root / "sessions" / self.session_id / "meta.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.meta), encoding="utf-8")


class FakeManager:
    loaded = {}

    def __init__(self, *, session_id="new-session", state_root, base_path=".", provider="mock", model="model", **kwargs):
        self.session_id = session_id
        self.state_root = state_root
        self.base_path = base_path
        self.project_root = base_path
        self.provider = provider
        self.model = model
        self.system_prompt = ""
        self.bago_mode = "B"
        self.active_bridges = [provider]
        self.agent_gateway = SimpleNamespace(active=SimpleNamespace(name="default"))
        self.adapters = {"mock": object}
        self.store = FakeStore(state_root, session_id)
        self.saved = 0

    def save(self):
        self.saved += 1

    @classmethod
    def load(cls, session_id, **kwargs):
        return cls.loaded[session_id]


def _write_session(root, session_id, messages=None, **meta):
    session = root / "sessions" / session_id
    session.mkdir(parents=True)
    (session / "meta.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:00+00:00", **meta}), encoding="utf-8")
    if messages:
        (session / "context.jsonl").write_text("\n".join(json.dumps(item) for item in messages) + "\n", encoding="utf-8")


def test_session_index_hides_empty_inactive_sessions(tmp_path):
    _write_session(tmp_path, "active-empty")
    _write_session(tmp_path, "old-empty")
    _write_session(tmp_path, "useful", messages=[{"role": "user", "content": "Recuperar este trabajo", "timestamp": "2026-02-01T00:00:00+00:00"}])

    sessions = list_session_summaries(tmp_path, current_session_id="active-empty")

    assert [item["session_id"] for item in sessions] == ["active-empty", "useful"]
    assert sessions[1]["title"] == "Recuperar este trabajo"


def test_active_session_pointer_is_persistent(tmp_path):
    manager = FakeManager(session_id="recover-me", state_root=tmp_path)

    mark_active_session(manager)

    assert active_session_id(tmp_path) == "recover-me"
    assert manager.store.meta["last_opened_at"]


def test_backend_restart_restores_the_active_session(tmp_path):
    manager = FakeManager(session_id="resume-after-restart", state_root=tmp_path)
    FakeManager.loaded = {manager.session_id: manager}
    mark_active_session(manager)

    restored = restore_active_session(FakeManager, tmp_path, base_path="workspace")

    assert restored is manager


def test_session_can_be_renamed_and_archived_without_deleting_history(tmp_path):
    _write_session(tmp_path, "lifecycle", messages=[{"role": "user", "content": "contenido"}])

    rename_session(tmp_path, "lifecycle", "Plan de lanzamiento")
    assert list_session_summaries(tmp_path, current_session_id="lifecycle")[0]["title"] == "Plan de lanzamiento"

    archive_session(tmp_path, "lifecycle")
    assert list_session_summaries(tmp_path, current_session_id="") == []
    archived = list_session_summaries(tmp_path, current_session_id="", archived_only=True)
    assert archived[0]["session_id"] == "lifecycle"
    assert archived[0]["archived"] is True
    assert (tmp_path / "sessions" / "lifecycle" / "context.jsonl").exists()

    restore_session(tmp_path, "lifecycle")
    assert session_archived(tmp_path, "lifecycle") is False
    assert list_session_summaries(tmp_path, current_session_id="lifecycle")[0]["title"] == "Plan de lanzamiento"


def test_session_handler_switches_shared_backend_authority(tmp_path, monkeypatch):
    import api_serializers
    import handlers_sessions

    current = FakeManager(session_id="current", state_root=tmp_path)
    target = FakeManager(session_id="target", state_root=tmp_path)
    FakeManager.loaded = {"target": target}
    _write_session(tmp_path, "current", messages=[{"role": "user", "content": "actual"}])
    _write_session(tmp_path, "target", messages=[{"role": "user", "content": "anterior"}])

    class Handler:
        session_mgr = current
        switch_engine = SimpleNamespace(adapters={})

    handler = Handler()
    responses = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))

    handlers_sessions.handle_post(handler, {"action": "switch", "session_id": "target"})

    assert responses[-1][0] == 200
    assert Handler.session_mgr is target
    assert handler.session_mgr is target
    assert active_session_id(tmp_path) == "target"
    assert responses[-1][1]["active_session_id"] == "target"


def test_archiving_active_session_activates_a_previous_session(tmp_path, monkeypatch):
    import api_serializers
    import handlers_sessions

    current = FakeManager(session_id="current", state_root=tmp_path)
    target = FakeManager(session_id="target", state_root=tmp_path)
    FakeManager.loaded = {"target": target}
    _write_session(tmp_path, "current", messages=[{"role": "user", "content": "actual"}])
    _write_session(tmp_path, "target", messages=[{"role": "user", "content": "anterior"}])

    class Handler:
        session_mgr = current
        switch_engine = SimpleNamespace(adapters={})

    handler = Handler()
    responses = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))

    handlers_sessions.handle_post(handler, {"action": "archive", "session_id": "current"})

    assert responses[-1][0] == 200
    assert Handler.session_mgr is target
    assert active_session_id(tmp_path) == "target"
    assert all(item["session_id"] != "current" for item in responses[-1][1]["sessions"])
    assert responses[-1][1]["archived_sessions"][0]["session_id"] == "current"


def test_restoring_archived_session_reactivates_shared_backend_authority(tmp_path, monkeypatch):
    import api_serializers
    import handlers_sessions

    current = FakeManager(session_id="current", state_root=tmp_path)
    archived = FakeManager(session_id="archived", state_root=tmp_path)
    FakeManager.loaded = {"archived": archived}
    _write_session(tmp_path, "current", messages=[{"role": "user", "content": "actual"}])
    _write_session(tmp_path, "archived", messages=[{"role": "user", "content": "recuperable"}])
    archive_session(tmp_path, "archived")

    class Handler:
        session_mgr = current
        switch_engine = SimpleNamespace(adapters={})

    handler = Handler()
    responses = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))

    handlers_sessions.handle_post(handler, {"action": "switch", "session_id": "archived"})
    assert responses[-1][0] == 409

    handlers_sessions.handle_post(handler, {"action": "restore", "session_id": "archived"})

    assert responses[-1][0] == 200
    assert Handler.session_mgr is archived
    assert active_session_id(tmp_path) == "archived"
    assert session_archived(tmp_path, "archived") is False
    assert responses[-1][1]["archived_count"] == 0
    assert responses[-1][1]["active_session_id"] == "archived"


def test_ui_bootstrap_keeps_archived_session_catalog(tmp_path):
    from handlers_ui_bootstrap import _sessions_payload

    current = FakeManager(session_id="current", state_root=tmp_path)
    _write_session(tmp_path, "current", messages=[{"role": "user", "content": "actual"}])
    _write_session(tmp_path, "archived", messages=[{"role": "user", "content": "recuperable"}])
    archive_session(tmp_path, "archived")

    payload = _sessions_payload(current)

    assert payload["active_session_id"] == "current"
    assert payload["archived_count"] == 1
    assert payload["archived_sessions"][0]["session_id"] == "archived"
