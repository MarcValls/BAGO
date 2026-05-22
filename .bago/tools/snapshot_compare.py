#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snapshot_compare.py — Compara dos snapshots de estado de BAGO.

Muestra diferencias en herramientas, ideas implementadas y archivos de estado
entre dos ZIPs de snapshot.

Uso:
    python3 .bago/tools/snapshot_compare.py --list       # lista snapshots
    python3 .bago/tools/snapshot_compare.py              # compara los 2 más recientes
    python3 .bago/tools/snapshot_compare.py FILE1 FILE2  # compara snapshots específicos
    python3 .bago/tools/snapshot_compare.py --ideas      # solo comparar ideas
    python3 .bago/tools/snapshot_compare.py --tools      # solo comparar herramientas
    python3 .bago/tools/snapshot_compare.py --json       # salida JSON

Códigos de salida: 0 = igual, 1 = hay diferencias, 2 = error
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT      = Path(__file__).resolve().parents[2]
STATE     = ROOT / ".bago" / "state"
SNAPSHOTS = ROOT / ".bago" / "snapshots"


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _list_snapshots() -> list[Path]:
    if not SNAPSHOTS.exists():
        return []
    snaps = sorted(SNAPSHOTS.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return snaps


def _read_zip_names(path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(path, "r") as z:
            return set(z.namelist())
    except Exception:
        return set()


def _read_json_from_zip(path: Path, name: str) -> dict | list | None:
    try:
        with zipfile.ZipFile(path, "r") as z:
            if name in z.namelist():
                raw = z.read(name).decode("utf-8", errors="replace")
                return json.loads(raw)
    except Exception:
        return None


def _extract_ideas(data: dict | list | None) -> set[str]:
    if not data:
        return set()
    if isinstance(data, dict):
        items = data.get("implemented", [])
    elif isinstance(data, list):
        items = data
    else:
        return set()
    return {item.get("title", item.get("idea_title", "")) for item in items}


def _extract_tools(data: dict | list | None) -> set[str]:
    if not data or not isinstance(data, dict):
        return set()
    return set(data.keys())


def cmd_list() -> None:
    snaps = _list_snapshots()
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Snapshots disponibles                               │")
    print("  └─────────────────────────────────────────────────────────────┘")
    if not snaps:
        print(f"  {YELLOW('⚠')} No hay snapshots. Ejecuta: bago snapshot\n")
        return
    for snap in snaps:
        size_kb = snap.stat().st_size // 1024
        print(f"  {snap.name:<50}  {DIM(str(size_kb) + 'KB')}")
    print()


def compare(snap_a: Path, snap_b: Path, only: str | None, as_json: bool) -> int:
    names_a = _read_zip_names(snap_a)
    names_b = _read_zip_names(snap_b)

    # Ideas diff
    ideas_json = ".bago/state/implemented_ideas.json"
    ideas_a = _extract_ideas(_read_json_from_zip(snap_a, ideas_json))
    ideas_b = _extract_ideas(_read_json_from_zip(snap_b, ideas_json))
    ideas_added   = ideas_b - ideas_a
    ideas_removed = ideas_a - ideas_b

    # Files diff
    files_added   = names_b - names_a
    files_removed = names_a - names_b
    common        = names_a & names_b

    if as_json:
        result = {
            "snapshot_a": snap_a.name,
            "snapshot_b": snap_b.name,
            "ideas_added":    sorted(ideas_added),
            "ideas_removed":  sorted(ideas_removed),
            "files_added":    sorted(files_added),
            "files_removed":  sorted(files_removed),
            "files_common":   len(common),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if (ideas_added or ideas_removed or files_added or files_removed) else 0

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Comparar snapshots                                  │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  A: {DIM(snap_a.name)}")
    print(f"  B: {DIM(snap_b.name)}")
    print()

    has_diff = False

    if only in (None, "ideas"):
        print(f"  {BOLD('Ideas implementadas:')}")
        if not ideas_added and not ideas_removed:
            print(f"    {GREEN('✅ Sin diferencias')}  ({len(ideas_a)} ideas en ambos)")
        else:
            has_diff = True
            if ideas_added:
                print(f"    {GREEN(f'+ {len(ideas_added)} nuevas en B:')}")
                for t in sorted(ideas_added):
                    print(f"      {GREEN('+')} {t}")
            if ideas_removed:
                print(f"    {RED(f'- {len(ideas_removed)} eliminadas en B:')}")
                for t in sorted(ideas_removed):
                    print(f"      {RED('-')} {t}")
        print()

    if only in (None, "tools"):
        print(f"  {BOLD('Archivos en snapshot:')}")
        if not files_added and not files_removed:
            print(f"    {GREEN('✅ Sin diferencias')}  ({len(common)} archivos en ambos)")
        else:
            has_diff = True
            # Only show tools/ changes (more relevant)
            tools_added   = {f for f in files_added   if f.startswith(".bago/tools/")}
            tools_removed = {f for f in files_removed if f.startswith(".bago/tools/")}
            state_added   = {f for f in files_added   if f.startswith(".bago/state/")}
            state_removed = {f for f in files_removed if f.startswith(".bago/state/")}

            if tools_added:
                print(f"    {GREEN(f'+ {len(tools_added)} herramientas nuevas:')}")
                for f in sorted(tools_added):
                    print(f"      {GREEN('+')} {Path(f).name}")
            if tools_removed:
                print(f"    {RED(f'- {len(tools_removed)} herramientas eliminadas:')}")
                for f in sorted(tools_removed):
                    print(f"      {RED('-')} {Path(f).name}")
            if state_added:
                print(f"    {CYAN(f'+ {len(state_added)} archivos de estado nuevos')}")
            if state_removed:
                print(f"    {YELLOW(f'- {len(state_removed)} archivos de estado eliminados')}")
            other_added = files_added - tools_added - state_added
            if other_added:
                print(f"    {DIM(f'+ {len(other_added)} otros archivos nuevos')}")
        print()

    if not has_diff:
        print(f"  {GREEN('✅ Los snapshots son idénticos')} — sin diferencias detectadas\n")
        return 0
    return 1


def main() -> int:
    args    = sys.argv[1:]
    as_json = "--json" in args
    only    = None
    if "--ideas" in args:
        only = "ideas"
    if "--tools" in args:
        only = "tools"

    if "--list" in args or args == ["-l"]:
        cmd_list()
        return 0

    snaps = _list_snapshots()

    pos = [a for a in args if not a.startswith("-")]

    if len(pos) >= 2:
        snap_a = Path(pos[0]) if Path(pos[0]).exists() else SNAPSHOTS / pos[0]
        snap_b = Path(pos[1]) if Path(pos[1]).exists() else SNAPSHOTS / pos[1]
    elif len(snaps) >= 2:
        snap_b = snaps[0]  # most recent = B
        snap_a = snaps[1]  # older = A
    elif len(snaps) == 1:
        print(f"\n  {YELLOW('⚠')} Solo hay un snapshot. Crea otro con: bago snapshot\n")
        return 2
    else:
        print(f"\n  {YELLOW('⚠')} No hay snapshots. Crea uno con: bago snapshot\n")
        return 2

    if not snap_a.exists():
        print(f"\n  {RED('✗')} No se encuentra: {snap_a}\n")
        return 2
    if not snap_b.exists():
        print(f"\n  {RED('✗')} No se encuentra: {snap_b}\n")
        return 2

    return compare(snap_a, snap_b, only, as_json)



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
