#!/usr/bin/env python3
"""
bago_db.py — Adaptador SQLite central del framework BAGO.

Gestiona bago.db en .bago/state/ con tres tablas:
  - ideas          → catálogo de ideas con estado de runtime
  - guardian_runs  → historial de ejecuciones del guardian
  - implemented    → registro de ideas completadas (semilla de implemented_ideas.json)

Uso directo:
  python3 .bago/tools/bago_db.py init     # crea/resiembra la DB
  python3 .bago/tools/bago_db.py status   # muestra resumen
  python3 .bago/tools/bago_db.py export   # exporta a JSON de backup

Importado por: emit_ideas.py, tool_guardian.py, ideas_selector.py, health_check.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
STATE    = ROOT / ".bago" / "state"
DB_PATH  = STATE / "bago.db"
MAX_GUARDIAN_RUNS = 30


# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=3000;

CREATE TABLE IF NOT EXISTS ideas (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT,
    section     TEXT,
    slot        INTEGER,
    generation  INTEGER DEFAULT 1,
    priority    INTEGER DEFAULT 50,
    risk        TEXT DEFAULT 'low',
    metric      TEXT,
    w2          TEXT,
    requires    TEXT DEFAULT '[]',
    blocks      TEXT DEFAULT '[]',
    extra_cond  TEXT DEFAULT 'always',
    status      TEXT DEFAULT 'available',
    accepted_at TEXT,
    completed_at TEXT,
    session_close TEXT,
    workflow    TEXT
);

CREATE TABLE IF NOT EXISTS guardian_runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT NOT NULL,
    health   REAL NOT NULL,
    ok       INTEGER NOT NULL,
    total    INTEGER NOT NULL,
    errors   INTEGER NOT NULL DEFAULT 0,
    warnings INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_SLOT_MAP = {
    "handoff":       1,
    "stability":     2,
    "gate":          3,
    "entrada_rapida": 4,
    "ranking":       5,
    "standalone":    None,
}


# ── Connection ────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


# ── Init / seed ───────────────────────────────────────────────────────────────

def init_db(force: bool = False) -> str:
    """Crea las tablas si no existen. Siembra desde JSON solo en primera init.

    Returns mensaje de estado.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    conn.executescript(_DDL)

    seeded = conn.execute("SELECT value FROM db_meta WHERE key='seeded'").fetchone()
    if seeded and not force:
        conn.close()
        return "DB ya inicializada (usa force=True para re-sembrar)"

    msgs = []
    msgs.append(_seed_ideas(conn))
    msgs.append(_seed_guardian_history(conn))
    msgs.append(_seed_implemented_ideas(conn))

    conn.execute(
        "INSERT OR REPLACE INTO db_meta(key,value) VALUES('seeded', ?)",
        (datetime.now(timezone.utc).isoformat(),)
    )
    conn.commit()
    conn.close()
    return " | ".join(msgs)


