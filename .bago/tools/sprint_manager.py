#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merged sprint tool for BAGO.

Behaviors:
  python sprint_manager.py                 -> show current sprint plan or create one
  python sprint_manager.py --new           -> create next sprint plan
  python sprint_manager.py --status        -> show sprint plan status
  python sprint_manager.py summary         -> generate/show sprint summaries
  python sprint_manager.py --summary       -> same as summary
  python sprint_manager.py manager ...     -> full sprint manager
  python sprint_manager.py new|list|...    -> full sprint manager shortcuts
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
STATE = ROOT / "state"
DB_PATH = STATE / "bago.db"
IMPL_PATH = STATE / "implemented_ideas.json"
SPRINT_PLAN_PATH = STATE / "sprint_plan.json"
SPRINTS_DIR = STATE / "sprints"
GLOBAL_STATE = STATE / "global_state.json"
SPRINT_SIZE = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Shared helpers ──────────────────────────────────────────────────────────

def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Legacy sprint.py behavior ───────────────────────────────────────────────

def _load_implemented_titles() -> set[str]:
    data = _load_json(IMPL_PATH, {"implemented": []})
    return {e.get("title", "") for e in data.get("implemented", []) if e.get("title")}


def _fetch_available_ideas(exclude_titles: set[str]) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT id, title, priority FROM ideas ORDER BY priority DESC, id ASC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": idea_id, "title": title, "priority": priority}
        for idea_id, title, priority in rows
        if title not in exclude_titles
    ]


def _next_plan_sprint_id() -> str:
    existing = sorted(STATE.glob("sprint_summary_*.md"))
    nums: list[int] = []
    for path in existing:
        try:
            nums.append(int(path.stem.split("_")[-1]))
        except (TypeError, ValueError, IndexError):
            pass
    if SPRINT_PLAN_PATH.exists():
        plan = _load_json(SPRINT_PLAN_PATH, {})
        sprint_id = plan.get("sprint_id", "")
        if sprint_id.startswith("sprint_"):
            try:
                nums.append(int(sprint_id.split("_")[-1]))
            except (TypeError, ValueError, IndexError):
                pass
    return f"sprint_{(max(nums) + 1) if nums else 1:02d}"


def _create_sprint_plan(sprint_id: str, ideas: list[dict]) -> dict:
    return {
        "sprint_id": sprint_id,
        "created_at": _now_iso(),
        "ideas": [
            {
                "id": idea["id"],
                "title": idea["title"],
                "priority": idea["priority"],
                "done": False,
            }
            for idea in ideas[:SPRINT_SIZE]
        ],
    }


def _sprint_num(sprint_id: str) -> str:
    parts = sprint_id.split("_")
    return parts[-1] if len(parts) > 1 else sprint_id


def _print_sprint(plan: dict, implemented_titles: set[str]) -> None:
    print(f"\nBAGO Sprint #{_sprint_num(plan.get('sprint_id', 'sprint'))}")
    ideas = plan.get("ideas", [])
    if not ideas:
        print("  (sin ideas en este sprint)")
        return
    for item in ideas:
        done = item.get("done", False) or item.get("title") in implemented_titles
        tick = "✓" if done else " "
        print(f"  [{tick}] [{item.get('priority', '?')}] {item.get('title', '—')}")
    print()


def _cmd_show() -> None:
    if SPRINT_PLAN_PATH.exists():
        _print_sprint(_load_json(SPRINT_PLAN_PATH, {}), _load_implemented_titles())
        return
    print("  No hay sprint activo. Generando uno nuevo…\n")
    _cmd_new()


def _cmd_new() -> None:
    implemented = _load_implemented_titles()
    available = _fetch_available_ideas(implemented)
    if not available:
        print("  ⚠ No hay ideas disponibles en bago.db.")
        raise SystemExit(1)
    plan = _create_sprint_plan(_next_plan_sprint_id(), available)
    _save_json(SPRINT_PLAN_PATH, plan)
    print(f"  ✅ Sprint creado: {plan['sprint_id']} → {SPRINT_PLAN_PATH}")
    _print_sprint(plan, implemented)


