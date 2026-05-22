#!/usr/bin/env python3
"""pack_cache_db.py — Cache híbrida de .bago/pack.json en SQLite.

Objetivo:
- Mantener .bago/pack.json como fuente canónica (Git-friendly).
- Crear/actualizar una cache read-optimized en .bago/state/bago.db.
- Validar integridad por checksum SHA-256.

Uso:
  python3 .bago/tools/pack_cache_db.py sync     # pack.json -> bago.db (cache)
  python3 .bago/tools/pack_cache_db.py check    # valida checksum cache vs pack
  python3 .bago/tools/pack_cache_db.py status   # estado resumido de cache
  python3 .bago/tools/pack_cache_db.py --test   # autotest mínimo

Comando BAGO:
  bago pack-cache [sync|check|status]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / ".bago" / "pack.json"
STATE_DIR = ROOT / ".bago" / "state"
DB_PATH = STATE_DIR / "bago.db"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_pack() -> tuple[dict, str]:
    if not PACK_PATH.exists():
        raise FileNotFoundError(f"No existe {PACK_PATH}")
    raw = PACK_PATH.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("pack.json debe ser un objeto JSON")
    return data, _sha256_bytes(raw)


def _connect() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pack_cache_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pack_cache_entities (
            entity_type TEXT NOT NULL,
            entity_key  TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(entity_type, entity_key)
        );

        CREATE INDEX IF NOT EXISTS idx_pack_cache_type
            ON pack_cache_entities(entity_type);
        """
    )


def _iter_entities(pack: dict) -> list[tuple[str, str, str]]:
    entities: list[tuple[str, str, str]] = []

    # Snapshot raíz para lecturas rápidas de contrato completo.
    entities.append(("pack", "root", json.dumps(pack, ensure_ascii=False, sort_keys=True)))

    commands = pack.get("commands", {})
    if isinstance(commands, dict):
        for cmd, payload in commands.items():
            entities.append(
                ("command", str(cmd), json.dumps(payload, ensure_ascii=False, sort_keys=True))
            )

    workflows = pack.get("workflows", {})
    if isinstance(workflows, dict):
        for wf, payload in workflows.items():
            entities.append(
                ("workflow", str(wf), json.dumps(payload, ensure_ascii=False, sort_keys=True))
            )
    elif isinstance(workflows, list):
        for i, payload in enumerate(workflows):
            key = str(payload.get("id") if isinstance(payload, dict) else i)
            entities.append(
                ("workflow", key, json.dumps(payload, ensure_ascii=False, sort_keys=True))
            )

    entrypoints = pack.get("entrypoints", {})
    if isinstance(entrypoints, dict):
        for ep, payload in entrypoints.items():
            entities.append(
                ("entrypoint", str(ep), json.dumps(payload, ensure_ascii=False, sort_keys=True))
            )
    elif isinstance(entrypoints, list):
        for i, payload in enumerate(entrypoints):
            key = str(payload.get("name") if isinstance(payload, dict) else i)
            entities.append(
                ("entrypoint", key, json.dumps(payload, ensure_ascii=False, sort_keys=True))
            )

    return entities


def cmd_sync() -> int:
    pack, pack_sha = _load_pack()
    entities = _iter_entities(pack)

    conn = _connect()
    _ensure_schema(conn)
    now = _utc_now()

    with conn:
        conn.execute("DELETE FROM pack_cache_entities")
        conn.executemany(
            """
            INSERT OR REPLACE INTO pack_cache_entities(entity_type, entity_key, payload_json, updated_at)
            VALUES(?,?,?,?)
            """,
            [(t, k, payload, now) for (t, k, payload) in entities],
        )
        conn.execute(
            "INSERT OR REPLACE INTO pack_cache_meta(key, value) VALUES('pack_sha256', ?)",
            (pack_sha,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO pack_cache_meta(key, value) VALUES('pack_path', ?)",
            (str(PACK_PATH),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO pack_cache_meta(key, value) VALUES('synced_at', ?)",
            (now,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO pack_cache_meta(key, value) VALUES('pack_version', ?)",
            (str(pack.get("version", "")),),
        )

    count = conn.execute("SELECT COUNT(*) FROM pack_cache_entities").fetchone()[0]
    conn.close()

    print(f"  ✅ pack-cache sync OK: {count} entidades · sha256={pack_sha[:12]}…")
    return 0


def cmd_check() -> int:
    _, current_sha = _load_pack()
    conn = _connect()
    _ensure_schema(conn)
    row = conn.execute(
        "SELECT value FROM pack_cache_meta WHERE key='pack_sha256'"
    ).fetchone()
    conn.close()

    if not row:
        print("  ❌ pack-cache sin inicializar. Ejecuta: bago pack-cache sync")
        return 1

    cached_sha = row[0]
    if cached_sha == current_sha:
        print(f"  ✅ pack-cache checksum OK ({current_sha[:12]}…)")
        return 0

    print("  ❌ pack-cache desactualizada")
    print(f"     cache : {cached_sha}")
    print(f"     pack  : {current_sha}")
    print("  Sugerido: bago pack-cache sync")
    return 1


def cmd_status() -> int:
    conn = _connect()
    _ensure_schema(conn)

    counts = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT entity_type, COUNT(*) FROM pack_cache_entities GROUP BY entity_type"
        )
    }
    meta = {
        row[0]: row[1]
        for row in conn.execute("SELECT key, value FROM pack_cache_meta")
    }
    conn.close()

    total = sum(counts.values())
    print("  🗄  pack-cache status")
    print(f"     db: {DB_PATH}")
    print(f"     entidades: {total}")
    print(f"     commands: {counts.get('command', 0)}")
    print(f"     workflows: {counts.get('workflow', 0)}")
    print(f"     entrypoints: {counts.get('entrypoint', 0)}")
    print(f"     synced_at: {meta.get('synced_at', '(nunca)')}")
    print(f"     pack_version: {meta.get('pack_version', '(n/a)')}")
    if "pack_sha256" in meta:
        print(f"     checksum: {meta['pack_sha256'][:12]}…")
    return 0


def _self_test() -> int:
    # Test lógico mínimo y rápido para cumplir tool_guardian.
    sample = {"version": "1.0.0", "commands": {"x": {"a": 1}}, "workflows": [], "entrypoints": []}
    entities = _iter_entities(sample)
    kinds = [e[0] for e in entities]
    assert "pack" in kinds
    assert "command" in kinds
    assert _sha256_bytes(b"abc") == hashlib.sha256(b"abc").hexdigest()
    print("  1/1 tests pasaron")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "--test" in args:
        return _self_test()

    parser = argparse.ArgumentParser(description="Pack cache híbrida en SQLite")
    parser.add_argument("action", nargs="?", default="sync", choices=["sync", "check", "status"])
    ns = parser.parse_args(args)

    if ns.action == "sync":
        return cmd_sync()
    if ns.action == "check":
        return cmd_check()
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
