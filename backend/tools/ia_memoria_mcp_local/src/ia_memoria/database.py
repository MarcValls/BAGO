from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
 path TEXT PRIMARY KEY, project_id TEXT NOT NULL, scope TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, content_hash TEXT NOT NULL,
 mtime REAL NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
 memory_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, scope TEXT NOT NULL,
 memory_class TEXT NOT NULL, category TEXT NOT NULL, statement TEXT NOT NULL,
 source_reference TEXT NOT NULL, authority_level INTEGER NOT NULL,
 confidence REAL NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, supersedes TEXT, contradicts TEXT, file_path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
 proposal_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, scope TEXT NOT NULL,
 proposed_class TEXT NOT NULL, category TEXT NOT NULL, statement TEXT NOT NULL,
 source_reference TEXT NOT NULL, authority_level INTEGER NOT NULL,
 confidence REAL NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
 resolved_at TEXT, resolved_by TEXT, memory_id TEXT, file_path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
 link_id TEXT PRIMARY KEY, source_project TEXT NOT NULL, target_project TEXT NOT NULL,
 concept TEXT NOT NULL, authority TEXT NOT NULL, conditions TEXT NOT NULL,
 source_reference TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
 file_path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, event_type TEXT NOT NULL,
 summary TEXT NOT NULL, evidence TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_links_projects ON links(source_project, target_project);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id);
"""

class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            try:
                conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(path UNINDEXED,title,body,project_id UNINDEXED,scope UNINDEXED)")
                conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(memory_id UNINDEXED,statement,category,project_id UNINDEXED,scope UNINDEXED)")
                conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('fts5','enabled')")
            except sqlite3.OperationalError:
                conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('fts5','disabled')")
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','1')")

    def fts_enabled(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='fts5'").fetchone()
            return bool(row and row['value'] == 'enabled')
