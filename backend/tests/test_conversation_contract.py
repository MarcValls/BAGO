from __future__ import annotations

import json
from types import SimpleNamespace

from context_store import ContextStore


def test_legacy_history_is_exposed_as_main_without_rewrite(tmp_path):
    session_dir = tmp_path / "sessions" / "legacy"
    session_dir.mkdir(parents=True)
    context_path = session_dir / "context.jsonl"
    context_path.write_text(json.dumps({"role": "user", "content": "legado"}) + "\n", encoding="utf-8")
    (session_dir / "meta.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")

    store = ContextStore.load("legacy", base_dir=tmp_path)

    assert store.active_conversation_id == "main"
    assert store.get_history()[0]["conversation_id"] == "main"
    assert store.list_conversations()[0]["message_count"] == 1
    assert "conversation_id" not in context_path.read_text(encoding="utf-8")


def test_conversations_keep_histories_isolated_and_persist_active(tmp_path):
    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("mensaje principal")
    second = store.create_conversation("Diseño")
    second_id = second["conversation_id"]
    store.append_user("mensaje diseño")

    with store.conversation_scope("main"):
        store.append_response("respuesta principal")

    assert store.active_conversation_id == second_id
    assert [item["content"] for item in store.get_history()] == ["mensaje diseño"]
    assert [item["content"] for item in store.get_history(conversation_id="main")] == ["mensaje principal", "respuesta principal"]

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    assert reloaded.active_conversation_id == second_id
    assert [item["conversation_id"] for item in reloaded.get_history()] == [second_id]
    assert reloaded.list_conversations()[0]["conversation_id"] == second_id


def test_conversation_handler_create_and_switch_returns_active_history(tmp_path, monkeypatch):
    import api_serializers
    import handlers_conversations

    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("principal")
    manager = SimpleNamespace(session_id="session-test", store=store, save=lambda: None)
    handler = SimpleNamespace(session_mgr=manager)
    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))

    handlers_conversations.handle_post(handler, {"action": "create", "title": "Segundo chat"})
    status, created = responses[-1]
    second_id = created["active_conversation_id"]
    assert status == 200
    assert second_id.startswith("chat-")
    assert created["history"]["messages"] == []

    handlers_conversations.handle_post(handler, {"action": "switch", "conversation_id": "main"})
    status, switched = responses[-1]
    assert status == 200
    assert switched["active_conversation_id"] == "main"
    assert switched["history"]["messages"][0]["content"] == "principal"


def test_conversation_rename_and_archive_keep_recoverable_history(tmp_path):
    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("mensaje conservado")
    created = store.create_conversation("Temporal")
    conversation_id = created["conversation_id"]
    store.append_user("mensaje secundario")

    renamed = store.rename_conversation(conversation_id, "Informe semanal")
    archived = store.archive_conversation(conversation_id)

    assert renamed["title"] == "Informe semanal"
    assert archived["archived"] is True
    assert store.active_conversation_id == "main"
    assert [item["content"] for item in store.get_history(conversation_id="main")] == ["mensaje conservado"]

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    archived_record = next(item for item in reloaded.list_conversations(include_archived=True) if item["conversation_id"] == conversation_id)
    assert archived_record["title"] == "Informe semanal"
    assert archived_record["archived"] is True
    assert archived_record["message_count"] == 1
    assert archived_record["preview"] == "mensaje secundario"


def test_workspace_conversation_scopes_history_by_root(tmp_path, monkeypatch):
    import api_serializers
    import handlers_workspace_conversation

    store = ContextStore.create_new(base_dir=tmp_path)
    manager = SimpleNamespace(session_id="session-test", store=store, save=lambda: None)
    handler = SimpleNamespace(session_mgr=manager)
    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))

    handlers_workspace_conversation.handle(handler, {"root": "C:/repo-one"})
    first = responses[-1][1]
    first_id = first["conversation_id"]
    handlers_workspace_conversation.handle(handler, {"root": "C:/repo-two"})
    second = responses[-1][1]
    handlers_workspace_conversation.handle(handler, {"root": "C:/repo-one/"})
    returned = responses[-1][1]

    assert first_id != second["conversation_id"]
    assert returned["conversation_id"] == first_id
    assert store.active_conversation_id == first_id
