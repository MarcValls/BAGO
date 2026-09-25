from __future__ import annotations

import tempfile
import sqlite3
from concurrent.futures import ThreadPoolExecutor


def _memory_write(state_root, operation, **arguments):
    from database_write_request import build_memory_database_request
    from execution_adapter_contract import ExecutionContext
    from execution_adapters.database_write import DatabaseWriteEffectAdapter

    class Manager:
        session_id = "test-memory-session"
        workspace_id = "test-workspace"
        project_root = str(state_root)

        def __init__(self, root):
            self.state_root = root

    manager = Manager(state_root)
    request = build_memory_database_request(
        manager,
        operation=operation,
        arguments=arguments,
        source_surface="test.memory.database",
    )
    authorization = {
        "state": "consumed",
        "effect_id": request.effect_id,
        "operation_fingerprint": request.fingerprint,
        "session_id": request.session_id,
    }
    return DatabaseWriteEffectAdapter().execute(
        request,
        ExecutionContext(manager=manager, services={"_authorization": authorization}),
    )


def test_fts_tracks_ids_and_deprecation():
    from knowledge_base import KnowledgeBase

    with tempfile.TemporaryDirectory() as state_root:
        store = KnowledgeBase(state_root=state_root)
        try:
            first = _memory_write(state_root, "knowledge.add", content="BAGO integra memoria persistente")["memory_id"]
            second = _memory_write(state_root, "knowledge.add", content="BAGO integra búsqueda vectorial")["memory_id"]
            found = store.search("BAGO")
            assert {item["id"] for item in found} == {first, second}
            assert _memory_write(state_root, "knowledge.deprecate", memory_id=first)["deprecated"]
            assert [item["id"] for item in store.search("persistente")] == []
            assert store.count() == 1
            assert store.count(include_deprecated=True) == 2
        finally:
            store.close()


def test_knowledge_store_uses_concurrency_pragmas_and_serializes_threads(tmp_path):
    from knowledge_base import KnowledgeBase

    store = KnowledgeBase(state_root=str(tmp_path))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(lambda index: _memory_write(tmp_path, "knowledge.add", content=f"memory-{index}")["memory_id"], range(20)))
        conn = store._connect()
        assert conn is not None
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert len(set(ids)) == 20
        assert store.count() == 20
    finally:
        store.close()


def test_two_knowledge_instances_share_one_wal_database(tmp_path):
    from knowledge_base import KnowledgeBase

    first = KnowledgeBase(state_root=str(tmp_path))
    second = KnowledgeBase(state_root=str(tmp_path))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda item: _memory_write(tmp_path, "knowledge.add", content=item)["memory_id"], ["one", "two"]))
        assert first.count() == 2
        assert second.count() == 2
    finally:
        first.close()
        second.close()


def test_embedding_store_validates_upserts_filters_and_removes():
    from embedding_store import EmbeddingStore

    with tempfile.TemporaryDirectory() as state_root:
        store = EmbeddingStore(state_root=state_root)
        try:
            first = _memory_write(state_root, "embedding.upsert", memory_id="m1", content="alpha", vector=[1, 0], provider="local", model="e1")["embedding_id"]
            assert _memory_write(state_root, "embedding.upsert", memory_id="m1", content="alpha updated", vector=[0.9, 0.1], provider="local", model="e1")["embedding_id"] == first
            _memory_write(state_root, "embedding.upsert", memory_id="m2", content="beta", vector=[0, 1], provider="remote", model="e2")
            results = store.search(query_vector=[1, 0], provider="local", model="e1")
            assert len(results) == 1 and results[0]["content"] == "alpha updated"
            remote = store.search(query_vector=[1, 0], provider="remote", model="e2")
            assert len(remote) == 1 and remote[0]["memory_id"] == "m2"
            assert _memory_write(state_root, "embedding.delete_for_memory", memory_id="m1")["deleted_count"] == 1
            assert [item["memory_id"] for item in store.search(query_vector=[1, 0])] == ["m2"]
            stats = store.stats()
            assert stats["total"] == 1
            assert stats["min_dim"] == stats["max_dim"] == 2
        finally:
            store.close()


def test_embedding_store_uses_wal_and_serializes_threaded_writes(tmp_path):
    from embedding_store import EmbeddingStore

    store = EmbeddingStore(state_root=str(tmp_path))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(
                lambda index: _memory_write(tmp_path, "embedding.upsert", memory_id=f"m-{index}", content=f"value-{index}", vector=[1.0, float(index)])["embedding_id"],
                range(20),
            ))
        conn = store._connect()
        assert conn is not None
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert len(set(ids)) == 20
        assert store.stats()["total"] == 20
    finally:
        store.close()


