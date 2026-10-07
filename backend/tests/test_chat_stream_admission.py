from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest


class _Wire:
    def __init__(self, *, disconnect_on_write: bool = False) -> None:
        self.data = bytearray()
        self.disconnect_on_write = disconnect_on_write

    def write(self, value: bytes) -> int:
        if self.disconnect_on_write:
            raise BrokenPipeError("client disconnected")
        self.data.extend(value)
        return len(value)

    def flush(self) -> None:
        return None


class _Handler:
    def __init__(self, manager, *, disconnect_on_write: bool = False) -> None:
        self.session_mgr = manager
        self.headers = {}
        self.chat_timeout_s = 2
        self.responses = []
        self.headers_sent = {}
        self.wfile = _Wire(disconnect_on_write=disconnect_on_write)

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers_sent[key] = value

    def end_headers(self) -> None:
        return None


class _Manager:
    session_id = "stream-session"
    provider = "provider-before"
    model = "model-before"
    last_response_state = "done"
    last_clarification = None
    last_stream_interpretation = {"route": "stream"}

    def __init__(self, base_dir, stream):
        from context_store import ContextStore

        self.store = ContextStore.create_new(base_dir=base_dir)
        self._stream = stream
        self.stream_calls = 0
        self.chat_calls = 0
        self.last_receipt = SimpleNamespace(
            to_dict=lambda: {
                "envelope_id": "stream-receipt",
                "provider_used": "provider-before",
                "model_used": "model-before",
                "metadata": {"reflexive_interpretation": {"route": "receipt"}},
            }
        )

    def send_stream(self, message):
        self.stream_calls += 1
        yield from self._stream(message)

    def send(self, message):
        self.chat_calls += 1
        return "chat reply"

    def send_internal(self, message):
        self.chat_calls += 1
        return "internal reply"

    def status(self):
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
        }


@pytest.fixture
def api_handlers(monkeypatch):
    import api_serializers
    import request_context
    from request_context import RequestContext

    def build(handler):
        return RequestContext(
            handler=handler,
            session_mgr=handler.session_mgr,
            chat_timeout_s=handler.chat_timeout_s,
        )

    send_json = lambda handler, status, payload: handler.responses.append((status, payload))
    monkeypatch.setattr(request_context, "build_context", build)
    monkeypatch.setattr(api_serializers, "send_json", send_json)
    monkeypatch.setattr(request_context, "send_json", send_json)


def _events(handler: _Handler) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in handler.wfile.data.decode("utf-8").split("\n\n")
        if line.startswith("data: ")
    ]


def test_stream_admission_blocks_chat_and_stream_overlaps_and_captures_turn_metadata(
    tmp_path, api_handlers,
):
    from chat_turns import turn_store
    from handlers_chat import handle as handle_chat
    from handlers_chat_stream import handle as handle_stream

    entered = threading.Event()
    paused_after_first = threading.Event()
    release = threading.Event()

    def provider_stream(_message):
        entered.set()
        yield "first"
        paused_after_first.set()
        assert release.wait(3)
        manager.provider = "provider-after"
        manager.model = "model-after"

    manager = _Manager(tmp_path, provider_stream)
    stream_handler = _Handler(manager)
    worker = threading.Thread(
        target=lambda: handle_stream(stream_handler, {"message": "same turn"}),
        daemon=True,
    )
    try:
        worker.start()
        assert entered.wait(3)

        duplicate_stream = _Handler(manager)
        handle_stream(duplicate_stream, {"message": "another stream"})
        assert duplicate_stream.responses[-1][0] == 409
        assert duplicate_stream.responses[-1][1]["code"] == "chat_turn_in_progress"

        chat_handler = _Handler(manager)
        handle_chat(chat_handler, {"message": "ordinary chat"})
        assert chat_handler.responses[-1][0] == 409
        assert chat_handler.responses[-1][1]["code"] == "chat_turn_in_progress"
        assert manager.stream_calls == 1
        assert manager.chat_calls == 0
        assert paused_after_first.wait(3)
        assert b'"chunk": "first"' in stream_handler.wfile.data
    finally:
        release.set()
        worker.join(3)

    assert not worker.is_alive()
    turn_id = stream_handler.headers_sent["X-Bago-Turn-Id"]
    turn = turn_store(manager).lookup(turn_id)
    assert turn.done.is_set()
    assert turn.conversation_id == "main"
    assert stream_handler.headers_sent["Content-Type"] == "text/event-stream"
    events = _events(stream_handler)
    done = events[-1]
    assert done["done"] is True and done["ok"] is True
    assert done["provider"] == "provider-before"
    assert done["model"] == "model-before"
    assert done["context_receipt"]["envelope_id"] == "stream-receipt"
    assert done["interpretation"] == {"route": "stream"}
    assert [event["chunk"] for event in events if "chunk" in event] == ["first"]

    manager.provider = "unrelated-provider"
    manager.model = "unrelated-model"
    manager.last_receipt = SimpleNamespace(to_dict=lambda: {"envelope_id": "later-receipt"})
    replay = _Handler(manager)
    handle_stream(replay, {"turn_id": turn_id})
    assert manager.stream_calls == 1
    replay_done = _events(replay)[-1]
    assert replay_done["provider"] == "provider-before"
    assert replay_done["model"] == "model-before"
    assert replay_done["context_receipt"]["envelope_id"] == "stream-receipt"
    other = manager.store.create_conversation()["conversation_id"]
    bound_replay = _Handler(manager)
    handle_stream(bound_replay, {
        "turn_id": turn_id,
        "conversation_id": other,
    })
    assert bound_replay.responses[-1][0] == 409
    assert bound_replay.responses[-1][1]["code"] == "chat_turn_request_mismatch"


@pytest.mark.parametrize("failure", [False, True], ids=["disconnect", "provider-failure"])
def test_stream_failure_or_disconnect_releases_shared_admission(
    tmp_path, api_handlers, failure,
):
    from chat_turns import turn_store
    from handlers_chat import handle as handle_chat
    from handlers_chat_stream import handle as handle_stream

    closed = threading.Event()

    def provider_stream(_message):
        try:
            yield "partial"
            if failure:
                raise RuntimeError("provider failed")
            yield "unreachable"
        finally:
            closed.set()

    manager = _Manager(tmp_path, provider_stream)
    stream_handler = _Handler(manager, disconnect_on_write=not failure)
    handle_stream(stream_handler, {"message": "stream"})

    turn_id = stream_handler.headers_sent["X-Bago-Turn-Id"]
    turn = turn_store(manager).lookup(turn_id)
    assert turn.done.is_set()
    assert closed.is_set()
    assert turn.stream_status == ("failed" if failure else "cancelled")

    chat_handler = _Handler(manager)
    handle_chat(chat_handler, {"message": "after stream"})
    assert chat_handler.responses[-1][0] == 200
    assert manager.chat_calls == 1
