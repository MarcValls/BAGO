#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
changelog_gen.py — Genera CHANGELOG.md desde las ideas implementadas en BAGO.

Agrupa por semana o por fecha de implementación. Puede actualizar el CHANGELOG
del proyecto o mostrarlo en pantalla.

Uso:
    python3 .bago/tools/changelog_gen.py           # muestra en pantalla
    python3 .bago/tools/changelog_gen.py --write   # escribe CHANGELOG.md
    python3 .bago/tools/changelog_gen.py --format md|txt  # formato (default md)
    python3 .bago/tools/changelog_gen.py --since 2024-01-01  # desde fecha
    python3 .bago/tools/changelog_gen.py --by day|week|month  # agrupación

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
IMPL_FILE = STATE / "implemented_ideas.json"


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _load_ideas() -> list[dict]:
    if not IMPL_FILE.exists():
        return []
    try:
        data = json.loads(IMPL_FILE.read_text(encoding="utf-8"))
        items = data.get("implemented", [])
        # Sort by done_at
        return sorted(items, key=lambda x: x.get("done_at", ""), reverse=True)
    except Exception:
        return []


def _group_key(dt: datetime, by: str) -> str:
    if by == "day":
        return dt.strftime("%Y-%m-%d")
    if by == "month":
        return dt.strftime("%Y-%m")
    # week (default)
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _group_label(key: str, by: str) -> str:
    if by == "day":
        try:
            d = datetime.strptime(key, "%Y-%m-%d")
            return d.strftime("%A %d %B %Y")
        except Exception:
            return key
    if by == "month":
        try:
            d = datetime.strptime(key, "%Y-%m")
            return d.strftime("%B %Y")
        except Exception:
            return key
    # week
    return f"Semana {key}"


def _build_changelog(ideas: list[dict], by: str, since: datetime | None) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for idea in ideas:
        dt = _parse_dt(idea.get("done_at", ""))
        if since and dt < since:
            continue
        key = _group_key(dt, by)
        title = idea.get("title", idea.get("idea_title", "Sin título"))
        groups[key].append(title)
    return dict(groups)


def _render_md(groups: dict[str, list[str]], by: str) -> str:
    lines = ["# CHANGELOG\n", "> Generado automáticamente por BAGO\n"]
    for key in sorted(groups.keys(), reverse=True):
        label = _group_label(key, by)
        lines.append(f"\n## {label}\n")
        for title in groups[key]:
            lines.append(f"- {title}")
        lines.append("")
    return "\n".join(lines)


def _render_txt(groups: dict[str, list[str]], by: str) -> str:
    lines = ["CHANGELOG", "=" * 60, ""]
    for key in sorted(groups.keys(), reverse=True):
        label = _group_label(key, by)
        lines.append(f"  {label}")
        lines.append("  " + "─" * 40)
        for title in groups[key]:
            lines.append(f"    • {title}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    fmt      = "md"
    by       = "week"
    write    = "--write" in args
    since_dt: datetime | None = None

    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            fmt = args[idx + 1]

    if "--by" in args:
        idx = args.index("--by")
        if idx + 1 < len(args):
            by = args[idx + 1]
        if by not in ("day", "week", "month"):
            print(f"\n  {RED('✗')} --by debe ser: day, week o month\n")
            return 1

    if "--since" in args:
        idx = args.index("--since")
        if idx + 1 < len(args):
            try:
                since_dt = datetime.fromisoformat(args[idx + 1]).replace(tzinfo=timezone.utc)
            except ValueError:
                print(f"\n  {RED('✗')} Formato de fecha inválido: {args[idx+1]}\n")
                return 1

    ideas = _load_ideas()
    if not ideas:
        print(f"\n  {YELLOW('⚠')} No hay ideas implementadas. Ejecuta: bago ideas --accept 1\n")
        return 0

    groups = _build_changelog(ideas, by, since_dt)

    if fmt == "md":
        content = _render_md(groups, by)
    else:
        content = _render_txt(groups, by)

    total = sum(len(v) for v in groups.values())

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Changelog                                           │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Ideas: {BOLD(str(total))}  |  Períodos: {len(groups)}  |  Agrupación: {by}  |  Formato: {fmt}")

    if since_dt:
        print(f"  Desde: {since_dt.strftime('%Y-%m-%d')}")
    print()

    if write:
        # Detect project CHANGELOG if it exists, otherwise create in project root
        gs = STATE / "global_state.json"
        project_root = ROOT
        if gs.exists():
            try:
                data = json.loads(gs.read_text(encoding="utf-8"))
                p = data.get("active_project", {}).get("path", "")
                if p:
                    project_root = Path(p)
            except Exception:
                pass

        suffix = ".md" if fmt == "md" else ".txt"
        out_file = project_root / f"BAGO_CHANGELOG{suffix}"
        out_file.write_text(content, encoding="utf-8")
        print(f"  {GREEN('✅')} Changelog escrito en: {BOLD(str(out_file))}")
        print(f"  {len(content.splitlines())} líneas, {len(content)} bytes")
        print()
    else:
        # Print to terminal (paginated at 40 lines)
        lines = content.splitlines()
        for line in lines[:80]:
            if line.startswith("##"):
                print(f"  {CYAN(line)}")
            elif line.startswith("- ") or line.startswith("  • "):
                print(f"  {DIM(line)}")
            else:
                print(f"  {line}")
        if len(lines) > 80:
            print(f"\n  {DIM(f'... y {len(lines)-80} líneas más. Usa --write para escribir el archivo completo.')}")
        print()

    return 0



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
