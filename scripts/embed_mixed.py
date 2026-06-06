#!/usr/bin/env python3
"""
embed_mixed.py — Ingest híbrido: real para `topics` (≤30 docs), determinista para
el resto. Sirve para sellar release 4.1.5 con embeddings parciales sin bloquear
el runtime durante horas.

Uso:
    python scripts\\embed_mixed.py
    python scripts\\embed_mixed.py --real-tables topic
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import datetime as _dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_knowledge as ik  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-bago", default=None)
    parser.add_argument("--source", default=None)
    parser.add_argument("--real-tables", default="topic", help="Tablas a embeber con Ollama (CSV)")
    parser.add_argument("--embed-model", default="llama3.2:3b")
    parser.add_argument("--embed-max-chars", type=int, default=4096)
    args = parser.parse_args(argv)
    user_bago = Path(args.user_bago or str(Path.home() / ".bago"))
    source = Path(args.source) if args.source else (user_bago / "knowledge" / "source")
    if not source.exists():
        print(f"source missing: {source}")
        return 1
    kb_dir = user_bago / "knowledge"
    kb = sqlite3.connect(kb_dir / "knowledge.db")
    emb = sqlite3.connect(kb_dir / "embeddings.db", timeout=30)
    # WAL: writers concurrent-friendly
    emb.execute("PRAGMA journal_mode=WAL")
    emb.execute("PRAGMA synchronous=NORMAL")
    real_tables = [t.strip() for t in args.real_tables.split(",") if t.strip()]
    n_real = 0
    n_fallback = 0
    n_skipped = 0
    for table in ("topic", "project_file", "session_arc", "simulation"):
        prefer = table in real_tables
        rows = kb.execute(f"SELECT id, path FROM {table}").fetchall()
        for rid, rel in rows:
            p = source / rel
            if not p.exists() or not p.is_file():
                n_skipped += 1
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                n_skipped += 1
                continue
            payload = text[: args.embed_max_chars]
            vec: list[float] | None = None
            if prefer:
                vec = ik._ollama_embed(payload, model=args.embed_model)
            if vec is not None:
                n_real += 1
            else:
                vec = ik._deterministic_embedding(payload)
                n_fallback += 1
            emb.execute(
                "INSERT OR REPLACE INTO embedding (id, source, vector, dims, ingested_at) VALUES (?, ?, ?, ?, ?)",
                (f"{table}:{rid}", f"{table}:{rel}", json.dumps(vec), len(vec), _dt.datetime.now(_dt.timezone.utc).isoformat()),
            )
        emb.commit()
    emb.execute(
        "CREATE TABLE IF NOT EXISTS embedding_run (id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT, model TEXT, real_tables TEXT, real_count INTEGER, fallback_count INTEGER, skipped INTEGER)"
    )
    # Migrations defensivas: añadir columnas si la tabla existía de antes sin ellas
    cur_e = emb.execute("PRAGMA table_info(embedding_run)")
    cols = {row[1] for row in cur_e.fetchall()}
    if "real_tables" not in cols:
        try:
            emb.execute("ALTER TABLE embedding_run ADD COLUMN real_tables TEXT")
        except sqlite3.OperationalError:
            pass
    emb.execute(
        "INSERT INTO embedding_run (run_at, model, real_tables, real_count, fallback_count, skipped) VALUES (?, ?, ?, ?, ?, ?)",
        (_dt.datetime.now(_dt.timezone.utc).isoformat(), args.embed_model, ",".join(real_tables), n_real, n_fallback, n_skipped),
    )
    emb.commit()
    emb.close()
    kb.close()
    print(json.dumps({"real": n_real, "fallback": n_fallback, "skipped": n_skipped, "real_tables": real_tables, "model": args.embed_model}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