def _seed_ideas(conn: sqlite3.Connection) -> str:
    """Puebla ideas desde ideas_catalog.json. Idempotente: usa INSERT OR IGNORE."""
    catalog_path = STATE / "config" / "ideas_catalog.json"
    if not catalog_path.exists():
        return "ideas_catalog.json no encontrado — skip"

    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"ideas_catalog.json inválido: {e}"

    count = 0
    for idea in catalog.get("ideas", []) + catalog.get("fallback", []):
        idea_id = idea.get("id") or idea.get("title", "").lower().replace(" ", "-")[:40]
        slot    = _SLOT_MAP.get(str(idea.get("chain", "")), None)
        gen     = idea.get("generation", 1)
        if not isinstance(gen, int):
            gen = 1
        excludes = json.dumps(idea.get("excludes", []))  # stored as 'blocks' column

        try:
            conn.execute(
                """INSERT OR IGNORE INTO ideas
                   (id, title, summary, section, slot, generation, priority,
                    risk, metric, w2, requires, blocks, extra_cond, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    idea_id,
                    idea.get("title", ""),
                    idea.get("summary", ""),
                    idea.get("section", ""),
                    slot,
                    gen,
                    int(idea.get("priority", 50)),
                    idea.get("risk", "low"),
                    idea.get("metric", ""),
                    idea.get("w2", ""),
                    json.dumps(idea.get("requires", [])),
                    excludes,
                    "always",
                    "available",
                )
            )
            count += 1
        except Exception:
            pass

    return f"{count} ideas sembradas"


def _seed_guardian_history(conn: sqlite3.Connection) -> str:
    """Importa guardian_history.json si la tabla está vacía."""
    hist_path = STATE / "guardian_history.json"
    if not hist_path.exists():
        return "guardian_history.json no encontrado — skip"

    existing = conn.execute("SELECT COUNT(*) FROM guardian_runs").fetchone()[0]
    if existing > 0:
        return f"guardian_runs ya tiene {existing} filas — skip"

    try:
        history = json.loads(hist_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"guardian_history.json inválido: {e}"

    count = 0
    for entry in history:
        if not isinstance(entry, dict) or "date" not in entry:
            continue
        try:
            conn.execute(
                "INSERT INTO guardian_runs(date,health,ok,total,errors,warnings) VALUES(?,?,?,?,?,?)",
                (
                    str(entry.get("date", "")),
                    float(entry.get("health", 0)),
                    int(entry.get("ok", 0)),
                    int(entry.get("total", 0)),
                    int(entry.get("errors", 0)),
                    int(entry.get("warnings", 0)),
                )
            )
            count += 1
        except Exception:
            pass

    return f"{count} guardian runs importados"


def _seed_implemented_ideas(conn: sqlite3.Connection) -> str:
    """Marca ideas como 'done' en la tabla ideas según implemented_ideas.json."""
    impl_path = STATE / "implemented_ideas.json"
    if not impl_path.exists():
        return "implemented_ideas.json no encontrado — skip"

    try:
        data = json.loads(impl_path.read_text(encoding="utf-8"))
        completed = data.get("ideas_completed", [])
    except Exception as e:
        return f"implemented_ideas.json inválido: {e}"

    count = 0
    for entry in completed:
        idea_id = entry.get("id")
        title   = entry.get("title", "")
        date    = entry.get("date", "")
        sc      = entry.get("session_close", "")
        wf      = entry.get("workflow", "")

        if not title or title == "—":
            continue

        # Mark by id if valid, else mark by title match
        if idea_id and idea_id != "null":
            conn.execute(
                "UPDATE ideas SET status='done', completed_at=?, session_close=?, workflow=? WHERE id=?",
                (date, sc, wf, idea_id)
            )
        conn.execute(
            "UPDATE ideas SET status='done', completed_at=?, session_close=?, workflow=? WHERE LOWER(title)=LOWER(?)",
            (date, sc, wf, title)
        )
        count += 1

    return f"{count} ideas marcadas done desde implemented_ideas.json"


# ── Guardian runs ─────────────────────────────────────────────────────────────

def record_guardian_run(date: str, health: float, ok: int, total: int,
                        errors: int = 0, warnings: int = 0) -> None:
    """Registra una ejecución del guardian en la DB (con trim a MAX_GUARDIAN_RUNS)."""
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO guardian_runs(date,health,ok,total,errors,warnings) VALUES(?,?,?,?,?,?)",
                (date, health, ok, total, errors, warnings)
            )
            # Trim: keep only last MAX_GUARDIAN_RUNS rows
            conn.execute(
                """DELETE FROM guardian_runs WHERE id NOT IN (
                       SELECT id FROM guardian_runs ORDER BY id DESC LIMIT ?
                   )""",
                (MAX_GUARDIAN_RUNS,)
            )
    finally:
        conn.close()


def get_guardian_history(n: int = MAX_GUARDIAN_RUNS) -> list[dict]:
    """Devuelve los últimos n runs del guardian, ordenados de más antiguo a más reciente."""
    if not DB_PATH.exists():
        return []
    conn = _connect()
    rows = conn.execute(
        "SELECT date,health,ok,total,errors,warnings FROM guardian_runs ORDER BY id DESC LIMIT ?",
        (n,)
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


def get_last_guardian_run() -> dict | None:
    """Devuelve el último run del guardian o None."""
    runs = get_guardian_history(1)
    return runs[0] if runs else None


# ── Implemented ideas ─────────────────────────────────────────────────────────

def mark_idea_done(idea_id: str | None, title: str, date: str | None = None,
                   session_close: str = "", workflow: str = "") -> None:
    """Marca una idea como completada en la DB y sincroniza implemented_ideas.json."""
    if date is None:
        date = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        with conn:
            affected = 0
            if idea_id:
                cur = conn.execute(
                    "UPDATE ideas SET status='done', completed_at=?, session_close=?, workflow=? WHERE id=?",
                    (date, session_close, workflow, idea_id)
                )
                affected += cur.rowcount
            if title:
                cur = conn.execute(
                    "UPDATE ideas SET status='done', completed_at=?, session_close=?, workflow=? WHERE LOWER(title)=LOWER(?)",
                    (date, session_close, workflow, title)
                )
                affected += cur.rowcount
            # If not in catalog, insert as standalone completed idea
            if affected == 0 and title:
                eid = idea_id or title.lower().replace(" ", "-")[:40]
                conn.execute(
                    """INSERT OR IGNORE INTO ideas
                       (id, title, status, completed_at, session_close, workflow)
                       VALUES (?,?,?,?,?,?)""",
                    (eid, title, "done", date, session_close, workflow)
                )
        _export_implemented_ideas(conn)
    finally:
        conn.close()


def get_implemented_titles() -> set[str]:
    """Devuelve títulos de ideas con status='done'."""
    if not DB_PATH.exists():
        return _load_implemented_json_titles()
    conn = _connect()
    rows = conn.execute("SELECT title FROM ideas WHERE status='done'").fetchall()
    conn.close()
    return {r["title"] for r in rows}


def get_implemented_ids() -> set[str]:
    """Devuelve IDs de ideas con status='done'."""
    if not DB_PATH.exists():
        return set()
    conn = _connect()
    rows = conn.execute("SELECT id FROM ideas WHERE status='done'").fetchall()
    conn.close()
    return {r["id"] for r in rows}


def _load_implemented_json_titles() -> set[str]:
    """Fallback: lee implemented_ideas.json si la DB no existe."""
    impl_path = STATE / "implemented_ideas.json"
    if not impl_path.exists():
        return set()
    try:
        data = json.loads(impl_path.read_text(encoding="utf-8"))
        return {str(e.get("title", "")) for e in data.get("ideas_completed", [])}
    except Exception:
        return set()


def _export_implemented_ideas(conn: sqlite3.Connection) -> None:
    """Exporta ideas done a implemented_ideas.json (compatibilidad con lectores JSON)."""
    rows = conn.execute(
        "SELECT id, title, completed_at as date, session_close, workflow FROM ideas WHERE status='done' ORDER BY completed_at"
    ).fetchall()
    completed = []
    for r in rows:
        completed.append({
            "id":            r["id"],
            "title":         r["title"],
            "date":          r["date"] or "",
            "session_close": r["session_close"] or "",
            "workflow":      r["workflow"] or "",
            "objetivo":      "",
        })
    data = {
        "ideas_completed": completed,
        "last_updated":    datetime.now(timezone.utc).isoformat(),
        "_note": "Generado por bago_db.py. Fuente primaria: bago.db tabla 'ideas'.",
    }
    try:
        (STATE / "implemented_ideas.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ── Export / status ───────────────────────────────────────────────────────────

def export_all() -> None:
    """Exporta todas las tablas a JSON para inspección humana."""
    if not DB_PATH.exists():
        print("bago.db no existe — ejecuta: bago db init")
        return
    conn = _connect()
    _export_implemented_ideas(conn)
    conn.close()
    print("✅ Exportado: implemented_ideas.json")


def db_status() -> None:
    """Muestra resumen de la DB."""
    if not DB_PATH.exists():
        print("  ⚠️  bago.db no encontrada. Ejecuta: bago db init")
        return

    conn = _connect()
    total_ideas = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
    done_ideas  = conn.execute("SELECT COUNT(*) FROM ideas WHERE status='done'").fetchone()[0]
    avail_ideas = conn.execute("SELECT COUNT(*) FROM ideas WHERE status='available'").fetchone()[0]
    runs        = conn.execute("SELECT COUNT(*) FROM guardian_runs").fetchone()[0]
    last_run    = conn.execute(
        "SELECT health, date FROM guardian_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    seeded      = conn.execute("SELECT value FROM db_meta WHERE key='seeded'").fetchone()
    conn.close()

    size_kb = DB_PATH.stat().st_size // 1024
    print(f"\n  🗄  bago.db  ({size_kb} KB)")
    print(f"  ideas: {total_ideas} total  |  {done_ideas} done  |  {avail_ideas} disponibles")
    print(f"  guardian_runs: {runs} entradas", end="")
    if last_run:
        print(f"  |  último: {last_run['health']}%  ({last_run['date'][:10]})")
    else:
        print()
    if seeded:
        print(f"  sembrado: {seeded['value'][:19]}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _self_test() -> int:
    """Tests básicos de la DB en un archivo temporal."""
    import tempfile
    global DB_PATH, STATE
    orig_db    = DB_PATH
    orig_state = STATE
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "config").mkdir()
        DB_PATH = tmpdir / "bago_test.db"
        STATE   = tmpdir
        # Test init (no JSON sources → seed returns skips)
        msg = init_db()
        assert DB_PATH.exists(), "DB no creada"
        # Test guardian record + trim
        record_guardian_run("2026-01-01T00:00:00Z", 95.0, 100, 105, 0, 5)
        hist = get_guardian_history()
        assert len(hist) == 1, f"esperaba 1 run, got {len(hist)}"
        assert hist[0]["health"] == 95.0
        # Test trim to MAX_GUARDIAN_RUNS
        for i in range(35):
            record_guardian_run(f"2026-01-{i+2:02d}T00:00:00Z", float(i), i, i+1, 0, 0)
        hist = get_guardian_history()
        assert len(hist) == MAX_GUARDIAN_RUNS, f"trim falló: {len(hist)}"
        # Test implemented
        mark_idea_done("test-id", "Test Idea", session_close="SC_001.md", workflow="W2")
        titles = get_implemented_titles()
        assert "Test Idea" in titles, f"títulos: {titles}"
        ids = get_implemented_ids()
        assert "test-id" in ids, f"ids: {ids}"
        print("  ✅ bago_db: todos los tests OK")
    DB_PATH = orig_db
    STATE   = orig_state
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "status"

    if cmd == "init":
        force = "--force" in argv
        print(init_db(force=force))
    elif cmd == "status":
        db_status()
    elif cmd == "export":
        export_all()
    elif cmd == "--test":
        return _self_test()
    else:
        print(f"Uso: bago db {{init|status|export|--test}}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
