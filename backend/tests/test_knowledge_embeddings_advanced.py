from __future__ import annotations

import tempfile
import sqlite3
from concurrent.futures import ThreadPoolExecutor


def test_fts_tracks_ids_and_deprecation():
    from knowledge_base import KnowledgeBase

    with tempfile.TemporaryDirectory() as state_root:
        store = KnowledgeBase(state_root=state_root)
        try:
            first = store.add("BAGO integra memoria persistente", "s1")
            second = store.add("BAGO integra búsqueda vectorial", "s2")
            found = store.search("BAGO")
            assert {item["id"] for item in found} == {first, second}
            assert store.deprecate(first)
            assert [item["id"] for item in store.search("persistente")] == []
            assert store.count() == 1
            assert store.count(include_deprecated=True) == 2
        finally:
            store.close()


def test_knowledge_store_uses_concurrency_pragmas_and_serializes_threads(tmp_path):
    from knowledge_base import KnowledgeBase

    store = KnowledgeBase(state_root=str(tmp_path))
    try:
        conn = store._connect()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(lambda index: store.add(f"memory-{index}", "thread-test"), range(20)))
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
            list(pool.map(lambda item: item[0].add(item[1], "multi-instance"), [(first, "one"), (second, "two")]))
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
            first = store.add(memory_id="m1", content="alpha", vector=[1, 0], provider="local", model="e1")
            assert store.add(memory_id="m1", content="alpha updated", vector=[0.9, 0.1], provider="local", model="e1") == first
            store.add(memory_id="m2", content="beta", vector=[0, 1], provider="remote", model="e2")
            results = store.search(query_vector=[1, 0], provider="local", model="e1")
            assert len(results) == 1 and results[0]["content"] == "alpha updated"
            remote = store.search(query_vector=[1, 0], provider="remote", model="e2")
            assert len(remote) == 1 and remote[0]["memory_id"] == "m2"
            assert store.remove_for_memory("m1") == 1
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
        assert store.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert store.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(
                lambda index: store.add(memory_id=f"m-{index}", content=f"value-{index}", vector=[1.0, float(index)]),
                range(20),
            ))
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
                lambda item: item[0].add(memory_id=item[1], content=item[1], vector=[1.0, 0.0]),
                [(first, "first"), (second, "second")],
            ))
        assert first.stats()["total"] == 2
        assert second.stats()["total"] == 2
    finally:
        first.close()
        second.close()


def test_embedding_failed_write_rolls_back_transaction(tmp_path):
    from embedding_store import EmbeddingStore

    store = EmbeddingStore(state_root=str(tmp_path))
    try:
        store.add(memory_id="kept", content="kept", vector=[1.0, 0.0])
        store.conn.execute(
            """CREATE TRIGGER reject_embedding BEFORE INSERT ON embeddings
               WHEN NEW.memory_id = 'rejected'
               BEGIN SELECT RAISE(ABORT, 'forced failure'); END"""
        )
        store.conn.commit()
        try:
            store.add(memory_id="rejected", content="rejected", vector=[0.0, 1.0])
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("forced SQLite failure was not raised")
        assert store.stats()["total"] == 1
        store.add(memory_id="after", content="after", vector=[0.5, 0.5])
        assert store.stats()["total"] == 2
    finally:
        store.close()


def test_memory_http_contract_supports_status_hybrid_search_and_upsert(tmp_path, monkeypatch):
    import api_serializers
    from handlers_memory import handle_embedding_upsert, handle_search, handle_status
    from knowledge_base import KnowledgeBase

    class Manager:
        base_path = tmp_path
        state_root = tmp_path

    class Handler:
        session_mgr = Manager()

    kb = KnowledgeBase(state_root=str(tmp_path))
    kb.add("BAGO conserva conocimiento avanzado", "s1")
    kb.close()

    captured = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _h, status, payload: captured.append((status, payload)))

    handle_embedding_upsert(Handler(), {
        "memory_id": "m-advanced",
        "content": "BAGO conserva conocimiento avanzado",
        "vector": [1.0, 0.0, 0.0],
        "provider": "local",
        "model": "deterministic-test",
    })
    handle_search(Handler(), {"query": "conocimiento", "query_vector": [1.0, 0.0, 0.0]})
    handle_status(Handler())

    assert [status for status, _ in captured] == [200, 200, 200]
    assert captured[0][1]["vector_dim"] == 3
    assert captured[1][1]["mode"] == "hybrid"
    assert len(captured[1][1]["lexical"]) == 1
    assert captured[1][1]["semantic"][0]["memory_id"] == "m-advanced"
    assert captured[2][1]["knowledge"]["active"] == 1
    assert captured[2][1]["embeddings"]["total"] == 1
    assert captured[2][1]["embeddings"]["vectors_generated_by_server"] is False