def _cmd_status() -> None:
    if not SPRINT_PLAN_PATH.exists():
        print("  ⚠ No hay sprint activo. Ejecuta: python sprint_manager.py --new")
        raise SystemExit(1)
    plan = _load_json(SPRINT_PLAN_PATH, {})
    implemented = _load_implemented_titles()
    ideas = plan.get("ideas", [])
    done_count = sum(1 for item in ideas if item.get("done") or item.get("title") in implemented)
    print(f"\nBAGO Sprint #{_sprint_num(plan.get('sprint_id', 'sprint'))} — Progreso: {done_count}/{len(ideas)}")
    print(f"  Creado: {str(plan.get('created_at', ''))[:10]}")
    _print_sprint(plan, implemented)


# ── Legacy sprint_summary.py behavior ───────────────────────────────────────

def _load_implemented() -> list[dict]:
    return _load_json(IMPL_PATH, {"implemented": []}).get("implemented", [])


def _total_in_db() -> int:
    if not DB_PATH.exists():
        return 0
    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            return conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return 0


def _sprint_path(sprint_n: int) -> Path:
    return STATE / f"sprint_summary_{sprint_n:02d}.md"


def _sprint_velocity(ideas: list[dict]) -> str:
    """Calcula velocidad: ideas/día basándose en done_at timestamps.
    # SPRINT_VELOCITY_IMPLEMENTED
    """
    dates = []
    for idea in ideas:
        done_at = idea.get("done_at", "")
        if not done_at:
            continue
        try:
            dates.append(datetime.fromisoformat(done_at.replace("Z", "+00:00")))
        except Exception:
            pass
    if not dates:
        return "— (sin fechas)"
    if len(dates) == 1:
        return f"1 idea (fecha única: {dates[0].strftime('%Y-%m-%d')})"
    dates.sort()
    days = max((dates[-1] - dates[0]).total_seconds() / 86400, 0.1)
    return f"{round(len(ideas) / days, 2)} ideas/día  ({len(ideas)} ideas en {round(days, 1)}d)"


