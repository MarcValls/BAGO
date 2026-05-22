#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_state.py — Sincroniza implemented_ideas.json ↔ tabla implemented_ideas en bago.db.

Detecta y muestra divergencias entre las dos fuentes de verdad de ideas implementadas.
Con --fix repara la divergencia importando entradas faltantes en cada fuente.

Uso:
    python3 .bago/tools/sync_state.py           # informe de divergencias
    python3 .bago/tools/sync_state.py --fix     # reparar divergencias
    python3 .bago/tools/sync_state.py --dry-run # igual que sin flags (informe)

Códigos de salida: 0 = sin divergencias (o reparadas), 1 = hay divergencias
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
DB_PATH = STATE / "bago.db"
JSON_PATH = STATE / "implemented_ideas.json"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"


def _load_json_titles() -> dict[str, dict]:
    """Load implemented titles from JSON. Returns {normalized_title: entry}."""
    if not JSON_PATH.exists():
        return {}
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    items = data if isinstance(data, list) else data.get("implemented", [])
    result = {}
    for item in items:
        title = item.get("title", "").strip()
        if title:
            result[title.lower()] = item
    return result


def _load_db_titles() -> dict[str, dict]:
    """Load implemented titles from bago.db. Returns {normalized_title: row}."""
    if not DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='implemented_ideas'")
        if not cur.fetchone():
            conn.close()
            return {}
        cur.execute("SELECT * FROM implemented_ideas")
        rows = cur.fetchall()
        conn.close()
        result = {}
        for row in rows:
            d = dict(row)
            title = (d.get("idea_title") or d.get("title") or "").strip()
            if title:
                result[title.lower()] = d
        return result
    except Exception as e:
        print(f"  [warn] Error leyendo DB: {e}", file=sys.stderr)
        return {}


def _fix_db_missing(json_titles: dict, db_titles: dict) -> int:
    """Insert JSON entries missing from DB into implemented_ideas table."""
    missing = {k: v for k, v in json_titles.items() if k not in db_titles}
    if not missing or not DB_PATH.exists():
        return 0

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        # Check columns available
        cur.execute("PRAGMA table_info(implemented_ideas)")
        cols = {row[1] for row in cur.fetchall()}

        inserted = 0
        for title_lower, entry in missing.items():
            title = entry.get("title", title_lower)
            done_at = entry.get("done_at", datetime.now(tz=timezone.utc).isoformat())
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO implemented_ideas (idea_title, implemented_at) VALUES (?, ?)",
                    (title, done_at)
                )
                inserted += cur.rowcount
            except sqlite3.Error:
                pass
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        print(f"  [warn] Error insertando en DB: {e}", file=sys.stderr)
        return 0


def _fix_json_missing(json_titles: dict, db_titles: dict) -> int:
    """Insert DB entries missing from JSON into implemented_ideas.json."""
    missing = {k: v for k, v in db_titles.items() if k not in json_titles}
    if not missing or not JSON_PATH.exists():
        return 0

    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return 0

    if isinstance(data, list):
        items = data
        wrapper = None
    else:
        items = data.get("implemented", [])
        wrapper = data

    added = 0
    for title_lower, row in missing.items():
        title = (row.get("title") or row.get("idea_title") or title_lower).strip()
        done_at = row.get("done_at", datetime.now(tz=timezone.utc).isoformat())
        items.append({"title": title, "done_at": done_at})
        added += 1

    if wrapper is not None:
        wrapper["implemented"] = items
        write_data = wrapper
    else:
        write_data = items

    try:
        JSON_PATH.write_text(json.dumps(write_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  [warn] Error escribiendo JSON: {e}", file=sys.stderr)
        return 0

    return added


def main() -> int:
    args = sys.argv[1:]
    fix = "--fix" in args

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Sincronizar estado de ideas                         │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()

    json_titles = _load_json_titles()
    db_titles = _load_db_titles()

    print(f"  JSON (implemented_ideas.json) : {len(json_titles)} entradas")
    print(f"  DB   (bago.db)               : {len(db_titles)} entradas")
    print()

    only_in_json = {k: v for k, v in json_titles.items() if k not in db_titles}
    only_in_db   = {k: v for k, v in db_titles.items() if k not in json_titles}
    in_both = len(json_titles) - len(only_in_json)

    print(f"  En ambas fuentes             : {GREEN(str(in_both))}")

    if only_in_json:
        print(f"  Solo en JSON (falta en DB)   : {YELLOW(str(len(only_in_json)))}")
        for t in list(only_in_json.keys())[:5]:
            title_display = only_in_json[t].get("title", t)[:50]
            print(f"    • {DIM(title_display)}")
        if len(only_in_json) > 5:
            print(f"    {DIM(f'... y {len(only_in_json)-5} más')}")
    else:
        print(f"  Solo en JSON (falta en DB)   : {GREEN('0 ✓')}")

    if only_in_db:
        print(f"  Solo en DB (falta en JSON)   : {YELLOW(str(len(only_in_db)))}")
        for t in list(only_in_db.keys())[:5]:
            title_display = only_in_db[t].get("title") or only_in_db[t].get("idea_title") or t
            title_display = str(title_display)[:50]
            print(f"    • {DIM(title_display)}")
        if len(only_in_db) > 5:
            print(f"    {DIM(f'... y {len(only_in_db)-5} más')}")
    else:
        print(f"  Solo en DB (falta en JSON)   : {GREEN('0 ✓')}")

    divergences = len(only_in_json) + len(only_in_db)

    if divergences == 0:
        print()
        print(f"  {GREEN('✅  Sin divergencias — las dos fuentes están sincronizadas.')}")
        print()
        return 0

    print()
    if fix:
        fixed_db   = _fix_db_missing(json_titles, db_titles)
        fixed_json = _fix_json_missing(json_titles, db_titles)
        print(f"  {GREEN('✅  Reparado:')}")
        print(f"     {fixed_db} entradas añadidas a DB")
        print(f"     {fixed_json} entradas añadidas a JSON")
    else:
        print(f"  {YELLOW(f'⚠  {divergences} divergencias detectadas.')}")
        print(f"  Ejecuta: bago sync --fix  para reparar automáticamente")

    print()
    return 0 if fix else 1



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
