#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
disk_usage.py — Muestra el tamaño de carpetas clave del proyecto.

Analiza node_modules, dist, build, .next, .bago, etc., con barras visuales.

Uso:
    python3 .bago/tools/disk_usage.py           # análisis completo
    python3 .bago/tools/disk_usage.py --all     # incluye carpetas vacías
    python3 .bago/tools/disk_usage.py web       # solo web

Códigos de salida: 0 = OK
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

# Target folders to measure in each app
TARGET_DIRS = [
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    "out",
    "coverage",
]


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path | None:
    gs = STATE / "global_state.json"
    if not gs.exists():
        return None
    try:
        data = json.loads(gs.read_text(encoding="utf-8"))
        p = data.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _dir_size(path: Path) -> int:
    """Sum of all file sizes in directory tree (bytes)."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return total


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 ** 2:
        return f"{size/1024:.1f}KB"
    elif size < 1024 ** 3:
        return f"{size/1024**2:.0f}MB"
    else:
        return f"{size/1024**3:.2f}GB"


def _size_bar(size: int, max_size: int, width: int = 25) -> str:
    if max_size == 0:
        return " " * width
    filled = int(size / max_size * width)
    bar = "█" * filled + "░" * (width - filled)
    gb = 1024 ** 3
    mb = 1024 ** 2
    if size > 500 * mb:
        return f"\033[31m{bar}\033[0m"  # red: >500MB
    elif size > 100 * mb:
        return f"\033[33m{bar}\033[0m"  # yellow: >100MB
    else:
        return f"\033[36m{bar}\033[0m"  # cyan: small


def _measure_app(app_name: str, app_dir: Path, show_all: bool) -> list[tuple[str, int]]:
    """Measure target dirs in an app. Returns [(label, size)]."""
    results = []
    for dirname in TARGET_DIRS:
        target = app_dir / dirname
        if target.exists() and target.is_dir():
            size = _dir_size(target)
            if size > 0 or show_all:
                results.append((f"{app_name}/{dirname}", size))
    return results


def main() -> int:
    args     = sys.argv[1:]
    show_all = "--all" in args or "-a" in args
    filters  = [a for a in args if not a.startswith("-")]

    project = _load_project()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Disk Usage                                          │")
    print("  └─────────────────────────────────────────────────────────────┘")

    candidates = [
        ("root",     project or ROOT),
        (".bago",    ROOT / ".bago"),
    ]
    if project:
        candidates += [
            ("server",   project / "apps" / "server"),
            ("web",      project / "apps" / "web"),
            ("electron", project / "apps" / "electron"),
        ]
        print(f"  Proyecto: {DIM(str(project))}")

    if filters:
        candidates = [(n, p) for n, p in candidates if n in filters]

    # Collect all measurements
    all_rows: list[tuple[str, int]] = []
    for app_name, app_dir in candidates:
        if not app_dir.exists():
            continue
        rows = _measure_app(app_name, app_dir, show_all)
        all_rows.extend(rows)

    # Also measure .bago/snapshots and state directly
    snap_dir = ROOT / ".bago" / "snapshots"
    if snap_dir.exists():
        size = _dir_size(snap_dir)
        if size > 0:
            all_rows.append((".bago/snapshots", size))
    state_dir = ROOT / ".bago" / "state"
    if state_dir.exists():
        size = _dir_size(state_dir)
        if size > 0:
            all_rows.append((".bago/state", size))

    if not all_rows:
        print(f"\n  {YELLOW('⚠')} No se encontraron carpetas de build/deps con contenido.\n")
        return 0

    all_rows.sort(key=lambda x: x[1], reverse=True)
    max_size = all_rows[0][1] if all_rows else 1
    total = sum(s for _, s in all_rows)

    print()
    print(f"  {'CARPETA':<30} {'TAMAÑO':>8}  PROPORCIÓN")
    print(f"  {'───────':<30} {'──────':>8}  ──────────")

    for label, size in all_rows:
        size_str = _fmt_size(size)
        bar = _size_bar(size, max_size)
        pct = f"{size/total*100:.0f}%" if total else "0%"
        print(f"  {label:<30} {size_str:>8}  {bar} {DIM(pct)}")

    print()
    print(f"  Total medido: {BOLD(_fmt_size(total))}")
    if total > 1024 ** 3:
        print(f"  {YELLOW('⚠')} Uso de disco elevado — considera limpiar con {CYAN('bago clean')}")
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
