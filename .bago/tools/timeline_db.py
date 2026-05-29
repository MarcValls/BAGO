#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
timeline_db.py — Gestión persistente de timelines para BAGO Dev Twin.

Base de datos SQLite que almacena sesiones y eventos de timeline,
permitiendo consultas, exportación, compactación y gestión desde la interfaz.

Uso:
    from timeline_db import TimelineDB
    db = TimelineDB()
    sid = db.create_session("dev-001", provider="copilot", model="gpt-4o")
    db.log_event(sid, "chat", "user-msg", "hola", level="user")
    rows = db.get_events(sid, limit=10)
    text = db.get_timeline_view(sid, limit=6)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Default location alongside unimodel history
_DEFAULT_DB = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "BAGO" / "timeline.db"


class TimelineDB:
    """SQLite-backed timeline manager for BAGO sessions."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or _DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._ensure_tables()

    # ── Connection-per-thread ───────────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ── Schema ────────────────────────────────────────────────────────────────
    def _ensure_tables(self):
        c = self._conn()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                name        TEXT,
                provider    TEXT,
                model       TEXT,
                created_at  TEXT NOT NULL,
                ended_at    TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                ts         TEXT NOT NULL,
                kind       TEXT NOT NULL,
                title      TEXT NOT NULL,
                detail     TEXT DEFAULT '',
                level      TEXT DEFAULT 'info',
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
            CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);
            """
        )
        c.commit()

    # ── Sessions ─────────────────────────────────────────────────────────────
    def create_session(
        self,
        name: str = "",
        provider: str = "",
        model: str = "",
        sid: str | None = None,
    ) -> str:
        sid = sid or str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        c = self._conn()
        c.execute(
            "INSERT INTO sessions (id, name, provider, model, created_at) VALUES (?, ?, ?, ?, ?)",
            (sid, name or sid, provider, model, now),
        )
        c.commit()
        return sid

    def get_session(self, sid: str) -> dict | None:
        c = self._conn()
        row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 50) -> list[dict]:
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close_session(self, sid: str):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        c = self._conn()
        c.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (now, sid))
        c.commit()

    def delete_session(self, sid: str):
        c = self._conn()
        c.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        c.commit()

    # ── Events ───────────────────────────────────────────────────────────────
    def log_event(
        self,
        sid: str,
        kind: str,
        title: str,
        detail: str = "",
        level: str = "info",
    ) -> int:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        c = self._conn()
        cur = c.execute(
            "INSERT INTO events (session_id, ts, kind, title, detail, level) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, now, kind, title, detail, level),
        )
        c.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_events(
        self,
        sid: str,
        limit: int = 100,
        kind: str | None = None,
        level: str | None = None,
        since: str | None = None,
    ) -> list[dict]:
        c = self._conn()
        sql = "SELECT * FROM events WHERE session_id = ?"
        params: list = [sid]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if level:
            sql += " AND level = ?"
            params.append(level)
        if since:
            sql += " AND ts >= ?"
            params.append(since)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def event_count(self, sid: str) -> int:
        c = self._conn()
        row = c.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?", (sid,)
        ).fetchone()
        return row[0] if row else 0

    def get_timeline_view(self, sid: str, limit: int = 20, width: int = 80) -> list[str]:
        rows = self.get_events(sid, limit=limit)
        rows.reverse()

        def _clip(text: str, max_len: int) -> str:
            text = " ".join(str(text).split())
            if len(text) <= max_len:
                return text
            return text[: max_len - 3].rstrip() + "..."

        lines = []
        for item in rows:
            kind = str(item.get("kind", "event")).upper()
            title = str(item.get("title", "")).strip()
            detail = str(item.get("detail", "")).strip()
            line = f"{item.get('ts', '--:--:--')} [{kind}] {title}"
            if detail:
                line += f" - {detail}"
            lines.append(_clip(line, width))
        return lines or ["(timeline vacía)"]

    # ── Compact / cleanup ─────────────────────────────────────────────────────
    def compact_session(self, sid: str, keep_last: int = 50) -> int:
        c = self._conn()
        row = c.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?", (sid,)
        ).fetchone()
        total = row[0] if row else 0
        if total <= keep_last:
            return 0
        # SQLite doesn't support LIMIT in DELETE directly without subquery
        c.execute(
            """
            DELETE FROM events
            WHERE id IN (
                SELECT id FROM events
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
            )
            """,
            (sid, total - keep_last),
        )
        c.commit()
        return total - keep_last

    def clear_session_events(self, sid: str):
        c = self._conn()
        c.execute("DELETE FROM events WHERE session_id = ?", (sid,))
        c.commit()

    # ── Export / Import ───────────────────────────────────────────────────────
    def export_session(self, sid: str, path: str | Path) -> Path:
        path = Path(path)
        sess = self.get_session(sid)
        events = self.get_events(sid, limit=10_000)
        payload = {
            "session": sess,
            "events": events,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def import_session(self, path: str | Path) -> str:
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        sess = payload["session"]
        sid = self.create_session(
            name=sess.get("name", "imported"),
            provider=sess.get("provider", ""),
            model=sess.get("model", ""),
            sid=sess.get("id"),
        )
        for ev in payload.get("events", []):
            self.log_event(
                sid,
                ev["kind"],
                ev["title"],
                detail=ev.get("detail", ""),
                level=ev.get("level", "info"),
            )
        return sid

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        c = self._conn()
        sess_count = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        evt_count = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {
            "sessions": sess_count,
            "events": evt_count,
            "db_path": str(self.db_path),
            "db_size": self.db_path.stat().st_size if self.db_path.exists() else 0,
        }
