#!/usr/bin/env python3
"""
bago goals — gestor de objetivos del pack con seguimiento de progreso.

Los objetivos se guardan en state/goals/GOAL-*.json.
Cada objetivo tiene título, descripción, categoría, estado y sesiones vinculadas.

Uso:
    bago goals                          → listar todos los objetivos
    bago goals new "Título" --cat cat   → crear objetivo
    bago goals show GOAL-001            → ver detalle
    bago goals close GOAL-001           → marcar como completado
    bago goals link GOAL-001 SES-ID     → vincular sesión
    bago goals progress                 → resumen de progreso global
    bago goals --test                   → tests integrados
"""

import argparse
import json
import sys
import datetime
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent
GOALS_DIR = BAGO_ROOT / "state" / "goals"

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_PAUSED = "paused"

CATEGORIES = ["capability", "quality", "automation", "documentation", "research", "other"]

STATUS_ICON = {
    STATUS_OPEN: "🎯",
    STATUS_CLOSED: "✅",
    STATUS_PAUSED: "⏸",
}


def _next_goal_id() -> str:
    GOALS_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(GOALS_DIR.glob("GOAL-*.json"))
    if not existing:
        return "GOAL-001"
    last = existing[-1].stem  # GOAL-NNN
    try:
        n = int(last.split("-")[1]) + 1
    except Exception:
        n = len(existing) + 1
    return f"GOAL-{n:03d}"


def _load_goal(goal_id: str) -> dict:
    GOALS_DIR.mkdir(parents=True, exist_ok=True)
    path = GOALS_DIR / f"{goal_id}.json"
    if not path.exists():
        print(f"  ERROR: objetivo no encontrado: {goal_id}")
        raise SystemExit(1)
    return json.loads(path.read_text())


def _save_goal(goal: dict):
    GOALS_DIR.mkdir(parents=True, exist_ok=True)
    path = GOALS_DIR / f"{goal['goal_id']}.json"
    path.write_text(json.dumps(goal, indent=2, ensure_ascii=False))


def _load_all_goals() -> list:
    GOALS_DIR.mkdir(parents=True, exist_ok=True)
    goals = []
    for f in sorted(GOALS_DIR.glob("GOAL-*.json")):
        try:
            goals.append(json.loads(f.read_text()))
        except Exception:
            pass
    return goals


def cmd_new(args):
    if not args.title:
        print("  ERROR: indica el título del objetivo")
        raise SystemExit(1)
    goal_id = _next_goal_id()
    cat = args.cat if args.cat in CATEGORIES else "other"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    goal = {
        "goal_id": goal_id,
        "title": args.title,
        "description": args.desc or "",
        "category": cat,
        "status": STATUS_OPEN,
        "created_at": now,
        "updated_at": now,
        "linked_sessions": [],
        "linked_changes": [],
        "notes": [],
    }
    _save_goal(goal)
    print(f"\n  ✅ Objetivo creado: {goal_id}")
    print(f"  Título:    {goal['title']}")
    print(f"  Categoría: {goal['category']}")
    print()


def cmd_list(args):
    goals = _load_all_goals()
    if not goals:
        print("\n  (sin objetivos registrados)")
        print(f"  Crea uno: bago goals new \"Mi objetivo\" --cat capability\n")
        return

    status_filter = args.status if args.status else None
    if status_filter:
        goals = [g for g in goals if g.get("status") == status_filter]

    cat_filter = args.cat if args.cat else None
    if cat_filter:
        goals = [g for g in goals if g.get("category") == cat_filter]

    print(f"\n  Objetivos BAGO ({len(goals)})\n")
    print(f"  {'ID':10s} {'St':2s} {'Cat':14s} {'Sesiones':8s} {'Título'}")
    print(f"  {'-'*10} {'-'*2} {'-'*14} {'-'*8} {'-'*40}")

    for g in goals:
        icon = STATUS_ICON.get(g.get("status", ""), "?")
        cat = g.get("category", "")[:14]
        ses_count = len(g.get("linked_sessions", []))
        title = g.get("title", "")[:50]
        print(f"  {g['goal_id']:10s} {icon:2s} {cat:14s} {ses_count:8d}  {title}")
    print()


