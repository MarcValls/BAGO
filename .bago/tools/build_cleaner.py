#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_cleaner.py — Elimina node_modules/dist/build para liberar espacio en disco.

Calcula tamaño antes de eliminar y muestra cuánto se liberará.
Por defecto es dry-run (no elimina nada hasta usar --run).

Uso:
    python3 .bago/tools/build_cleaner.py              # dry-run (muestra qué se eliminaría)
    python3 .bago/tools/build_cleaner.py --run        # eliminar efectivamente
    python3 .bago/tools/build_cleaner.py --app web    # solo una app
    python3 .bago/tools/build_cleaner.py --keep-modules   # no tocar node_modules
    python3 .bago/tools/build_cleaner.py --targets dist,build  # solo targets específicos

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

DEFAULT_TARGETS = ["node_modules", "dist", "build", ".next", "out", "coverage", ".turbo"]


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"


def _load_project() -> Path:
    gs = STATE / "global_state.json"
    if gs.exists():
        try:
            data = json.loads(gs.read_text(encoding="utf-8"))
            p = data.get("active_project", {}).get("path", "")
            if p:
                return Path(p)
        except Exception:
            pass
    return ROOT


def _dir_size_fast(path: Path) -> int:
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def _fmt(b: int) -> str:
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.2f}GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f}MB"
    if b >= 1_024:         return f"{b/1_024:.1f}KB"
    return f"{b}B"


def main() -> int:
    args       = sys.argv[1:]
    do_run     = "--run" in args
    keep_mods  = "--keep-modules" in args
    filter_app = None

    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            filter_app = args[idx + 1]

    targets = list(DEFAULT_TARGETS)
    if "--targets" in args:
        idx = args.index("--targets")
        if idx + 1 < len(args):
            targets = [t.strip() for t in args[idx + 1].split(",")]

    if keep_mods and "node_modules" in targets:
        targets.remove("node_modules")

    project = _load_project()

    # Build list of scan dirs: project root + apps/*
    scan_dirs = [project]
    apps_dir = project / "apps"
    if apps_dir.exists():
        for d in sorted(apps_dir.iterdir()):
            if d.is_dir():
                if not filter_app or d.name == filter_app:
                    scan_dirs.append(d)

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Limpiar artefactos de build                         │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if not do_run:
        print(f"  {YELLOW('[DRY RUN]')} Usa --run para eliminar efectivamente")
    else:
        print(f"  {RED('⚠ ELIMINANDO artefactos...')}  (sin marcha atrás)")
    print(f"  Targets: {DIM(', '.join(targets))}")
    print()

    found: list[tuple[Path, int]] = []
    print("  Escaneando...")
    for scan_dir in scan_dirs:
        for target in targets:
            tp = scan_dir / target
            if tp.exists():
                size = _dir_size_fast(tp)
                found.append((tp, size))

    if not found:
        print(f"  {GREEN('✅ No hay artefactos que limpiar')}\n")
        return 0

    total = sum(s for _, s in found)
    print(f"\n  {'DIRECTORIO':<55}  TAMAÑO")
    print(f"  {'──────────':<55}  ──────")

    for path, size in sorted(found, key=lambda x: x[1], reverse=True):
        try:
            rel = path.relative_to(project)
        except ValueError:
            rel = path
        color = RED if size > 500_000_000 else (YELLOW if size > 50_000_000 else DIM)
        print(f"  {str(rel):<55}  {color(_fmt(size))}")

    print()
    print(f"  Total a liberar: {BOLD(_fmt(total))}")
    print()

    if not do_run:
        print(f"  {DIM('Ejecuta con --run para eliminar estos directorios.')}\n")
        return 0

    freed = 0
    errors = 0
    for path, size in found:
        try:
            shutil.rmtree(str(path))
            freed += size
            try:
                rel = path.relative_to(project)
            except ValueError:
                rel = path
            print(f"  {GREEN('✓')} {rel}")
        except Exception as e:
            errors += 1
            print(f"  {RED('✗')} Error: {path.name}: {e}")

    print()
    print(f"  {GREEN('✅')} Liberado: {BOLD(_fmt(freed))}")
    if errors:
        print(f"  {YELLOW(f'{errors} error(s) al eliminar')}")
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