def _generate_sprint(sprint_n: int, ideas_in_sprint: list[dict], total_impl: int, total_db: int) -> Path:
    start_idx = (sprint_n - 1) * SPRINT_SIZE + 1
    end_idx = sprint_n * SPRINT_SIZE
    pct = round(100 * total_impl / total_db) if total_db > 0 else 0
    slots = sorted({str(i.get("slot", "—")) for i in ideas_in_sprint})
    rows = []
    for rel_idx, idea in enumerate(ideas_in_sprint):
        rows.append(
            f"| {start_idx + rel_idx} | {idea.get('title', '—')} | {idea.get('slot', '—')} | {(idea.get('done_at') or '')[:10] or '—'} |"
        )
    lines = [
        f"# Sprint BAGO #{sprint_n:02d} — Resumen",
        f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}",
        f"Ideas: {start_idx}–{end_idx} de {total_impl} implementadas",
        "",
        "## Ideas implementadas en este sprint",
        "",
        "| # | Título | Slot | Fecha |",
        "|---|--------|------|-------|",
        *rows,
        "",
        "## Métricas",
        f"- Ideas en este sprint: {len(ideas_in_sprint)}",
        f"- Slots activados: {', '.join(slots)}",
        f"- Total acumulado: {total_impl}/{total_db} ({pct}%)",
        f"- Velocidad: {_sprint_velocity(ideas_in_sprint)}",
        "",
        "## Próximos hitos",
        f"- Sprint #{sprint_n + 1:02d} completará: {end_idx + SPRINT_SIZE} ideas",
        "",
    ]
    out = _sprint_path(sprint_n)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _export_report() -> Path:
    implemented = _load_implemented()
    total = len(implemented)
    total_db = _total_in_db() or total
    completed = total // SPRINT_SIZE
    lines = [
        "# BAGO — Historial completo de ideas implementadas",
        f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}",
        f"Total: {total}/{total_db} ideas implementadas ({round(100 * total / total_db) if total_db > 0 else 0}%)",
        "",
    ]
    for sprint_n in range(1, completed + 1):
        start = (sprint_n - 1) * SPRINT_SIZE
        end = sprint_n * SPRINT_SIZE
        ideas = implemented[start:end]
        lines += [
            f"## Sprint #{sprint_n:02d}  (ideas {start + 1}–{end})",
            f"Velocidad: {_sprint_velocity(ideas)}",
            "",
            "| # | Título | Slot | Fecha |",
            "|---|--------|------|-------|",
        ]
        for idx, idea in enumerate(ideas):
            lines.append(
                f"| {start + idx + 1} | {idea.get('title', '—')} | {idea.get('slot', '—')} | {(idea.get('done_at') or '')[:10] or '—'} |"
            )
        lines.append("")
    extra = implemented[completed * SPRINT_SIZE:]
    if extra:
        lines += [
            f"## Sprint #{completed + 1:02d}  (en progreso — {len(extra)}/{SPRINT_SIZE})",
            "",
            "| # | Título | Slot | Fecha |",
            "|---|--------|------|-------|",
        ]
        for idx, idea in enumerate(extra):
            lines.append(
                f"| {completed * SPRINT_SIZE + idx + 1} | {idea.get('title', '—')} | {idea.get('slot', '—')} | {(idea.get('done_at') or '')[:10] or '—'} |"
            )
        lines.append("")
    out = STATE / "ideas_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def generate_if_due() -> list[Path]:
    """
    Genera resúmenes para todos los sprints completados sin archivo de resumen.
    # SPRINT_SUMMARY_IMPLEMENTED
    """
    implemented = _load_implemented()
    total = len(implemented)
    if total < SPRINT_SIZE:
        return []
    total_db = _total_in_db() or total
    generated: list[Path] = []
    for sprint_n in range(1, total // SPRINT_SIZE + 1):
        path = _sprint_path(sprint_n)
        if not path.exists():
            start = (sprint_n - 1) * SPRINT_SIZE
            generated.append(_generate_sprint(sprint_n, implemented[start:start + SPRINT_SIZE], total, total_db))
    return generated


def summary_main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    status_only = "--status" in args
    export_only = "--export" in args
    implemented = _load_implemented()
    total = len(implemented)
    completed = total // SPRINT_SIZE

    print()
    print("BAGO Sprint Summary")
    print(f"  Ideas implementadas : {total}")
    print(f"  Sprints completados : {completed}")
    print()

    if export_only:
        out = _export_report()
        print(f"  📄 Informe exportado: {out.relative_to(ROOT.parent)}")
        print()
        return 0

    if status_only:
        for n in range(1, completed + 1):
            path = _sprint_path(n)
            print(f"  {'✅' if path.exists() else '⏳'}  Sprint #{n:02d}  {path.name}  {'(existe)' if path.exists() else '(pendiente)'}")
        if not completed:
            print("  Sin sprints completados aún (< 5 ideas implementadas).")
        print()
        return 0

    generated = generate_if_due()
    if generated:
        for path in generated:
            print(f"  📋 Generado: {path.relative_to(ROOT.parent)}")
    else:
        print("  ✅ Todos los resúmenes de sprint al día.")
    print()
    return 0


# ── Legacy sprint_manager.py behavior ───────────────────────────────────────

def _all_sprints() -> list[dict]:
    SPRINTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in SPRINTS_DIR.glob("SPRINT-*.json"):
        data = _load_json(path, {})
        if data:
            items.append(data)
    items.sort(key=lambda item: item.get("created_at", ""))
    return items


def _next_manager_sprint_id() -> str:
    nums: list[int] = []
    for path in SPRINTS_DIR.glob("SPRINT-*.json"):
        try:
            nums.append(int(path.stem.split("-")[-1]))
        except (TypeError, ValueError, IndexError):
            pass
    return f"SPRINT-{(max(nums) + 1) if nums else 1:03d}"


def _active_sprint() -> Optional[dict]:
    for sprint in _all_sprints():
        if sprint.get("status") == "open":
            return sprint
    return None


def _sprint_file(sprint_id: str) -> Path:
    return SPRINTS_DIR / f"{sprint_id}.json"


def _sync_global_state(sprints: list[dict]) -> None:
    data = _load_json(GLOBAL_STATE, {})
    data["sprint_status"] = {s["sprint_id"]: s.get("status", "unknown") for s in sprints if s.get("sprint_id")}
    data["updated_at"] = _now_iso()
    _save_json(GLOBAL_STATE, data)


def cmd_new(name: str, goal: str = "", tags: list | None = None, force: bool = False) -> None:
    active = _active_sprint()
    if active and not force:
        print(f"  Ya hay un sprint abierto: {active['sprint_id']} -- {active['name']}")
        print("  Cierralo primero con: bago sprint close")
        print("  O usa --force para crear igualmente.")
        raise SystemExit(1)
    sprint = {
        "sprint_id": _next_manager_sprint_id(),
        "name": name,
        "goal": goal or name,
        "status": "open",
        "tags": tags or [],
        "sessions": [],
        "artifacts": [],
        "decisions": [],
        "created_at": _now_iso(),
        "closed_at": None,
        "summary": None,
    }
    _save_json(_sprint_file(sprint["sprint_id"]), sprint)
    _sync_global_state(_all_sprints())
    print()
    print("  +----------------------------------------------------------+")
    print("  |  Sprint creado                                           |")
    print("  +----------------------------------------------------------+")
    print(f"  ID:     {sprint['sprint_id']}")
    print(f"  Nombre: {name}")
    if goal and goal != name:
        print(f"  Obj:    {goal}")
    print("  Estado: open")
    print()
    print("  Comandos utiles:")
    print("    bago sprint status   -> ver estado")
    print("    bago sprint close    -> cerrar sprint")
    print()


def cmd_list() -> None:
    sprints = _all_sprints()
    if not sprints:
        print("  No hay sprints. Usa: bago sprint new 'Nombre'")
        return
    print("\n  BAGO - Sprints\n")
    icons = {"open": "[OPEN]", "closed": "[DONE]", "cancelled": "[CANC]"}
    for sprint in reversed(sprints):
        closed_at = sprint.get("closed_at") or ""
        print(
            "  {}  {:<14}  {:<35}  {} -> {}".format(
                icons.get(sprint.get("status", ""), "[----]"),
                sprint.get("sprint_id", "?"),
                str(sprint.get("name", "--"))[:35],
                str(sprint.get("created_at", ""))[:10],
                closed_at[:10] if closed_at else "abierto",
            )
        )
        sessions = len(sprint.get("sessions", []))
        artifacts = len(sprint.get("artifacts", []))
        if sessions or artifacts:
            print(f"               sesiones={sessions}  artefactos={artifacts}")
    print()


def cmd_status() -> None:
    active = _active_sprint()
    if not active:
        closed = [s for s in _all_sprints() if s.get("status") == "closed"]
        if closed:
            last = closed[-1]
            print(f"  No hay sprint activo. Ultimo cerrado: {last['sprint_id']} -- {last['name']}")
        else:
            print("  No hay sprints. Crea uno: bago sprint new Nombre")
        return
    print()
    print("  [OPEN] Sprint activo")
    print(f"  ID:        {active['sprint_id']}")
    print(f"  Nombre:    {active['name']}")
    print(f"  Objetivo:  {active.get('goal', '--')}")
    print(f"  Creado:    {str(active.get('created_at', ''))[:16].replace('T', ' ')} UTC")
    print(f"  Sesiones:  {len(active.get('sessions', []))}")
    for sid in active.get("sessions", [])[-3:]:
        print(f"               * {sid}")
    if len(active.get("sessions", [])) > 3:
        print(f"               ... +{len(active['sessions']) - 3} mas")
    print(f"  Artefactos: {len(active.get('artifacts', []))}")
    for art in active.get("artifacts", [])[-5:]:
        print(f"               * {art}")
    if len(active.get("artifacts", [])) > 5:
        print(f"               ... +{len(active['artifacts']) - 5} mas")
    print(f"  Decisiones: {len(active.get('decisions', []))}")
    for decision in active.get("decisions", [])[-3:]:
        print(f"               * {decision}")
    if active.get("tags"):
        print(f"  Tags:      {', '.join(active['tags'])}")
    print()


def cmd_active() -> None:
    active = _active_sprint()
    print(active["sprint_id"] if active else "none")


def cmd_close(sprint_id: str | None = None, summary: str = "") -> None:
    if sprint_id:
        path = _sprint_file(sprint_id)
        if not path.exists():
            print(f"  Sprint no encontrado: {sprint_id}")
            raise SystemExit(1)
        sprint = _load_json(path, {})
    else:
        sprint = _active_sprint()
        if not sprint:
            print("  No hay sprint activo para cerrar.")
            return
        path = _sprint_file(sprint["sprint_id"])
    if sprint.get("status") == "closed":
        print(f"  El sprint {sprint['sprint_id']} ya esta cerrado.")
        return
    sprint["status"] = "closed"
    sprint["closed_at"] = _now_iso()
    sprint["summary"] = summary or sprint.get("summary") or (
        f"Sprint cerrado -- {len(sprint.get('artifacts', []))} artefactos, {len(sprint.get('sessions', []))} sesiones."
    )
    _save_json(path, sprint)
    _sync_global_state(_all_sprints())
    print(f"\n  [DONE] Sprint cerrado: {sprint['sprint_id']}")
    print(f"  Nombre:  {sprint['name']}")
    print(f"  Resumen: {sprint['summary']}\n")


def cmd_show(sprint_id: str) -> None:
    path = _sprint_file(sprint_id)
    if not path.exists():
        print(f"  Sprint no encontrado: {sprint_id}")
        raise SystemExit(1)
    print(json.dumps(_load_json(path, {}), indent=2, ensure_ascii=False))


def cmd_link(sprint_id: str, session_id: str) -> None:
    path = _sprint_file(sprint_id)
    if not path.exists():
        print(f"  Sprint no encontrado: {sprint_id}")
        raise SystemExit(1)
    sprint = _load_json(path, {})
    sessions = sprint.setdefault("sessions", [])
    if session_id not in sessions:
        sessions.append(session_id)
        _save_json(path, sprint)
        print(f"  Sesion {session_id} enlazada a {sprint_id}")
    else:
        print(f"  Sesion {session_id} ya enlazada a {sprint_id}")


def cmd_add_artifact(sprint_id: str, artifact: str) -> None:
    if not sprint_id or sprint_id == "none":
        return
    path = _sprint_file(sprint_id)
    if not path.exists():
        return
    sprint = _load_json(path, {})
    artifacts = sprint.setdefault("artifacts", [])
    if artifact not in artifacts:
        artifacts.append(artifact)
        _save_json(path, sprint)


def manager_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestor de sprints BAGO")
    sub = parser.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new")
    p_new.add_argument("name")
    p_new.add_argument("--goal", default="")
    p_new.add_argument("--tags", default="")
    p_new.add_argument("--force", action="store_true")

    sub.add_parser("list")
    sub.add_parser("status")
    sub.add_parser("active")

    p_close = sub.add_parser("close")
    p_close.add_argument("sprint_id", nargs="?", default=None)
    p_close.add_argument("--summary", default="")

    p_show = sub.add_parser("show")
    p_show.add_argument("sprint_id")

    p_link = sub.add_parser("link")
    p_link.add_argument("sprint_id")
    p_link.add_argument("session_id")

    args = parser.parse_args([] if argv is None else argv)
    if args.cmd == "new":
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()] if args.tags else []
        cmd_new(args.name, goal=args.goal, tags=tags, force=args.force)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "active":
        cmd_active()
    elif args.cmd == "close":
        cmd_close(args.sprint_id, summary=args.summary)
    elif args.cmd == "show":
        cmd_show(args.sprint_id)
    elif args.cmd == "link":
        cmd_link(args.sprint_id, args.session_id)
    else:
        cmd_status()
    return 0


def _print_usage() -> None:
    print(__doc__)
    print("\nManager subcommands:")
    print("  new | list | status | active | close | show | link")
    print("\nSummary shortcuts:")
    print("  summary [--status|--export]")
    print("  --summary [--status|--export]")


def _run_tests() -> None:
    assert _sprint_num("sprint_08") == "08"
    assert _sprint_velocity([]).startswith("—")
    assert _next_plan_sprint_id().startswith("sprint_")
    print("  3/3 tests pasaron")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--test" in args:
        _run_tests()
        return 0
    if not args:
        _cmd_show()
        return 0
    if args[0] in {"-h", "--help", "help"}:
        _print_usage()
        return 0
    if args[0] == "summary":
        return summary_main(args[1:])
    if "--summary" in args:
        return summary_main([arg for arg in args if arg != "--summary"])
    if args[0] == "manager":
        return manager_main(args[1:])
    if "--manager" in args:
        return manager_main([arg for arg in args if arg != "--manager"])
    if args[0] in {"new", "list", "status", "active", "close", "show", "link"}:
        return manager_main(args)
    if "--new" in args:
        _cmd_new()
        return 0
    if "--status" in args:
        _cmd_status()
        return 0
    _print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
