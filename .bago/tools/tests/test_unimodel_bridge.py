"""Pruebas para bago_unimodel_bridge.py — comandos y persistencia."""
import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bago_unimodel_bridge as bridge


def test_load_save_session_data():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        path = f.name
    try:
        data = {
            "provider": "copilot",
            "model_name": "gpt-4o",
            "messages": [
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "adios"},
            ],
            "timeline": [{"ts": "12:00:00", "kind": "test", "title": "evt", "detail": "", "level": "info"}],
            "token_log": {"copilot": {"gpt-4o": {"in": 10, "out": 5, "calls": 1}}},
        }
        bridge._save_session_data(path, data)
        loaded = bridge._load_session_data(path)
        assert loaded["provider"] == "copilot"
        assert len(loaded["messages"]) == 2
        assert len(loaded["timeline"]) == 1
        assert loaded["token_log"]["copilot"]["gpt-4o"]["calls"] == 1
    finally:
        os.unlink(path)


def test_load_legacy_list_format():
    """Debe soportar archivos antiguos que son solo una lista de mensajes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        path = f.name
        json.dump([{"role": "user", "content": "legacy"}], f)
    try:
        loaded = bridge._load_session_data(path)
        assert loaded["messages"][0]["content"] == "legacy"
    finally:
        os.unlink(path)


def test_compact_history():
    from bago.session import BagoSession
    from bago import CredentialManager
    creds = CredentialManager()
    session = BagoSession("copilot", "gpt-4o", "gpt-4o", creds)
    # Add 20 user+assistant pairs
    for i in range(20):
        session.history.append({"role": "user", "content": f"msg{i}"})
        session.history.append({"role": "assistant", "content": f"reply{i}"})
    total = len(session.history)
    removed = bridge._compact_history(session, keep_last=4)
    assert removed == total - 5  # system + 4 kept = 5
    assert len(session.history) == 5
    assert session.history[0]["role"] == "system"
    assert session.history[-1]["content"] == "reply19"


def test_format_status_includes_tokens():
    from bago.session import BagoSession
    from bago import CredentialManager
    creds = CredentialManager()
    session = BagoSession("copilot", "gpt-4o", "gpt-4o", creds)
    session.record_tokens("copilot", "gpt-4o", 100, 50)
    text = bridge._format_status(session)
    assert "copilot" in text
    assert "gpt-4o" in text
    assert "100" in text
    assert "50" in text


def test_format_timeline():
    from bago.session import BagoSession
    from bago import CredentialManager
    creds = CredentialManager()
    session = BagoSession("copilot", "gpt-4o", "gpt-4o", creds)
    session.add_timeline("test", "evt1", "detail1")
    session.add_timeline("test", "evt2", "detail2")
    text = bridge._format_timeline(session, limit=5)
    assert "Timeline" in text
    assert "EVT1" in text.upper() or "evt1" in text


def test_help_output_contains_all_commands():
    text = bridge._print_help()
    assert "SWITCH" in text
    assert "CLEAR" in text
    assert "SAVE" in text
    assert "COMPACT" in text
    assert "STATUS" in text
    assert "TIMELINE" in text
    assert "MODELS" in text
    assert "NEW" in text
    assert "DB-STATUS" in text
    assert "DB-LIST" in text
    assert "DB-COMPACT" in text
    assert "DB-CLEAR" in text
    assert "DB-EXPORT" in text
    assert "HELP" in text
    assert "EXIT" in text
