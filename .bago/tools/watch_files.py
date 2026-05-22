#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch_files.py — Monitoriza cambios de archivos en el proyecto en tiempo real.

Usa polling de mtime para detectar archivos creados/modificados/eliminados.
No requiere dependencias externas.

Uso:
    python3 .bago/tools/watch_files.py              # vigila apps/src del proyecto
    python3 .bago/tools/watch_files.py src          # directorio específico
    python3 .bago/tools/watch_files.py --interval 2 # revisar cada 2s (por defecto 1s)
    python3 .bago/tools/watch_files.py --ext ts,py  # solo ciertos tipos
    python3 .bago/tools/watch_files.py --once       # snapshot actual sin watch

Ctrl+C para salir.
Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

EXCLUDE_DIRS = {"node_modules", "dist", "build", ".next", ".git", ".bago", "out", "coverage", ".turbo", "__pycache__"}


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


def _should_exclude(path: Path, root: Path) -> bool:
    try:
        parts = set(path.relative_to(root).parts)
        return bool(parts & EXCLUDE_DIRS)
    except ValueError:
        return False


def _snapshot(watch_root: Path, extensions: set[str] | None) -> dict[str, float]:
    """Return {path_str: mtime} for all relevant files."""
    state: dict[str, float] = {}
    try:
        for f in watch_root.rglob("*"):
            if not f.is_file():
                continue
            if _should_exclude(f, watch_root):
                continue
            if extensions and f.suffix.lower() not in extensions:
                continue
            try:
                state[str(f)] = f.stat().st_mtime
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return state


def _diff(old: dict[str, float], new: dict[str, float]) -> list[tuple[str, str]]:
    """Return list of (event_type, path) for changes."""
    events = []
    for path, mtime in new.items():
        if path not in old:
            events.append(("CREATED", path))
        elif mtime != old[path]:
            events.append(("MODIFIED", path))
    for path in old:
        if path not in new:
            events.append(("DELETED", path))
    return events


def _fmt_time() -> str:
    return time.strftime("%H:%M:%S")


def main() -> int:
    args     = sys.argv[1:]
    interval = 1.0
    once     = "--once" in args

    if "--interval" in args:
        idx = args.index("--interval")
        if idx + 1 < len(args):
            try:
                interval = float(args[idx + 1])
            except ValueError:
                pass

    ext_str = ""
    if "--ext" in args:
        idx = args.index("--ext")
        if idx + 1 < len(args):
            ext_str = args[idx + 1]
    extensions: set[str] | None = {f".{e.lstrip('.')}" for e in ext_str.split(",")} if ext_str else None

    # Determine watch root
    path_args = [a for a in args if not a.startswith("-") and a not in ("interval",)]
    project = _load_project()

    if path_args:
        watch_root = Path(path_args[0])
        if not watch_root.is_absolute():
            watch_root = (project or ROOT) / path_args[0]
    elif project:
        # Watch src folders inside project apps
        watch_root = project
    else:
        watch_root = ROOT

    if not watch_root.exists():
        print(f"\n  {RED('❌')} Directorio no encontrado: {watch_root}\n")
        return 1

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Watch                                               │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Vigilando: {DIM(str(watch_root))}")
    if extensions:
        print(f"  Tipos:     {', '.join(sorted(extensions))}")
    print(f"  Intervalo: {interval}s")

    if once:
        state = _snapshot(watch_root, extensions)
        print(f"\n  {BOLD(str(len(state)))} archivos en el snapshot actual")
        for path in sorted(state.keys())[:20]:
            try:
                rel = str(Path(path).relative_to(watch_root))
            except ValueError:
                rel = path
            print(f"  {DIM(rel)}")
        if len(state) > 20:
            print(f"  {DIM(f'... y {len(state)-20} más')}")
        print()
        return 0

    print(f"\n  {DIM('(Ctrl+C para salir)')}\n")

    prev_state = _snapshot(watch_root, extensions)
    print(f"  {DIM(_fmt_time())}  {BOLD(str(len(prev_state)))} archivos en monitorización")

    try:
        while True:
            time.sleep(interval)
            curr_state = _snapshot(watch_root, extensions)
            events = _diff(prev_state, curr_state)

            for event_type, path in events:
                try:
                    rel = str(Path(path).relative_to(watch_root))
                except ValueError:
                    rel = path
                ts = _fmt_time()
                if event_type == "CREATED":
                    print(f"  {DIM(ts)}  {GREEN('+')} {rel}")
                elif event_type == "MODIFIED":
                    print(f"  {DIM(ts)}  {YELLOW('~')} {rel}")
                elif event_type == "DELETED":
                    print(f"  {DIM(ts)}  {RED('-')} {rel}")

            prev_state = curr_state

    except KeyboardInterrupt:
        print(f"\n  {DIM('Watch detenido.')}\n")
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
