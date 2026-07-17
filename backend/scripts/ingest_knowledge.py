#!/usr/bin/env python3
"""
ingest_knowledge.py — Población canónica de knowledge.db y embeddings.db desde
MarcValls/bago-knowledge clonado en .gabo/knowledge/source/.

Uso:
    python scripts\\ingest_knowledge.py
    python scripts\\ingest_knowledge.py --source .gabo\\knowledge\\source
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import urllib.error
import urllib.request
import datetime as _dt
from pathlib import Path

from bago_core.user_state_paths import legacy_user_root, state_root


def _user_bago_root() -> Path:
    return state_root().parent


def _user_bago_kb() -> Path:
    return state_root() / "knowledge"


def _ensure_db(path: Path, schema: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.commit()
    return conn


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _deterministic_embedding(text: str, dims: int = 64) -> list[float]:
    """Hashing determinista (signed feature hashing) — fallback si Ollama embeddings
    no están cableados. NO es un embedding semántico, sólo sirve para poblar."""
    out = [0.0] * dims
    for token in text.split():
        h = hashlib.sha256(token.encode("utf-8")).digest()
        idx = h[0] % dims
        sign = 1.0 if (h[1] & 1) else -1.0
        out[idx] += sign
    # L2 normalizar
    norm = sum(x * x for x in out) ** 0.5 or 1.0
    return [x / norm for x in out]


def _ollama_embed(text: str, model: str = "llama3.2:3b", base_url: str = "http://127.0.0.1:11434", timeout: int = 60) -> list[float] | None:
    """Llama al endpoint /api/embed de Ollama; cae a /api/embeddings si el primero
    no responde. Devuelve None si Ollama no está disponible o el modelo no existe,
    para que el llamador use el fallback determinista."""
    payload = json.dumps({"model": model, "input": text}).encode("utf-8")
    for path in ("/api/embed", "/api/embeddings"):
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}{path}",
                data=payload if path == "/api/embed" else json.dumps({"model": model, "prompt": text}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            vec = data.get("embedding") or (data.get("embeddings") or [[]])[0]
            if vec:
                return vec
        except urllib.error.HTTPError as e:
            # 404 en uno: probar el otro; 4xx en ambos: no se puede
            if e.code in (400, 404):
                continue
            return None
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        except Exception:
            return None
    return None


def _truncate(text: str, max_chars: int) -> str:
    return text[:max_chars] if len(text) > max_chars else text


KB_SCHEMA = """
CREATE TABLE IF NOT EXISTS topic (
  id TEXT PRIMARY KEY,
  title TEXT,
  path TEXT,
  status TEXT,
  ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS project_file (
  id TEXT PRIMARY KEY,
  project TEXT,
  path TEXT,
  ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS session_arc (
  id TEXT PRIMARY KEY,
  path TEXT,
  ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS simulation (
  id TEXT PRIMARY KEY,
  path TEXT,
  ingested_at TEXT
);
"""

EMB_SCHEMA = """
CREATE TABLE IF NOT EXISTS embedding (
  id TEXT PRIMARY KEY,
  source TEXT,
  vector BLOB,
  dims INTEGER,
  ingested_at TEXT
);
"""


def _read_manifest(source: Path) -> dict:
    p = source / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ingest_topics(conn: sqlite3.Connection, source: Path, manifest: dict) -> int:
    canonical = (manifest.get("canonical_paths") or {}).get("topics") or "topics"
    topics_dir = source / canonical
    if not topics_dir.exists():
        return 0
    n = 0
    for p in topics_dir.glob("*.md"):
        cid = p.stem
        conn.execute(
            "INSERT OR REPLACE INTO topic (id, title, path, status, ingested_at) VALUES (?, ?, ?, ?, ?)",
            (cid, p.stem.replace("-", " ").title(), str(p.relative_to(source)), "stable", _dt.datetime.now(_dt.timezone.utc).isoformat()),
        )
        n += 1
    return n


def _ingest_projects(conn: sqlite3.Connection, source: Path, manifest: dict) -> int:
    canonical = (manifest.get("canonical_paths") or {}).get("projects") or "projects"
    projects_dir = source / canonical
    if not projects_dir.exists():
        return 0
    n = 0
    for proj in projects_dir.iterdir():
        if not proj.is_dir():
            continue
        for f in proj.rglob("*"):
            if f.is_file():
                cid = f"{proj.name}/{f.relative_to(proj).as_posix()}"
                conn.execute(
                    "INSERT OR REPLACE INTO project_file (id, project, path, ingested_at) VALUES (?, ?, ?, ?)",
                    (cid, proj.name, str(f.relative_to(source)), _dt.datetime.now(_dt.timezone.utc).isoformat()),
                )
                n += 1
    return n


def _ingest_sessions(conn: sqlite3.Connection, source: Path, manifest: dict) -> int:
    canonical = (manifest.get("canonical_paths") or {}).get("sessions") or "sessions"
    sessions_dir = source / canonical
    if not sessions_dir.exists():
        return 0
    n = 0
    for p in sessions_dir.rglob("*"):
        if p.is_file():
            cid = str(p.relative_to(source)).replace("\\", "/")
            conn.execute(
                "INSERT OR REPLACE INTO session_arc (id, path, ingested_at) VALUES (?, ?, ?)",
                (cid, str(p.relative_to(source)), _dt.datetime.now(_dt.timezone.utc).isoformat()),
            )
            n += 1
    return n


def _ingest_simulations(conn: sqlite3.Connection, source: Path, manifest: dict) -> int:
    canonical = (manifest.get("canonical_paths") or {}).get("simulations") or "simulations"
    sim_dir = source / canonical
    if not sim_dir.exists():
        return 0
    n = 0
    for p in sim_dir.rglob("*"):
        if p.is_file():
            cid = str(p.relative_to(source)).replace("\\", "/")
            conn.execute(
                "INSERT OR REPLACE INTO simulation (id, path, ingested_at) VALUES (?, ?, ?)",
                (cid, str(p.relative_to(source)), _dt.datetime.now(_dt.timezone.utc).isoformat()),
            )
            n += 1
    return n


def _populate_embeddings(
    kb: sqlite3.Connection,
    emb: sqlite3.Connection,
    source: Path,
    manifest: dict,
    *,
    embed_model: str = "llama3.2:3b",
    embed_max_chars: int = 4096,
    prefer_real: bool = True,
    progress_every: int = 200,
) -> tuple[int, dict]:
    n_real = 0
    n_fallback = 0
    n_skipped = 0
    cur = kb.cursor()
    total = 0
    for table in ("topic", "project_file", "session_arc", "simulation"):
        total += cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    processed = 0
    for table in ("topic", "project_file", "session_arc", "simulation"):
        rows = cur.execute(f"SELECT id, path FROM {table}").fetchall()
        for rid, rel in rows:
            processed += 1
            p = source / rel
            if not p.exists() or not p.is_file():
                n_skipped += 1
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                n_skipped += 1
                continue
            payload = _truncate(text, embed_max_chars)
            vec: list[float] | None = None
            mode = "deterministic"
            if prefer_real:
                vec = _ollama_embed(payload, model=embed_model)
            if vec is not None:
                n_real += 1
            else:
                vec = _deterministic_embedding(payload)
                n_fallback += 1
            emb.execute(
                "INSERT OR REPLACE INTO embedding (id, source, vector, dims, ingested_at) VALUES (?, ?, ?, ?, ?)",
                (f"{table}:{rid}", f"{table}:{rel}", json.dumps(vec), len(vec), _dt.datetime.now(_dt.timezone.utc).isoformat()),
            )
            if processed % progress_every == 0:
                emb.commit()
                print(f"[embed] {processed}/{total} real={n_real} fallback={n_fallback} skipped={n_skipped}", file=sys.stderr)
    emb.execute(
        "CREATE TABLE IF NOT EXISTS embedding_run (id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT, model TEXT, real_count INTEGER, fallback_count INTEGER, skipped INTEGER)"
    )
    emb.execute(
        "INSERT INTO embedding_run (run_at, model, real_count, fallback_count, skipped) VALUES (?, ?, ?, ?, ?)",
        (_dt.datetime.now(_dt.timezone.utc).isoformat(), embed_model if prefer_real else "(disabled)", n_real, n_fallback, n_skipped),
    )
    return n_real + n_fallback, {"real": n_real, "fallback": n_fallback, "skipped": n_skipped, "model": embed_model if prefer_real else "(deterministic)"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-bago", default=None)
    parser.add_argument("--source", default=None)
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--embed-model", default="llama3.2:3b", help="Modelo Ollama a usar para embeddings (default: llama3.2:3b)")
    parser.add_argument("--deterministic", action="store_true", help="Forzar hashing determinista (no llamar a Ollama)")
    parser.add_argument("--embed-max-chars", type=int, default=4096, help="Truncar texto a N caracteres antes de embed (default: 4096)")
    args = parser.parse_args(argv)
    user_bago = Path(args.user_bago or str(_user_bago_root()))
    source = Path(args.source) if args.source else (user_bago / "knowledge" / "source")
    if not source.exists():
        print(f"source missing: {source}")
        return 1
    manifest = _read_manifest(source)
    if not manifest:
        print("manifest.json missing or invalid; using defaults")

    kb_dir = _user_bago_kb()
    kb_dir.mkdir(parents=True, exist_ok=True)
    kb = _ensure_db(kb_dir / "knowledge.db", KB_SCHEMA)
    emb = _ensure_db(kb_dir / "embeddings.db", EMB_SCHEMA)

    counts = {
        "topic": _ingest_topics(kb, source, manifest),
        "project_file": _ingest_projects(kb, source, manifest),
        "session_arc": _ingest_sessions(kb, source, manifest),
        "simulation": _ingest_simulations(kb, source, manifest),
    }
    kb.commit()
    if not args.skip_embeddings:
        n_emb, emb_stats = _populate_embeddings(
            kb,
            emb,
            source,
            manifest,
            embed_model=args.embed_model,
            embed_max_chars=args.embed_max_chars,
            prefer_real=not args.deterministic,
        )
        counts["embedding"] = n_emb
        counts["embedding_stats"] = emb_stats
        emb.commit()
        kb.commit()
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
