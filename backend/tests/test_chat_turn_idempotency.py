from types import SimpleNamespace
import threading

import pytest


def _setup(tmp_path, monkeypatch, *, fail=False, internal=False):
    import api_serializers
    from context_store import ContextStore

    class Manager:
        session_id = "audit-session"
        provider = "offline"
        model = "fake-model"
        last_response_state = "done"
        last_clarification = None
        def __init__(self):
            self.store = ContextStore.create_new(base_dir=tmp_path)
            self.calls = 0
            self.entered = threading.Event()
            self.release = threading.Event()
            self.receipt_data = {"envelope_id": "first", "metadata": {}}
            self.last_receipt = SimpleNamespace(to_dict=lambda: self.receipt_data)
        def status(self):
            return {"session_id": self.session_id, "provider": self.provider, "model": self.model}
        def send(self, message):
            self.calls += 1
            self.entered.set()
            assert self.release.wait(3)
            if fail:
                raise RuntimeError("offline error")
            self.store.append_user(message)
            self.store.append_response("offline reply")
            return "offline reply"
        def send_internal(self, message):
            self.calls += 1
            return "internal reply"

    manager = Manager()
    handler = SimpleNamespace(session_mgr=manager, headers={}, chat_timeout_s=.01)
    responses = []
    monkeypatch.setattr(api_serializers, "send_json", lambda h, s, p: responses.append((s, p)))
    return manager, handler, responses


def test_timeout_returns_running_id_and_retry_never_dispatches_twice(tmp_path, monkeypatch):
    from handlers_chat import handle
    from chat_turns import turn_store
    manager, handler, responses = _setup(tmp_path, monkeypatch)
    try:
        handle(handler, {"message": "slow turn"})
        status, pending = responses[-1]
        assert status == 504 and pending["response_state"] == "running"
        assert pending["retry_with_same_turn_id"]
        turn_id = pending["turn_id"]
        assert manager.entered.wait(3)
        handle(handler, {"turn_id": turn_id})
        assert responses[-1][0] == 504
        handle(handler, {"message": "slow turn"})
        assert responses[-1][0] == 409
        assert responses[-1][1]["turn_id"] == turn_id
        assert manager.calls == 1
    finally:
        manager.release.set()
    assert turn_store(manager).lookup(turn_id).done.wait(3)
    handle(handler, {"turn_id": turn_id})
    assert responses[-1][0] == 200
    first_payload = responses[-1][1]
    assert first_payload["response"] == "offline reply"
    assert first_payload["turn_id"] == turn_id
    # Changing active conversation/receipt must not replace a cached result.
    other = manager.store.create_conversation()["conversation_id"]
    manager.receipt_data["envelope_id"] = "later"
    handle(handler, {"turn_id": turn_id})
    assert responses[-1][1]["context_receipt"]["envelope_id"] == "first"
    assert responses[-1][1]["conversation_id"] == "main"
    assert manager.store.get_history(conversation_id=other) == []
    assert manager.calls == 1


def test_unknown_id_is_not_a_new_operation_even_after_restart(tmp_path, monkeypatch):
    from handlers_chat import handle
    manager, handler, responses = _setup(tmp_path, monkeypatch)
    handle(handler, {"turn_id": "old-or-forged", "message": "never execute"})
    assert responses[-1][0] == 404
    assert manager.calls == 0


def test_mismatched_retry_cannot_repurpose_existing_turn(tmp_path, monkeypatch):
    from handlers_chat import handle
    from chat_turns import turn_store
    manager, handler, responses = _setup(tmp_path, monkeypatch)
    try:
        handle(handler, {"message": "original"})
        turn_id = responses[-1][1]["turn_id"]
        handle(handler, {"turn_id": turn_id, "message": "different"})
        assert responses[-1][0] == 409
        assert responses[-1][1]["code"] == "chat_turn_request_mismatch"
        assert manager.calls == 1
    finally:
        manager.release.set()
    assert turn_store(manager).lookup(turn_id).done.wait(3)


def test_failed_turn_is_cached_and_internal_receipt_remains_private(tmp_path, monkeypatch):
    from handlers_chat import handle
    manager, handler, responses = _setup(tmp_path, monkeypatch, fail=True)
    manager.release.set()
    handle(handler, {"message": "failure"})
    assert responses[-1][0] == 500
    turn_id = responses[-1][1]["turn_id"]
    handle(handler, {"turn_id": turn_id})
    assert responses[-1][0] == 500 and manager.calls == 1
    handle(handler, {"message": "helper", "internal": True})
    assert responses[-1][0] == 200
    assert responses[-1][1]["context_receipt"] is None


def test_evicted_id_fails_closed_without_reexecution():
    from chat_turns import ChatTurnStore, ChatTurnError
    store = ChatTurnStore(max_completed=1)
    calls = []
    def runner():
        calls.append(True)
        return "ok", {}
    first = store.get_or_start("first", False, "main", runner)
    assert first.done.wait(3)
    second = store.get_or_start("second", False, "main", runner)
    assert second.done.wait(3)
    with pytest.raises(ChatTurnError, match="no se reejecutó"):
        store.get_or_start("first", False, "main", runner, turn_id=first.turn_id)
    assert len(calls) == 2


def test_concurrent_retries_wait_on_one_worker():
    from chat_turns import ChatTurnStore
    store = ChatTurnStore()
    release = threading.Event()
    calls = []
    def runner():
        calls.append(True)
        assert release.wait(3)
        return "ok", {}
    first = store.get_or_start("message", False, "main", runner)
    result = []
    workers = [threading.Thread(target=lambda: result.append(store.get_or_start("message", False, "main", runner, turn_id=first.turn_id))) for _ in range(8)]
    try:
        for w in workers: w.start()
        for w in workers: w.join(3)
        assert len(result) == 8 and all(r is first for r in result)
    finally:
        release.set()
    assert first.done.wait(3) and len(calls) == 1
