#!/usr/bin/env python3
"""
task_assign.py — Asignación de tareas a agentes BAGO (CAP layer)

Permite asignar ideas/tareas a agentes funcionales o roles,
integrándose con el ShepardCycle del CAP (Continuous Ascent Protocol).

Uso CLI:
  python task_assign.py list-agents          # agentes y roles disponibles
  python task_assign.py assign <id> <agent>  # asigna idea a agente/rol
  python task_assign.py assign <id> <a1> <a2> <a3>  # asigna múltiples voces (≤3)
  python task_assign.py unassign <id>        # elimina asignación
  python task_assign.py show <id>            # muestra asignación de una idea
  python task_assign.py pending              # ideas sin agente asignado
  python task_assign.py assigned             # ideas con agente asignado
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
_HERE      = Path(__file__).resolve().parent
_BAGO      = _HERE.parent
_STATE     = _BAGO / "state"
_DB        = _STATE / "bago.db"
_AGENTS    = _STATE / "agents_registry.json"
_ROLES     = _BAGO / "roles" / "manifest.json"
_LLM_CFG   = _STATE / "llm_config.json"

MAX_VOICES = 3  # ShepardCycle: nunca > 3 voces simultáneas

# ── Colores ────────────────────────────────────────────────────────────────
_TTY = sys.stdout.isatty()
def _c(code: str, t: str) -> str: return f"\033[{code}m{t}\033[0m" if _TTY else t
BOLD   = lambda t: _c("1", t)
GREEN  = lambda t: _c("1;32", t)
YELLOW = lambda t: _c("1;33", t)
CYAN   = lambda t: _c("1;36", t)
RED    = lambda t: _c("1;31", t)
DIM    = lambda t: _c("2", t)
MAGENTA = lambda t: _c("1;35", t)

# ── Iconos por categoría ───────────────────────────────────────────────────
_ROLE_ICON = {
    "gobierno":    "👑",
    "produccion":  "⚙️ ",
    "supervision": "🔍",
    "especialistas":"🎯",
    "tools":       "🔧",
    "tests":       "🧪",
    "docs":        "📝",
    "ops":         "🛠️ ",
}

# ── Helpers ────────────────────────────────────────────────────────────────

def _load_json(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _db() -> sqlite3.Connection:
    if not _DB.exists():
        print(RED(f"✗ bago.db no encontrado: {_DB}"), file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(_DB)


def _safe_migrate(con: sqlite3.Connection) -> None:
    """Añade columnas agent/voices si no existen (idempotente)."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(ideas)").fetchall()]
    for col in ("agent", "voices"):
        if col not in cols:
            con.execute(f"ALTER TABLE ideas ADD COLUMN {col} TEXT DEFAULT NULL")
    con.commit()


# ── Catálogo de agentes disponibles ───────────────────────────────────────

def _available_agents() -> dict[str, dict]:
    """Devuelve dict id→info con todos los agentes funcionales y roles."""
    agents: dict[str, dict] = {}

    # 1. Agentes funcionales (agents_registry.json)
    reg = _load_json(_AGENTS, {})
    for k, v in reg.items():
        if isinstance(v, dict) and k != "_meta":
            agents[k] = {
                "type": "agent",
                "category": v.get("category", ""),
                "description": v.get("description", ""),
                "model": v.get("model", ""),
                "icon": _ROLE_ICON.get(v.get("category", ""), "◈"),
            }

    # 2. Roles de producción y especialistas (manifest.json)
    manifest = _load_json(_ROLES, {})
    for role_id, info in manifest.get("roles", {}).items():
        if not isinstance(info, dict):
            continue
        family = info.get("family", "")
        if family in ("production", "specialist", "produccion", "especialistas"):
            short = info.get("name", role_id).upper()
            desc = info.get("description") or info.get("name", "")
            agents[short] = {
                "type": "role",
                "category": family,
                "description": desc,
                "role_id": role_id,
                "icon": _ROLE_ICON.get(
                    "produccion" if family in ("production", "produccion")
                    else "especialistas", "◈"
                ),
            }

    return agents


# ── Operaciones DB ─────────────────────────────────────────────────────────

def _get_idea(con: sqlite3.Connection, idea_id: str) -> dict | None:
    row = con.execute(
        "SELECT id, title, status, agent, voices, workflow FROM ideas WHERE id = ?",
        (idea_id,)
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "title": row[1], "status": row[2],
        "agent": row[3], "voices": row[4], "workflow": row[5],
    }


def _assign(con: sqlite3.Connection, idea_id: str, agents: list[str]) -> None:
    primary = agents[0]
    voices_str = ",".join(agents) if len(agents) > 1 else None
    con.execute(
        "UPDATE ideas SET agent = ?, voices = ? WHERE id = ?",
        (primary, voices_str, idea_id)
    )
    con.commit()


def _unassign(con: sqlite3.Connection, idea_id: str) -> None:
    con.execute("UPDATE ideas SET agent = NULL, voices = NULL WHERE id = ?", (idea_id,))
    con.commit()


# ── Comandos CLI ───────────────────────────────────────────────────────────