def test_two_embedding_instances_share_one_wal_database(tmp_path):
    from embedding_store import EmbeddingStore

    first = EmbeddingStore(state_root=str(tmp_path))
    second = EmbeddingStore(state_root=str(tmp_path))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(
                lambda item: _memory_write(tmp_path, "embedding.upsert", memory_id=item, content=item, vector=[1.0, 0.0])["embedding_id"],
                ["first", "second"],
            ))
        assert first.stats()["total"] == 2
        assert second.stats()["total"] == 2
    finally:
        first.close()
        second.close()


def test_embedding_failed_write_rolls_back_transaction(tmp_path):
    from embedding_store import EmbeddingStore
    from execution_adapter_contract import ExecutionGatewayError

    store = EmbeddingStore(state_root=str(tmp_path))
    try:
        _memory_write(tmp_path, "embedding.upsert", memory_id="kept", content="kept", vector=[1.0, 0.0])
        setup = sqlite3.connect(store.db_path)
        setup.execute(
            """CREATE TRIGGER reject_embedding BEFORE INSERT ON embeddings
               WHEN NEW.memory_id = 'rejected'
               BEGIN SELECT RAISE(ABORT, 'forced failure'); END"""
        )
        setup.commit()
        setup.close()
        try:
            _memory_write(tmp_path, "embedding.upsert", memory_id="rejected", content="rejected", vector=[0.0, 1.0])
        except ExecutionGatewayError as exc:
            assert exc.code == "database_write_failed"
        else:
            raise AssertionError("forced SQLite failure was not raised")
        assert store.stats()["total"] == 1
        _memory_write(tmp_path, "embedding.upsert", memory_id="after", content="after", vector=[0.5, 0.5])
        assert store.stats()["total"] == 2
    finally:
        store.close()


def test_memory_http_contract_supports_status_hybrid_search_and_upsert(tmp_path, monkeypatch):
    import api_serializers
    from handlers_memory import handle_embedding_upsert, handle_search, handle_status

    class Manager:
        base_path = tmp_path
        state_root = tmp_path / "memory-state"
        session_id = "active-session-001"
        workspace_id = "memory-test-workspace"
        project_root = tmp_path

    class Handler:
        session_mgr = Manager()
        headers = {"X-Bago-Channel": "ui-react"}

    captured = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _h, status, payload: captured.append((status, payload)))
    _memory_write(Manager.state_root, "knowledge.add", content="BAGO conserva conocimiento avanzado")
    monkeypatch.setenv("BAGO_STATE_ROOT", str(tmp_path / "authorization-state"))
    interaction_id = "memory-upsert-interaction"
    payload = {
        "memory_id": "m-advanced",
        "content": "BAGO conserva conocimiento avanzado",
        "vector": [1.0, 0.0, 0.0],
        "source_session": "forged-session-from-request",
        "provider": "local",
        "model": "deterministic-test",
        "interaction_id": interaction_id,
    }
    handle_embedding_upsert(Handler(), {**payload, "authorization_action": "challenge"})
    challenge = captured[-1][1]["authorization"]["challenge"]["challenge_id"]
    handle_embedding_upsert(Handler(), {
        **payload,
        "authorization_action": "approve",
        "challenge_id": challenge,
        "user_decision": "approve",
    })
    permit = captured[-1][1]["authorization"]["permit"]["token"]
    handle_embedding_upsert(Handler(), {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })
    handle_search(Handler(), {"query": "conocimiento", "query_vector": [1.0, 0.0, 0.0]})
    handle_status(Handler())

    assert [status for status, _ in captured] == [200, 200, 200, 200, 200]
    assert captured[2][1]["vector_dim"] == 3
    assert captured[3][1]["mode"] == "hybrid"
    assert len(captured[3][1]["lexical"]) == 1
    assert captured[3][1]["semantic"][0]["memory_id"] == "m-advanced"
    assert captured[3][1]["semantic"][0]["source_session"] == "active-session-001"
    assert captured[4][1]["knowledge"]["active"] == 1
    assert captured[4][1]["embeddings"]["total"] == 1
    assert captured[4][1]["embeddings"]["vectors_generated_by_server"] is False


def test_embedding_upsert_without_active_session_fails_before_store_creation(tmp_path, monkeypatch):
    import api_serializers
    from handlers_memory import handle_embedding_upsert

    class Manager:
        base_path = tmp_path
        state_root = tmp_path

    class Handler:
        session_mgr = Manager()

    captured = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _h, status, payload: captured.append((status, payload)))

    handle_embedding_upsert(Handler(), {
        "memory_id": "m-no-session",
        "content": "must not persist",
        "vector": [1.0, 0.0],
        "source_session": "caller-chosen-session",
    })

    assert captured == [(409, {"error": "active_session_required"})]
    assert list(tmp_path.iterdir()) == []
