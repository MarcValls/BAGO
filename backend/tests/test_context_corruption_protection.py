from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_store import ContextStore


def _write_context_jsonl(path: Path, records: list[dict | bytes]) -> None:
    """Write context.jsonl mixing dict records and raw byte fragments."""
    parts: list[bytes] = []
    for record in records:
        if isinstance(record, bytes):
            parts.append(record)
        else:
            parts.append(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        parts.append(b"\n")
    path.write_bytes(b"".join(parts))


def _write_timeline_jsonl(path: Path, records: list[dict | bytes]) -> None:
    """Write timeline.jsonl mixing dict records and raw byte fragments."""
    _write_context_jsonl(path, records)


def _make_session_dir(tmp_path: Path, session_id: str = "corrupt-test") -> Path:
    session_dir = tmp_path / "sessions" / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(
        json.dumps({"created_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    return session_dir


def test_healthy_context_and_timeline_remain_unaffected(tmp_path: Path) -> None:
    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("hello")
    store.append_response("hi", provider="mock", model="m")

    assert store.recovery_errors == []
    assert not store._corrupt_paths

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    assert reloaded.recovery_errors == []
    assert not reloaded._corrupt_paths
    assert [m["content"] for m in reloaded.get_history()] == ["hello", "hi"]


def test_corrupt_middle_json_in_context_retains_valid_records(tmp_path: Path, caplog) -> None:
    session_dir = _make_session_dir(tmp_path)
    context_path = session_dir / "context.jsonl"
    _write_context_jsonl(
        context_path,
        [
            {"role": "user", "content": "first"},
            b"this is not json",
            {"role": "assistant", "content": "third"},
        ],
    )

    store = ContextStore.load("corrupt-test", base_dir=tmp_path)

    assert len(store.get_history()) == 2
    assert [m["content"] for m in store.get_history()] == ["first", "third"]
    assert len(store.recovery_errors) == 1
    error = store.recovery_errors[0]
    assert error["path"] == str(context_path)
    assert error["line"] == 2
    assert error["reason"] == "json-syntax"
    assert context_path in store._corrupt_paths
    assert "Corrupt context record skipped" in caplog.text


def test_corrupt_middle_schema_in_context_retains_valid_records(tmp_path: Path) -> None:
    session_dir = _make_session_dir(tmp_path)
    context_path = session_dir / "context.jsonl"
    _write_context_jsonl(
        context_path,
        [
            {"role": "user", "content": "first"},
            {"content": "missing role field"},
            {"role": "assistant", "content": "third"},
        ],
    )

    store = ContextStore.load("corrupt-test", base_dir=tmp_path)

    assert len(store.get_history()) == 2
    assert [m["content"] for m in store.get_history()] == ["first", "third"]
    assert len(store.recovery_errors) == 1
    error = store.recovery_errors[0]
    assert error["reason"] == "schema"
    assert error["path"] == str(context_path)
    assert error["line"] == 2
    assert context_path in store._corrupt_paths


def test_corrupt_middle_utf8_in_context_retains_valid_records(tmp_path: Path) -> None:
    session_dir = _make_session_dir(tmp_path)
    context_path = session_dir / "context.jsonl"
    _write_context_jsonl(
        context_path,
        [
            {"role": "user", "content": "first"},
            b'{"role":"user","content":"bad utf8 \xff"}',
            {"role": "assistant", "content": "third"},
        ],
    )

    store = ContextStore.load("corrupt-test", base_dir=tmp_path)

    assert len(store.get_history()) == 2
    assert [m["content"] for m in store.get_history()] == ["first", "third"]
    assert len(store.recovery_errors) == 1
    error = store.recovery_errors[0]
    assert error["reason"] == "utf8-decode"
    assert error["path"] == str(context_path)
    assert error["line"] == 2
    assert context_path in store._corrupt_paths


def test_corrupt_timeline_retains_valid_records(tmp_path: Path) -> None:
    session_dir = _make_session_dir(tmp_path)
    _write_context_jsonl(session_dir / "context.jsonl", [])
    timeline_path = session_dir / "timeline.jsonl"
    _write_timeline_jsonl(
        timeline_path,
        [
            {"kind": "session", "title": "start"},
            b"bad json",
            {"kind": "session", "title": "end"},
        ],
    )

    store = ContextStore.load("corrupt-test", base_dir=tmp_path)

    assert [e["title"] for e in store.get_timeline(limit=10)] == ["start", "end"]
    assert any(e["path"] == str(timeline_path) and e["reason"] == "json-syntax" for e in store.recovery_errors)
    assert timeline_path in store._corrupt_paths


def test_recovery_errors_contain_no_sensitive_content(tmp_path: Path) -> None:
    session_dir = _make_session_dir(tmp_path)
    context_path = session_dir / "context.jsonl"
    _write_context_jsonl(
        context_path,
        [
            {"role": "user", "content": "first"},
            {"content": "super-secret-password"},
            {"role": "assistant", "content": "third"},
        ],
    )

    store = ContextStore.load("corrupt-test", base_dir=tmp_path)
    assert len(store.recovery_errors) == 1
    for error in store.recovery_errors:
        assert "path" in error
        assert "line" in error
        assert "reason" in error
        assert "super-secret-password" not in str(error.values())
        assert "content" not in error


def test_mark_good_blocked_for_corrupt_context_preserves_memory_and_file(tmp_path: Path) -> None:
    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("one")
    store.append_response("two", provider="mock", model="m")
    store.append_user("three")

    session_dir = tmp_path / "sessions" / store.sid
    context_path = session_dir / "context.jsonl"
    original_bytes = context_path.read_bytes()

    # Corrupt the middle record.
    lines = original_bytes.splitlines(keepends=True)
    lines.insert(1, b"not json\n")
    context_path.write_bytes(b"".join(lines))
    corrupt_bytes = context_path.read_bytes()

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    assert len(reloaded.recovery_errors) == 1
    assert context_path in reloaded._corrupt_paths
    original_history = [dict(m) for m in reloaded.get_history()]
    assert len(original_history) == 3

    with pytest.raises(RuntimeError) as exc_info:
        reloaded.mark_good()

    assert "Refusing destructive rewrite" in str(exc_info.value)
    assert [dict(m) for m in reloaded.get_history()] == original_history
    assert context_path.read_bytes() == corrupt_bytes


def test_clear_history_blocked_for_corrupt_context_preserves_memory_and_file(tmp_path: Path) -> None:
    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("one")
    store.append_response("two", provider="mock", model="m")

    session_dir = tmp_path / "sessions" / store.sid
    context_path = session_dir / "context.jsonl"
    original_bytes = context_path.read_bytes()

    lines = original_bytes.splitlines(keepends=True)
    lines.insert(0, b"not json\n")
    context_path.write_bytes(b"".join(lines))
    corrupt_bytes = context_path.read_bytes()

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    original_history = [dict(m) for m in reloaded.get_history()]
    assert original_history

    with pytest.raises(RuntimeError) as exc_info:
        reloaded.clear_history()

    assert "Refusing destructive rewrite" in str(exc_info.value)
    assert [dict(m) for m in reloaded.get_history()] == original_history
    assert context_path.read_bytes() == corrupt_bytes


def test_compress_history_blocked_for_corrupt_context_preserves_memory_and_file(tmp_path: Path) -> None:
    store = ContextStore.create_new(base_dir=tmp_path)
    for i in range(5):
        store.append_user(f"user-{i}")
        store.append_response(f"response-{i}", provider="mock", model="m")

    session_dir = tmp_path / "sessions" / store.sid
    context_path = session_dir / "context.jsonl"
    original_bytes = context_path.read_bytes()

    lines = original_bytes.splitlines(keepends=True)
    lines.insert(2, b"not json\n")
    context_path.write_bytes(b"".join(lines))
    corrupt_bytes = context_path.read_bytes()

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    original_history = [dict(m) for m in reloaded.get_history()]
    assert len(original_history) >= 8

    with pytest.raises(RuntimeError) as exc_info:
        reloaded.compress_history(target_messages=1)

    assert "Refusing destructive rewrite" in str(exc_info.value)
    assert [dict(m) for m in reloaded.get_history()] == original_history
    assert context_path.read_bytes() == corrupt_bytes


def test_append_still_allowed_on_corrupt_loaded_context(tmp_path: Path) -> None:
    store = ContextStore.create_new(base_dir=tmp_path)
    store.append_user("one")
    store.append_response("two", provider="mock", model="m")

    session_dir = tmp_path / "sessions" / store.sid
    context_path = session_dir / "context.jsonl"
    original_bytes = context_path.read_bytes()
    lines = original_bytes.splitlines(keepends=True)
    lines.insert(1, b"not json\n")
    context_path.write_bytes(b"".join(lines))
    corrupt_bytes = context_path.read_bytes()

    reloaded = ContextStore.load(store.sid, base_dir=tmp_path)
    before_history = reloaded.get_history()
    reloaded.append_user("after corruption")
    after_history = reloaded.get_history()

    assert len(after_history) == len(before_history) + 1
    assert after_history[-1]["content"] == "after corruption"
    new_bytes = context_path.read_bytes()
    assert new_bytes.startswith(corrupt_bytes)


def test_torn_tail_append_preserves_bytes_and_next_record(tmp_path):
    session_dir = _make_session_dir(tmp_path)
    path = session_dir / "context.jsonl"
    torn = b'{"role":"user","content":"unfinished'
    path.write_bytes(torn)
    store = ContextStore.load("corrupt-test", base_dir=tmp_path)
    store.append_user("new valid record")
    assert path.read_bytes().startswith(torn + b"\n")
    reloaded = ContextStore.load("corrupt-test", base_dir=tmp_path)
    assert [m["content"] for m in reloaded.get_history()] == ["new valid record"]
    assert reloaded.recovery_errors[0]["line"] == 1


def test_nonstring_message_content_reported_as_schema_error(tmp_path):
    session_dir = _make_session_dir(tmp_path)
    _write_context_jsonl(session_dir / "context.jsonl", [{"role": "user", "content": 123}])
    store = ContextStore.load("corrupt-test", base_dir=tmp_path)
    assert store.get_history() == []
    assert store.recovery_errors[0]["reason"] == "schema"


def test_read_failure_is_not_empty_history(tmp_path, monkeypatch):
    session_dir = _make_session_dir(tmp_path)
    path = session_dir / "context.jsonl"
    path.write_text('{"role":"user","content":"preserve"}\n', encoding="utf-8")
    original = path.read_bytes()
    real_read = Path.read_bytes
    def fail_read(candidate):
        if candidate == path:
            raise PermissionError("unreadable history")
        return real_read(candidate)
    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(PermissionError, match="unreadable history"):
        ContextStore.load("corrupt-test", base_dir=tmp_path)
    assert real_read(path) == original