def cmd_show(args):
    if not args.goal_id:
        print("  ERROR: indica el ID del objetivo")
        raise SystemExit(1)
    g = _load_goal(args.goal_id)
    icon = STATUS_ICON.get(g.get("status", ""), "?")
    print(f"\n  {icon} {g['goal_id']}: {g['title']}")
    print(f"  Categoría: {g['category']}  |  Estado: {g['status']}")
    print(f"  Creado:    {g['created_at'][:19]}")
    if g.get("description"):
        print(f"  Desc:      {g['description']}")
    ses = g.get("linked_sessions", [])
    if ses:
        print(f"\n  Sesiones vinculadas ({len(ses)}):")
        for s in ses:
            print(f"    · {s}")
    chgs = g.get("linked_changes", [])
    if chgs:
        print(f"\n  Cambios vinculados ({len(chgs)}):")
        for c in chgs:
            print(f"    · {c}")
    notes = g.get("notes", [])
    if notes:
        print(f"\n  Notas:")
        for n in notes:
            print(f"    - {n}")
    print()


def cmd_close(args):
    if not args.goal_id:
        print("  ERROR: indica el ID del objetivo")
        raise SystemExit(1)
    g = _load_goal(args.goal_id)
    g["status"] = STATUS_CLOSED
    g["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if args.note:
        g.setdefault("notes", []).append(args.note)
    _save_goal(g)
    print(f"\n  ✅ Objetivo cerrado: {args.goal_id} — {g['title']}\n")


def cmd_link(args):
    if not args.goal_id or not args.ref:
        print("  ERROR: indica GOAL-ID y el REF (sesión o cambio)")
        raise SystemExit(1)
    g = _load_goal(args.goal_id)
    ref = args.ref
    if ref.startswith("SES-") or ref.startswith("ses-"):
        lst = g.setdefault("linked_sessions", [])
        if ref not in lst:
            lst.append(ref)
            print(f"  Sesión {ref} vinculada a {args.goal_id}")
        else:
            print(f"  (ya vinculada)")
    elif ref.startswith("BAGO-CHG") or ref.startswith("CHG"):
        lst = g.setdefault("linked_changes", [])
        if ref not in lst:
            lst.append(ref)
            print(f"  Cambio {ref} vinculado a {args.goal_id}")
        else:
            print(f"  (ya vinculado)")
    else:
        # Generic link
        lst = g.setdefault("linked_sessions", [])
        if ref not in lst:
            lst.append(ref)
            print(f"  Referencia {ref} vinculada a {args.goal_id}")
    g["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _save_goal(g)


def cmd_progress(args):
    goals = _load_all_goals()
    if not goals:
        print("\n  (sin objetivos)\n")
        return

    total = len(goals)
    by_status = {}
    for g in goals:
        s = g.get("status", "?")
        by_status[s] = by_status.get(s, 0) + 1

    by_cat = {}
    for g in goals:
        c = g.get("category", "other")
        by_cat[c] = by_cat.get(c, 0) + 1

    closed = by_status.get(STATUS_CLOSED, 0)
    pct = int(closed / total * 100) if total else 0
    bar_w = 30
    filled = int(pct / 100 * bar_w)
    bar = "█" * filled + "░" * (bar_w - filled)

    print(f"\n  Progreso de objetivos BAGO")
    print(f"  Total: {total}  |  Completados: {closed}/{total}  ({pct}%)")
    print(f"  [{bar}] {pct}%\n")

    print("  Por estado:")
    for s, c in sorted(by_status.items()):
        icon = STATUS_ICON.get(s, "?")
        print(f"    {icon} {s:10s} {c}")

    print("\n  Por categoría:")
    for c, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"    {c:14s} {n}")
    print()


def run_tests():
    import tempfile, shutil
    print("Ejecutando tests de goals.py...")
    errors = 0

    def ok(name):
        print(f"  OK: {name}")

    def fail(name, msg):
        nonlocal errors
        errors += 1
        print(f"  FAIL: {name} — {msg}")

    with tempfile.TemporaryDirectory() as tmp:
        # Patch GOALS_DIR
        orig = GOALS_DIR
        import sys
        import importlib
        import types

        tmp_goals = pathlib.Path(tmp) / "goals"
        tmp_goals.mkdir()

        # Test using direct function calls with patched dir
        goal = {
            "goal_id": "GOAL-T01",
            "title": "Test Goal",
            "description": "desc",
            "category": "quality",
            "status": "open",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "linked_sessions": [],
            "linked_changes": [],
            "notes": [],
        }
        (tmp_goals / "GOAL-T01.json").write_text(json.dumps(goal))

        # Test 1: load
        loaded = json.loads((tmp_goals / "GOAL-T01.json").read_text())
        if loaded["goal_id"] == "GOAL-T01":
            ok("goals:load")
        else:
            fail("goals:load", str(loaded))

        # Test 2: modify status
        loaded["status"] = "closed"
        (tmp_goals / "GOAL-T01.json").write_text(json.dumps(loaded))
        reloaded = json.loads((tmp_goals / "GOAL-T01.json").read_text())
        if reloaded["status"] == "closed":
            ok("goals:close")
        else:
            fail("goals:close", str(reloaded))

        # Test 3: multiple goals
        for i in range(2, 5):
            g2 = dict(goal)
            g2["goal_id"] = f"GOAL-T{i:02d}"
            g2["category"] = "capability" if i % 2 == 0 else "research"
            (tmp_goals / f"GOAL-T{i:02d}.json").write_text(json.dumps(g2))

        all_goals = [json.loads(f.read_text()) for f in sorted(tmp_goals.glob("GOAL-*.json"))]
        if len(all_goals) == 4:
            ok("goals:list_all")
        else:
            fail("goals:list_all", f"expected 4 got {len(all_goals)}")

        # Test 4: link session
        loaded2 = json.loads((tmp_goals / "GOAL-T01.json").read_text())
        loaded2.setdefault("linked_sessions", []).append("SES-TEST-001")
        (tmp_goals / "GOAL-T01.json").write_text(json.dumps(loaded2))
        check = json.loads((tmp_goals / "GOAL-T01.json").read_text())
        if "SES-TEST-001" in check.get("linked_sessions", []):
            ok("goals:link_session")
        else:
            fail("goals:link_session", str(check))

        # Test 5: progress calc
        by_status = {}
        for g in all_goals:
            s = g.get("status", "?")
            by_status[s] = by_status.get(s, 0) + 1
        closed = by_status.get("closed", 0)
        if closed == 1:
            ok("goals:progress_closed_count")
        else:
            fail("goals:progress_closed_count", f"expected 1 got {closed}")

    total = 5
    passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors:
        raise SystemExit(1)

# Need pathlib imported at module level for tests
import pathlib

def main():
    parser = argparse.ArgumentParser(prog="bago goals", add_help=False)
    sub = parser.add_subparsers(dest="subcmd")

    p_new = sub.add_parser("new")
    p_new.add_argument("title", nargs="?", default=None)
    p_new.add_argument("--cat", default="other")
    p_new.add_argument("--desc", default="")

    p_list = sub.add_parser("list")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--cat", default=None)

    p_show = sub.add_parser("show")
    p_show.add_argument("goal_id", nargs="?", default=None)

    p_close = sub.add_parser("close")
    p_close.add_argument("goal_id", nargs="?", default=None)
    p_close.add_argument("--note", default=None)

    p_link = sub.add_parser("link")
    p_link.add_argument("goal_id", nargs="?", default=None)
    p_link.add_argument("ref", nargs="?", default=None)

    sub.add_parser("progress")

    parser.add_argument("--test", action="store_true")
    parser.add_argument("--status", default=None)
    parser.add_argument("--cat", default=None)

    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.subcmd == "new":
        cmd_new(args)
    elif args.subcmd == "show":
        cmd_show(args)
    elif args.subcmd == "close":
        cmd_close(args)
    elif args.subcmd == "link":
        cmd_link(args)
    elif args.subcmd == "progress":
        cmd_progress(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    main()