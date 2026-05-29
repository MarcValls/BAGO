"""Pruebas para timeline_db.py — SQLite timeline manager."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from timeline_db import TimelineDB


def test_create_and_get_session():
    with tempfile.TemporaryDirectory() as td:
        db = TimelineDB(db_path=os.path.join(td, "test.db"))
        sid = db.create_session("test-session", provider="copilot", model="gpt-4o")
        assert len(sid) > 0
        sess = db.get_session(sid)
        assert sess is not None
        assert sess["name"] == "test-session"
        assert sess["provider"] == "copilot"
        db.close()


def test_log_and_get_events():
    with tempfile.TemporaryDirectory() as td:
        db = TimelineDB(db_path=os.path.join(td, "test.db"))
        sid = db.create_session("evt-test")
        db.log_event(sid, "chat", "msg1", "hola", level="user")
        db.log_event(sid, "chat", "msg2", "adios", level="assistant")
        evts = db.get_events(sid, limit=10)
        assert len(evts) == 2
        assert evts[0]["title"] == "msg2"  # DESC order
        db.close()


def test_timeline_view_format():
    with tempfile.TemporaryDirectory() as td:
        db = TimelineDB(db_path=os.path.join(td, "test.db"))
        sid = db.create_session("view-test")
        db.log_event(sid, "test", "evt1", "detail1")
        lines = db.get_timeline_view(sid, limit=5)
        assert len(lines) == 1
        assert "EVT1" in lines[0].upper()
        db.close()


def test_compact_session():
    with tempfile.TemporaryDirectory() as td:
        db = TimelineDB(db_path=os.path.join(td, "test.db"))
        sid = db.create_session("compact-test")
        for i in range(20):
            db.log_event(sid, "chat", f"msg{i}", "")
        removed = db.compact_session(sid, keep_last=5)
        assert removed == 15
        count = db.event_count(sid)
        assert count == 5
        db.close()


def test_export_import():
    with tempfile.TemporaryDirectory() as td:
        db = TimelineDB(db_path=os.path.join(td, "test.db"))
        sid = db.create_session("export-test", provider="ollama", model="qwen")
        db.log_event(sid, "system", "start", "ok")
        out_path = os.path.join(td, "exported.json")
        db.export_session(sid, out_path)
        assert os.path.exists(out_path)
        # Import into fresh db
        db2 = TimelineDB(db_path=os.path.join(td, "test2.db"))
        sid2 = db2.import_session(out_path)
        sess = db2.get_session(sid2)
        assert sess["provider"] == "ollama"
        assert db2.event_count(sid2) == 1
        db.close()
        db2.close()


def test_stats():
    with tempfile.TemporaryDirectory() as td:
        db = TimelineDB(db_path=os.path.join(td, "test.db"))
        sid = db.create_session("stats-test")
        db.log_event(sid, "a", "b")
        stats = db.stats()
        assert stats["sessions"] == 1
        assert stats["events"] == 1
        db.close()