def cmd_list_agents() -> int:
    agents = _available_agents()
    print(BOLD("\n🤖 Agentes y roles disponibles para asignación\n"))

    functional = {k: v for k, v in agents.items() if v["type"] == "agent"}
    roles = {k: v for k, v in agents.items() if v["type"] == "role"}

    if functional:
        print(f"  {CYAN('AGENTES FUNCIONALES')} (agents_registry):")
        for aid, info in sorted(functional.items()):
            model = DIM(f"· {info['model']}") if info.get("model") else ""
            print(f"    {info['icon']} {YELLOW(aid):<20} {info['description'][:50]}  {model}")

    if roles:
        print(f"\n  {CYAN('ROLES DE PRODUCCIÓN')} (roles/manifest):")
        for rid, info in sorted(roles.items()):
            print(f"    {info['icon']} {YELLOW(rid):<20} {info['description'][:50]}")

    print()
    print(DIM(f"  ShepardCycle: máx {MAX_VOICES} voces simultáneas"))
    print()
    return 0


def cmd_assign(idea_id: str, agent_ids: list[str]) -> int:
    if len(agent_ids) > MAX_VOICES:
        print(RED(f"✗ ShepardCycle: máximo {MAX_VOICES} voces simultáneas (recibido: {len(agent_ids)})"))
        return 1

    available = _available_agents()
    # Normalizar a mayúsculas para roles, minúsculas para agents
    resolved: list[str] = []
    for a in agent_ids:
        if a in available:
            resolved.append(a)
        elif a.upper() in available:
            resolved.append(a.upper())
        elif a.lower() in available:
            resolved.append(a.lower())
        else:
            print(RED(f"✗ Agente/rol desconocido: '{a}'"))
            print(DIM(f"  Usa 'task_assign.py list-agents' para ver los disponibles"))
            return 1

    con = _db()
    _safe_migrate(con)
    idea = _get_idea(con, idea_id)
    if not idea:
        print(RED(f"✗ Idea '{idea_id}' no encontrada en bago.db"))
        return 1

    _assign(con, idea_id, resolved)

    label = " + ".join(YELLOW(a) for a in resolved)
    print(GREEN(f"✓ Idea #{idea_id} asignada → {label}"))
    print(DIM(f"  «{idea['title'][:60]}»"))
    if len(resolved) > 1:
        print(DIM(f"  ShepardCycle: {len(resolved)} voces activadas"))
    return 0


def cmd_unassign(idea_id: str) -> int:
    con = _db()
    _safe_migrate(con)
    idea = _get_idea(con, idea_id)
    if not idea:
        print(RED(f"✗ Idea '{idea_id}' no encontrada"))
        return 1
    _unassign(con, idea_id)
    print(GREEN(f"✓ Asignación eliminada de idea #{idea_id}"))
    return 0


def cmd_show(idea_id: str) -> int:
    con = _db()
    _safe_migrate(con)
    idea = _get_idea(con, idea_id)
    if not idea:
        print(RED(f"✗ Idea '{idea_id}' no encontrada"))
        return 1
    print(BOLD(f"\n  Idea #{idea['id']}"))
    print(f"  Título   : {idea['title']}")
    print(f"  Estado   : {idea['status']}")
    print(f"  Workflow : {idea['workflow'] or DIM('(sin asignar)')}")
    print(f"  Agente   : {YELLOW(idea['agent']) if idea['agent'] else DIM('(sin asignar)')}")
    if idea["voices"]:
        voices = idea["voices"].split(",")
        print(f"  Voces CAP: {' + '.join(YELLOW(v) for v in voices)}")
    print()
    return 0


def cmd_pending() -> int:
    con = _db()
    _safe_migrate(con)
    rows = con.execute(
        "SELECT id, title, priority, status FROM ideas WHERE agent IS NULL AND status = 'available' ORDER BY priority DESC LIMIT 20"
    ).fetchall()
    if not rows:
        print(GREEN("✓ Todas las ideas disponibles tienen agente asignado."))
        return 0
    print(BOLD(f"\n📋 Ideas sin agente asignado ({len(rows)})\n"))
    for r in rows:
        print(f"  {DIM(str(r[0])):<30} [{r[2]:>3}] {r[1][:55]}")
    print()
    print(DIM(f"  Asignar: python task_assign.py assign <id> <agente>"))
    print()
    return 0


def cmd_assigned() -> int:
    con = _db()
    _safe_migrate(con)
    rows = con.execute(
        "SELECT id, title, agent, voices, status FROM ideas WHERE agent IS NOT NULL ORDER BY priority DESC LIMIT 20"
    ).fetchall()
    if not rows:
        print(YELLOW("No hay ideas con agente asignado todavía."))
        return 0
    print(BOLD(f"\n✅ Ideas con agente asignado ({len(rows)})\n"))
    for r in rows:
        voices = f" {DIM('+')} {r[3]}" if r[3] else ""
        print(f"  {DIM(str(r[0])):<30} {YELLOW(r[2])}{voices}  {r[1][:40]}")
    print()
    return 0


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd = args[0]

    if cmd == "list-agents":
        return cmd_list_agents()
    elif cmd == "assign":
        if len(args) < 3:
            print(RED("✗ Uso: assign <idea_id> <agente> [agente2] [agente3]"))
            return 1
        return cmd_assign(args[1], args[2:])
    elif cmd == "unassign":
        if len(args) < 2:
            print(RED("✗ Uso: unassign <idea_id>"))
            return 1
        return cmd_unassign(args[1])
    elif cmd == "show":
        if len(args) < 2:
            print(RED("✗ Uso: show <idea_id>"))
            return 1
        return cmd_show(args[1])
    elif cmd == "pending":
        return cmd_pending()
    elif cmd == "assigned":
        return cmd_assigned()
    else:
        print(RED(f"✗ Subcomando desconocido: '{cmd}'"))
        print(DIM("  Subcomandos: list-agents | assign | unassign | show | pending | assigned"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
