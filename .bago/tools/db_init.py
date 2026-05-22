#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago db — Gestión de la base de datos SQLite de BAGO.

Uso:
  python bago db init          # Crear/verificar BD y hacer seed de ideas
  python bago db status        # Mostrar resumen de tablas
  python bago db ideas         # Listar ideas almacenadas
  python bago db ideas --add   # Añadir una idea interactivamente
  python bago db reset-ideas   # Repoblar ideas desde el catálogo (no borra ideas de usuario)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / ".bago" / "state" / "bago.db"
CATALOG_PATH = ROOT / ".bago" / "ideas_catalog.json"


# ── Conexión ────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ──────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id          TEXT PRIMARY KEY,
    slot        INTEGER,
    generation  INTEGER DEFAULT 1,
    priority    INTEGER DEFAULT 50,
    section     TEXT    DEFAULT 'contextuales',
    risk        TEXT    DEFAULT 'low',
    title       TEXT    NOT NULL,
    summary     TEXT    DEFAULT '',
    metric      TEXT    DEFAULT '',
    w2          TEXT    DEFAULT '',
    detail      TEXT    DEFAULT '[]',
    requires    TEXT    DEFAULT '[]',
    blocks      TEXT    DEFAULT '[]',
    extra_cond  TEXT    DEFAULT 'always',
    source      TEXT    DEFAULT 'catalog',
    created_at  TEXT    DEFAULT (datetime('now')),
    updated_at  TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    objective   TEXT,
    workflow    TEXT,
    status      TEXT    DEFAULT 'open',
    opened_at   TEXT    DEFAULT (datetime('now')),
    closed_at   TEXT,
    notes       TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS changes (
    id          TEXT PRIMARY KEY,
    session_id  TEXT    REFERENCES sessions(id),
    type        TEXT    DEFAULT 'CHG',
    title       TEXT,
    files       TEXT    DEFAULT '[]',
    summary     TEXT    DEFAULT '',
    evidences   TEXT    DEFAULT '[]',
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS implemented_ideas (
    id          TEXT PRIMARY KEY,
    idea_id     TEXT,
    idea_title  TEXT,
    session_id  TEXT,
    implemented_at TEXT
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# ── Seed desde catálogo ──────────────────────────────────────────────────────

# Mapeo: condiciones legibles → campos requires/blocks/extra_cond
_SLOT_CONDITIONS = {
    ("1", 1): {"requires": [],        "blocks": ["handoff_w2"],   "extra_cond": "always"},
    ("1", 2): {"requires": ["handoff_w2"], "blocks": ["session_opener"], "extra_cond": "always"},
    ("1", 3): {"requires": ["handoff_w2", "session_opener"], "blocks": [], "extra_cond": "always"},
    ("2", 1): {"requires": [],        "blocks": ["stability_cmd"], "extra_cond": "always"},
    ("2", 2): {"requires": ["stability_cmd"], "blocks": ["banner_shows_task"], "extra_cond": "always"},
    ("2", 3): {"requires": ["stability_cmd", "banner_shows_task"], "blocks": [], "extra_cond": "always"},
    ("3", 1): {"requires": [],        "blocks": ["gate_in_code"],  "extra_cond": "stable_reports"},
    ("3", 2): {"requires": ["gate_in_code"], "blocks": ["impl_registry"], "extra_cond": "always"},
    ("3", 3): {"requires": ["impl_registry"], "blocks": [],         "extra_cond": "always"},
    ("4", 1): {"requires": [],        "blocks": [],                "extra_cond": "matrix_pass"},
    ("5", 1): {"requires": [],        "blocks": [],                "extra_cond": "baseline_clean"},
    ("6", 1): {"requires": [],        "blocks": [],                "extra_cond": "has_session_close"},
    ("7", 1): {"requires": [],        "blocks": [],                "extra_cond": "has_readme"},
    ("8", 1): {"requires": [],        "blocks": [],                "extra_cond": "always"},
    # Slot 9: Progreso visible
    ("9", 1): {"requires": ["impl_registry"], "blocks": ["progress_in_banner"], "extra_cond": "always"},
    ("9", 2): {"requires": ["progress_in_banner"], "blocks": [],   "extra_cond": "always"},
    # Slot 10: Sesiones reales
    ("10", 1): {"requires": [],       "blocks": ["session_closes_counted"], "extra_cond": "has_session_close"},
    ("10", 2): {"requires": ["session_closes_counted"], "blocks": ["health_score_real"], "extra_cond": "always"},
    # Slot 11: Cosecha post-tarea
    ("11", 1): {"requires": ["handoff_w2"], "blocks": ["cosecha_post_task"], "extra_cond": "always"},
    ("11", 2): {"requires": ["cosecha_post_task", "impl_registry"], "blocks": [], "extra_cond": "always"},
    # Slot 12: Guía de renovación + autorenovación
    ("12", 1): {"requires": ["impl_registry"],                              "blocks": ["catalog_exhaustion_handled"], "extra_cond": "always"},
    ("12", 2): {"requires": ["catalog_exhaustion_handled", "impl_registry"],"blocks": ["auto_renew_active"],          "extra_cond": "always"},
    # Slot 13: Dashboard con ideas
    ("13", 1): {"requires": ["progress_in_banner"],                         "blocks": ["dashboard_shows_ideas"],      "extra_cond": "always"},
    ("13", 2): {"requires": ["dashboard_shows_ideas"],                      "blocks": ["ideas_history_in_dashboard"], "extra_cond": "always"},
    # Slot 14: Resumen automático de sprint
    ("14", 1): {"requires": ["impl_registry", "cosecha_post_task"],         "blocks": ["sprint_summary_auto"],        "extra_cond": "always"},
    # Slot 15: Ideas personalizadas
    ("15", 1): {"requires": ["impl_registry"],                              "blocks": ["custom_ideas_cli"],           "extra_cond": "always"},
    # Slot 16: Health score real
    ("16", 1): {"requires": ["session_closes_counted"],                     "blocks": ["health_score_real"],          "extra_cond": "always"},
    # Slot 17: Sprint velocity
    ("17", 1): {"requires": ["sprint_summary_auto"],                        "blocks": ["sprint_velocity"],            "extra_cond": "always"},
    # Slot 18: Health en banner
    ("18", 1): {"requires": ["health_score_real", "progress_in_banner"],    "blocks": ["health_in_banner"],           "extra_cond": "always"},
    # Slot 19: Health score en cosecha
    ("19", 1): {"requires": ["cosecha_sprint_ideas", "health_score_real"],  "blocks": ["cosecha_health_compare"],     "extra_cond": "always"},
    # Slot 20: Export ideas
    ("20", 1): {"requires": ["impl_registry", "sprint_summary_auto"],       "blocks": ["ideas_exportable"],           "extra_cond": "always"},
    # Slot 21: Guía de catálogo
    ("21", 1): {"requires": ["impl_registry"],                              "blocks": ["catalog_guide_added"],        "extra_cond": "always"},
    # Wave 4 — slots 22-26
    ("22", 1): {"requires": ["sprint_velocity"],                            "blocks": ["velocity_in_dashboard"],      "extra_cond": "always"},
    ("23", 1): {"requires": ["cosecha_health_compare"],                     "blocks": ["cosecha_health_trend"],       "extra_cond": "always"},
    ("24", 1): {"requires": ["health_in_banner", "sprint_velocity"],        "blocks": ["full_sprint_in_stability"],   "extra_cond": "always"},
    ("25", 1): {"requires": ["health_in_banner"],                           "blocks": ["banner_compact_mode"],        "extra_cond": "always"},
    ("26", 1): {"requires": ["ideas_exportable"],                           "blocks": ["dashboard_export_link"],      "extra_cond": "always"},
}


def seed_from_catalog(conn: sqlite3.Connection, overwrite: bool = False) -> int:
    """Inserta ideas del catálogo en la BD. Devuelve número de ideas insertadas."""
    if not CATALOG_PATH.exists():
        print(f"  ⚠  Catálogo no encontrado: {CATALOG_PATH}")
        return 0

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    inserted = 0

    # Fallback ideas
    for entry in catalog.get("fallback", []):
        _upsert_idea(conn, entry, slot=None, generation=0, source="catalog",
                     requires=[], blocks=[], extra_cond="always", overwrite=overwrite)
        inserted += 1

    # Slot ideas
    for slot_key, slot_data in catalog.get("slots", {}).items():
        for gen_entry in slot_data.get("generations", []):
            gen = int(gen_entry.get("generation", 1))
            cond = _SLOT_CONDITIONS.get((slot_key, gen), {})
            _upsert_idea(
                conn, gen_entry,
                slot=int(slot_key),
                generation=gen,
                source="catalog",
                requires=cond.get("requires", []),
                blocks=cond.get("blocks", []),
                extra_cond=cond.get("extra_cond", "always"),
                overwrite=overwrite,
            )
            inserted += 1

    conn.commit()
    return inserted


def _upsert_idea(conn: sqlite3.Connection, entry: dict, *,
                 slot, generation, source, requires, blocks, extra_cond,
                 overwrite: bool) -> None:
    idea_id = str(entry.get("id", entry.get("title", "").lower().replace(" ", "_")))
    now = datetime.now(timezone.utc).isoformat()

    if overwrite:
        conn.execute("""
            INSERT OR REPLACE INTO ideas
              (id, slot, generation, priority, section, risk, title, summary,
               metric, w2, detail, requires, blocks, extra_cond, source, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            idea_id, slot, generation,
            int(entry.get("priority", 50)),
            entry.get("section", "contextuales"),
            entry.get("risk", "low"),
            entry["title"],
            entry.get("summary", ""),
            entry.get("metric", ""),
            entry.get("w2", ""),
            json.dumps(entry.get("detail", []), ensure_ascii=False),
            json.dumps(requires, ensure_ascii=False),
            json.dumps(blocks, ensure_ascii=False),
            extra_cond, source, now, now,
        ))
    else:
        conn.execute("""
            INSERT OR IGNORE INTO ideas
              (id, slot, generation, priority, section, risk, title, summary,
               metric, w2, detail, requires, blocks, extra_cond, source, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            idea_id, slot, generation,
            int(entry.get("priority", 50)),
            entry.get("section", "contextuales"),
            entry.get("risk", "low"),
            entry["title"],
            entry.get("summary", ""),
            entry.get("metric", ""),
            entry.get("w2", ""),
            json.dumps(entry.get("detail", []), ensure_ascii=False),
            json.dumps(requires, ensure_ascii=False),
            json.dumps(blocks, ensure_ascii=False),
            extra_cond, source, now, now,
        ))


# ── Queries de ideas ─────────────────────────────────────────────────────────

def load_ideas_for_context(conn: sqlite3.Connection, feat: dict,
                            extra_flags: dict) -> list[dict]:
    """
    Carga ideas de la BD aplicando lógica de slots y condiciones.
    Devuelve lista de ideas ordenadas por prioridad desc.
    """
    rows = conn.execute(
        "SELECT * FROM ideas ORDER BY slot NULLS LAST, generation DESC, priority DESC"
    ).fetchall()

    selected: dict[str | None, dict] = {}  # slot → idea ganadora

    for row in rows:
        idea = dict(row)
        slot = idea["slot"]  # None para ideas sin slot
        gen = idea["generation"]
        requires = json.loads(idea["requires"] or "[]")
        blocks = json.loads(idea["blocks"] or "[]")
        extra_cond = idea["extra_cond"]

        # Evaluar condiciones de features
        if not all(feat.get(r) for r in requires):
            continue
        if any(feat.get(b) for b in blocks):
            continue

        # Evaluar condición extra
        if extra_cond != "always":
            if not extra_flags.get(extra_cond, False):
                continue

        if slot is None:
            # Ideas sin slot: siempre incluir si pasan condiciones
            selected[f"_noslot_{idea['id']}"] = idea
        else:
            # Por slot: gana la de mayor generación que pasa condiciones
            key = str(slot)
            if key not in selected:
                selected[key] = idea

    ideas = list(selected.values())
    ideas.sort(key=lambda x: (-x["priority"], x["title"]))
    return ideas


def add_user_idea(conn: sqlite3.Connection, title: str, summary: str,
                  priority: int, metric: str, w2: str,
                  risk: str = "low") -> str:
    """Inserta una idea definida por el usuario. Devuelve el id generado."""
    idea_id = "user_" + title.lower().replace(" ", "_")[:40]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO ideas
          (id, slot, generation, priority, section, risk, title, summary,
           metric, w2, detail, requires, blocks, extra_cond, source, created_at, updated_at)
        VALUES (?,NULL,1,?,?,?,?,?,?,?,'[]','[]','[]','always','user',?,?)
    """, (idea_id, priority, "contextuales", risk, title, summary, metric, w2, now, now))
    conn.commit()
    return idea_id


# ── CLI ──────────────────────────────────────────────────────────────────────

def cmd_init(args: list[str]) -> int:
    print("BAGO db init")
    print("=" * 40)
    conn = get_conn()
    init_schema(conn)
    print("  ✅ Schema creado/verificado")

    n = seed_from_catalog(conn, overwrite=False)
    print(f"  ✅ {n} ideas seed insertadas (INSERT OR IGNORE)")
    print(f"  📁 BD en: {DB_PATH.relative_to(ROOT)}")

    _print_status(conn)
    return 0


def cmd_status(args: list[str]) -> int:
    if not DB_PATH.exists():
        print("BD no inicializada. Ejecuta: python bago db init")
        return 1
    conn = get_conn()
    _print_status(conn)
    return 0


def _print_status(conn: sqlite3.Connection) -> None:
    tables = ["ideas", "sessions", "changes", "implemented_ideas"]
    print("")
    print("Tablas:")
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:25s} {count:4d} filas")
        except Exception:
            print(f"  {t:25s}  —")
    print(f"\n  Ruta: {DB_PATH}")


def cmd_ideas(args: list[str]) -> int:
    if not DB_PATH.exists():
        print("BD no inicializada. Ejecuta: python bago db init")
        return 1
    conn = get_conn()

    if "--add" in args:
        return _add_idea_interactive(conn)

    rows = conn.execute(
        "SELECT id, slot, generation, priority, section, title, source FROM ideas ORDER BY priority DESC"
    ).fetchall()
    print(f"Ideas en BD: {len(rows)}")
    print("")
    for r in rows:
        slot_str = f"slot={r['slot']} gen={r['generation']}" if r['slot'] else "sin-slot"
        print(f"  [{r['priority']:3d}] {r['title']:<45s}  ({slot_str}, {r['source']})")
    print("")
    print("Para añadir una idea: python bago db ideas --add")
    return 0


def _add_idea_interactive(conn: sqlite3.Connection) -> int:
    print("Nueva idea BAGO (Ctrl+C para cancelar)")
    print("-" * 40)
    try:
        title    = input("Título:    ").strip()
        summary  = input("Resumen:   ").strip()
        metric   = input("Métrica:   ").strip()
        w2       = input("Siguiente paso: ").strip()
        priority = int(input("Prioridad (0-100) [50]: ").strip() or "50")
        risk     = input("Riesgo (low/medium/high) [low]: ").strip() or "low"
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 0

    if not title:
        print("El título es obligatorio.")
        return 1

    idea_id = add_user_idea(conn, title, summary, priority, metric, w2, risk)
    print(f"\n✅ Idea añadida con id: {idea_id}")
    print("   Ejecuta 'python bago ideas' para verla en el selector.")
    return 0


def cmd_reset_ideas(args: list[str]) -> int:
    if not DB_PATH.exists():
        print("BD no inicializada. Ejecuta: python bago db init")
        return 1
    conn = get_conn()
    # Solo resetear ideas del catálogo, preservar las de usuario
    conn.execute("DELETE FROM ideas WHERE source = 'catalog'")
    conn.commit()
    n = seed_from_catalog(conn, overwrite=False)
    print(f"✅ {n} ideas del catálogo repobladas. Ideas de usuario preservadas.")
    return 0


COMMANDS: dict[str, tuple] = {
    "init":        (cmd_init,        "Crear/verificar BD y hacer seed de ideas"),
    "status":      (cmd_status,      "Mostrar resumen de tablas"),
    "ideas":       (cmd_ideas,       "Listar ideas almacenadas (--add para crear)"),
    "reset-ideas": (cmd_reset_ideas, "Repoblar ideas del catálogo (preserva ideas de usuario)"),
}


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print("Uso: python bago db <comando> [opciones]")
        print("")
        for cmd, (_, desc) in COMMANDS.items():
            print(f"  {cmd:<15s} {desc}")
        return 0

    subcmd = args[0]
    if subcmd not in COMMANDS:
        print(f"Comando desconocido: {subcmd}")
        print(f"Comandos disponibles: {', '.join(COMMANDS)}")
        return 1

    fn, _ = COMMANDS[subcmd]
    return fn(args[1:])


if __name__ == "__main__":
    raise SystemExit(main())
