"""Shared SQLite schema declarations for the persistent memory stores."""

KNOWLEDGE_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source_session TEXT,
    created_at TEXT NOT NULL,
    deprecated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
"""

KNOWLEDGE_FTS_SCHEMA = "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, source_session)"

EMBEDDING_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT,
    content TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    source_session TEXT,
    provider TEXT,
    model TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_embeddings_memory_id ON embeddings(memory_id);
"""
