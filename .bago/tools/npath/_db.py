"""npath._db — Schema, connection, paths, colors, init helpers."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────

TOOLS_DIR = Path(__file__).resolve().parent.parent   # .bago/tools/
BAGO_ROOT = TOOLS_DIR.parent                         # .bago/
STATE_DIR = BAGO_ROOT / "state"
DB_PATH   = STATE_DIR / "npath.db"

# Windows UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# ── Colors ─────────────────────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty()

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t

BOLD   = lambda t: _c("1", t)        # noqa: E731
GREEN  = lambda t: _c("1;32", t)     # noqa: E731
CYAN   = lambda t: _c("1;36", t)     # noqa: E731
YELLOW = lambda t: _c("1;33", t)     # noqa: E731
RED    = lambda t: _c("1;31", t)     # noqa: E731
DIM    = lambda t: _c("2", t)        # noqa: E731
BLUE   = lambda t: _c("1;34", t)     # noqa: E731

# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    branch      TEXT NOT NULL,
    content     TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'concept',
    weight      REAL NOT NULL DEFAULT 0.5,
    active      INTEGER NOT NULL DEFAULT 1,
    deleted     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    from_id     TEXT NOT NULL,
    to_id       TEXT NOT NULL,
    relation    TEXT NOT NULL DEFAULT 'follows',
    weight      REAL NOT NULL DEFAULT 1.0,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES nodes(id),
    FOREIGN KEY (to_id)   REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS branches (
    name        TEXT PRIMARY KEY,
    head_node   TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    FOREIGN KEY (head_node) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS merges (
    id          TEXT PRIMARY KEY,
    sources     TEXT NOT NULL,
    result_node TEXT NOT NULL,
    strategy    TEXT NOT NULL DEFAULT 'manual',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (result_node) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS splits (
    id           TEXT PRIMARY KEY,
    origin_node  TEXT NOT NULL,
    removed_branch TEXT NOT NULL,
    result_node  TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS npath_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS node_embeddings (
    node_id    TEXT PRIMARY KEY,
    model      TEXT NOT NULL,
    vector     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_branch  ON nodes(branch);
CREATE INDEX IF NOT EXISTS idx_nodes_active  ON nodes(active, deleted);
CREATE INDEX IF NOT EXISTS idx_edges_from    ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to      ON edges(to_id);
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    content, type, branch, metadata,
    content=nodes, content_rowid=rowid
);
"""

FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS nodes_fts_insert AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, content, type, branch, metadata)
    VALUES (new.rowid, new.content, new.type, new.branch, new.metadata);
END;
CREATE TRIGGER IF NOT EXISTS nodes_fts_delete AFTER DELETE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content, type, branch, metadata)
    VALUES ('delete', old.rowid, old.content, old.type, old.branch, old.metadata);
END;
CREATE TRIGGER IF NOT EXISTS nodes_fts_update AFTER UPDATE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content, type, branch, metadata)
    VALUES ('delete', old.rowid, old.content, old.type, old.branch, old.metadata);
    INSERT INTO nodes_fts(rowid, content, type, branch, metadata)
    VALUES (new.rowid, new.content, new.type, new.branch, new.metadata);
END;
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    import npath._db as _self
    _self.STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_self.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Auto-migrate: ensure all tables exist (idempotent via IF NOT EXISTS)
    with conn:
        conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _short_id() -> str:
    return str(uuid.uuid4())[:8]


def _node_id(branch: str, content: str) -> str:
    digest = hashlib.sha1(f"{branch}:{content}:{time.time()}".encode(), usedforsecurity=False).hexdigest()[:8]
    return f"n_{digest}"


def _merge_id() -> str:
    return f"m_{_short_id()}"


def _split_id() -> str:
    return f"s_{_short_id()}"


def _get_current_branch(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM npath_meta WHERE key='current_branch'").fetchone()
    return row["value"] if row else "main"


def _set_current_branch(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO npath_meta (key, value) VALUES ('current_branch', ?)", (name,)
    )


# ── Init ───────────────────────────────────────────────────────────────────────

def cmd_init() -> None:
    """Initialize the npath graph database."""
    import npath._db as _self
    conn = _connect()
    with conn:
        conn.executescript(SCHEMA)
        for stmt in FTS_TRIGGERS.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
        conn.execute(
            "INSERT OR IGNORE INTO branches (name, active, description, created_at) VALUES (?,1,?,?)",
            ("main", "Rama principal del grafo cognitivo", _now()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO npath_meta (key, value) VALUES (?,?)",
            ("current_branch", "main"),
        )
    conn.close()
    print(GREEN("✅ npath inicializado") + f"  →  {_self.DB_PATH}")
    print(f"   Rama activa: {CYAN('main')}")


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
