"""Regression tests at public turn boundaries, with real store persistence."""
from types import SimpleNamespace
import threading

import pytest


def _manager(tmp_path, *, fail=False):
    from context_store import ContextStore
    from session_turn_mixin import SessionTurnMixin

    class Manager(SessionTurnMixin):
        def _send_turn(self, message, **kwargs):
            self.history_seen = self.store.get_history()
            self.entered.set()
            assert self.release.wait(3)
            if fail:
                raise RuntimeError("provider failed")
            self.store.append_user(message)
            self.store.append_response("reply from original history")
            self.completed.set()
            return "reply"

        def _send_stream_turn(self, message, **kwargs):
            self.history_seen = self.store.get_history()
            yield "chunk"
            self.store.append_user(message)
            self.store.append_response("streamed reply")

    manager = Manager()
    manager.store = ContextStore.create_new(base_dir=tmp_path)
    manager.store.append_user("main history")
    manager.entered = threading.Event()
    manager.release = threading.Event()
    manager.completed = threading.Event()
    return manager


def test_public_send_keeps_original_conversation_across_switch(tmp_path):
    manager = _manager(tmp_path)
    errors = []
    def run():
        try:
            manager.send("main turn")
        except Exception as exc:
            errors.append(exc)
    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert manager.entered.wait(3)
        other = manager.store.create_conversation("Other")["conversation_id"]
        manager.store.append_user("other history")
    finally:
        manager.release.set()
        worker.join(3)
    assert not worker.is_alive() and not errors
    assert [m["content"] for m in manager.history_seen] == ["main history"]
    assert [m["content"] for m in manager.store.get_history(conversation_id="main")] == ["main history", "main turn", "reply from original history"]
    assert [m["content"] for m in manager.store.get_history(conversation_id=other)] == ["other history"]
    assert manager.store.active_conversation_id == other


def test_send_exception_restores_scope(tmp_path):
    manager = _manager(tmp_path, fail=True)
    manager.release.set()
    with pytest.raises(RuntimeError, match="provider failed"):
        manager.send("failing turn", conversation_id="main")
    other = manager.store.create_conversation()["conversation_id"]
    assert manager.store.active_conversation_id == other
    assert getattr(manager.store._conversation_local, "conversation_id", "") == ""


def test_stream_captures_conversation_before_first_iteration_and_restores_on_close(tmp_path):
    manager = _manager(tmp_path)
    stream = manager.send_stream("stream turn")
    other = manager.store.create_conversation("Other")["conversation_id"]
    assert next(stream) == "chunk"
    assert manager.history_seen[0]["content"] == "main history"
    assert list(stream) == []
    assert manager.store.get_history(conversation_id="main")[-1]["content"] == "streamed reply"
    assert manager.store.get_history(conversation_id=other) == []
    assert manager.store.active_conversation_id == other
    stream = manager.send_stream("unfinished", conversation_id="main")
    assert next(stream) == "chunk"
    stream.close()
    assert manager.store.active_conversation_id == other


def test_watchdog_carries_request_thread_conversation_to_worker(tmp_path):
    from handlers_chat import _send_with_watchdog
    manager = _manager(tmp_path)
    response, error, _ = _send_with_watchdog(SimpleNamespace(session_mgr=manager), "slow main turn", .01)
    assert response is None and error["timed_out"]
    try:
        assert manager.entered.wait(3)
        other = manager.store.create_conversation("Other")["conversation_id"]
    finally:
        manager.release.set()
    assert manager.completed.wait(3)
    assert manager.store.get_history(conversation_id=other) == []
    assert manager.store.get_history(conversation_id="main")[-2]["content"] == "slow main turn"


def test_paused_stream_does_not_redirect_another_turn_on_the_same_thread(tmp_path):
    manager = _manager(tmp_path)
    stream = manager.send_stream("original stream")
    try:
        assert next(stream) == "chunk"
        other = manager.store.create_conversation("Other")["conversation_id"]
        assert manager.store.active_conversation_id == other
        manager.release.set()
        manager.send("other turn")
        assert manager.store.get_history(conversation_id=other)[0]["content"] == "other turn"
        assert list(stream) == []
        assert manager.store.get_history(conversation_id="main")[-2]["content"] == "original stream"
    finally:
        stream.close()


def test_stream_resumes_on_another_thread_without_leaking_scope(tmp_path):
    manager = _manager(tmp_path)
    stream = manager.send_stream("migrated stream")
    assert next(stream) == "chunk"
    other = manager.store.create_conversation("Other")["conversation_id"]
    errors = []
    def finish():
        try:
            assert list(stream) == []
            assert manager.store.active_conversation_id == other
        except Exception as exc:
            errors.append(exc)
    worker = threading.Thread(target=finish)
    worker.start()
    worker.join(3)
    assert not worker.is_alive() and not errors
    assert manager.store.active_conversation_id == other
    assert manager.store.get_history(conversation_id="main")[-2]["content"] == "migrated stream"
    assert manager.store.get_history(conversation_id=other) == []


def test_started_stream_remains_bound_if_conversation_is_archived(tmp_path):
    manager = _manager(tmp_path)
    stream = manager.send_stream("archived stream")
    assert next(stream) == "chunk"
    other = manager.store.create_conversation("Other")["conversation_id"]
    manager.store.archive_conversation("main")
    assert list(stream) == []
    assert manager.store.active_conversation_id == other
    assert [m.content for m in manager.store._messages if m.conversation_id == "main"][-2] == "archived stream"


@pytest.mark.parametrize("operation", ["throw", "close", "gc"])
def test_stream_cleanup_executes_bound_without_leaking_caller_scope(tmp_path, monkeypatch, operation):
    import gc
    manager = _manager(tmp_path)
    def body(message, **kwargs):
        try:
            yield "chunk"
        finally:
            manager.store.append_user("cleanup " + message)
    monkeypatch.setattr(manager, "_send_stream_turn", body)
    stream = manager.send_stream("original")
    assert next(stream) == "chunk"
    other = manager.store.create_conversation("Other")["conversation_id"]
    if operation == "throw":
        with pytest.raises(RuntimeError, match="consumer error"):
            stream.throw(RuntimeError("consumer error"))
    elif operation == "close":
        errors = []
        def close():
            try:
                stream.close()
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=close)
        worker.start()
        worker.join(3)
        assert not worker.is_alive() and not errors
    else:
        del stream
        gc.collect()
    assert manager.store.active_conversation_id == other
    assert manager.store.get_history(conversation_id="main")[-1]["content"] == "cleanup original"
    assert manager.store.get_history(conversation_id=other) == []


def test_new_stream_cannot_target_an_already_archived_conversation(tmp_path):
    manager = _manager(tmp_path)
    manager.store.create_conversation("Other")
    manager.store.archive_conversation("main")
    with pytest.raises(ValueError, match="archivada"):
        manager.send_stream("new turn", conversation_id="main")
