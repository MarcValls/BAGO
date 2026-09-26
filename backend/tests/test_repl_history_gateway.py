from __future__ import annotations

from pathlib import Path

import repl_history


def test_readline_history_uses_state_writer_without_readline_file_writer(monkeypatch, tmp_path: Path):
    calls = []

    def write_text_atomic(path, content, **kwargs):
        calls.append((path, content, kwargs))
        return {"ok": True}

    monkeypatch.setattr("bago_core.server_effects.write_text_atomic", write_text_atomic)

    class Readline:
        @staticmethod
        def get_current_history_length():
            return 2

        @staticmethod
        def get_history_item(index):
            return ["first", "second"][index - 1]

    target = tmp_path / ".bago" / "state" / ".bago_history"
    repl_history.save_readline_history(
        Readline(), target, trusted_root=tmp_path, session_id="session-1"
    )

    assert calls == [(target, "first\nsecond\n", {
        "trusted_root": tmp_path,
        "source_surface": "chat.readline_history",
        "session_id": "session-1",
    })]


def test_prompt_history_appends_gateway_owned_filehistory_format(monkeypatch, tmp_path: Path):
    calls = []

    def append_text_durable(path, content, **kwargs):
        calls.append((path, content, kwargs))
        return {"ok": True}

    monkeypatch.setattr("bago_core.server_effects.append_text_durable", append_text_durable)
    history = repl_history.GatewayFileHistory(
        tmp_path / ".bago_prompt_history", trusted_root=tmp_path, session_id="session-2"
    )
    history.store_string("first\nsecond")

    path, content, kwargs = calls[0]
    assert path == tmp_path / ".bago_prompt_history"
    assert content.startswith("\n# ")
    assert content.endswith("\n+first\n+second\n")
    assert kwargs == {
        "trusted_root": tmp_path,
        "source_surface": "chat.prompt_history",
        "session_id": "session-2",
    }


def test_prompt_history_reads_existing_filehistory_format(tmp_path: Path):
    target = tmp_path / "history"
    target.write_bytes(b"\n# prior\n+first\n+second\n")
    history = repl_history.GatewayFileHistory(
        target, trusted_root=tmp_path, session_id="session-3"
    )

    assert list(history.load_history_strings()) == ["first\nsecond"]
