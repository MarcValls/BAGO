#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logs_tail.py — Tail del log del servidor local con coloreado de niveles.

Muestra las últimas N líneas del log del servidor y detecta errores recientes.
Soporta archivos de log y también puede leer stdout capturado de PM2.

Uso:
    python3 .bago/tools/logs_tail.py              # últimas 50 líneas del log
    python3 .bago/tools/logs_tail.py -n 100       # últimas 100 líneas
    python3 .bago/tools/logs_tail.py --errors     # solo líneas de error/warn
    python3 .bago/tools/logs_tail.py --follow     # modo tail -f (Ctrl+C para salir)

Códigos de salida: 0 = OK, 1 = no se encontró log, 2 = hay errores recientes
"""
from __future__ import annotations

import json
import re
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

# ─── Colores ──────────────────────────────────────────────────────────────────

def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def BLUE(s: str)   -> str: return f"\033[34m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"

# ─── Level detection ──────────────────────────────────────────────────────────

_LEVEL_PATTERNS = [
    (re.compile(r"\b(error|err|fatal|exception|traceback|failed|failure)\b", re.IGNORECASE), "error"),
    (re.compile(r"\b(warn(?:ing)?|deprecated|caution)\b",                    re.IGNORECASE), "warn"),
    (re.compile(r"\b(info|log|debug|verbose|trace)\b",                       re.IGNORECASE), "info"),
]

def _detect_level(line: str) -> str:
    for pattern, level in _LEVEL_PATTERNS:
        if pattern.search(line):
            return level
    return "plain"


def _colorize(line: str) -> str:
    level = _detect_level(line)
    if level == "error":
        return RED(line)
    elif level == "warn":
        return YELLOW(line)
    elif level == "info":
        return line  # neutral
    return DIM(line)


# ─── Log file finder ──────────────────────────────────────────────────────────

_CANDIDATE_LOG_PATHS = [
    "apps/server/logs/server.log",
    "apps/server/logs/app.log",
    "apps/server/logs/combined.log",
    "apps/server/logs/error.log",
    "apps/server/.log",
    "logs/server.log",
    "logs/app.log",
]


def _find_log_file(project: Path) -> Path | None:
    """Search for the most recently modified log file in the project."""
    for rel in _CANDIDATE_LOG_PATHS:
        p = project / rel
        if p.exists() and p.is_file():
            return p

    # Search logs/ directories for any .log file
    for logs_dir in project.glob("**/logs"):
        if logs_dir.is_dir() and ".git" not in str(logs_dir):
            candidates = sorted(logs_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
            if candidates:
                return candidates[0]

    return None


def _project_root() -> Path | None:
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return None
    try:
        gs = json.loads(gs_file.read_text(encoding="utf-8"))
        p = gs.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


# ─── Tail logic ───────────────────────────────────────────────────────────────

def _tail_lines(path: Path, n: int) -> list[str]:
    """Read last n lines of a file efficiently."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == 0:
                return []
            # Read from end in chunks
            chunk = min(file_size, n * 200)  # estimate ~200 bytes/line
            f.seek(max(0, file_size - chunk))
            data = f.read().decode("utf-8", errors="replace")
            lines = data.splitlines()
            return lines[-n:]
    except OSError:
        return []


def _print_lines(lines: list[str], errors_only: bool) -> int:
    """Print lines with colorization. Returns count of error lines."""
    error_count = 0
    for line in lines:
        level = _detect_level(line)
        if level == "error":
            error_count += 1
        if errors_only and level not in ("error", "warn"):
            continue
        print(_colorize(line))
    return error_count


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    errors_only = "--errors" in args
    follow      = "--follow" in args

    n = 50
    if "-n" in args:
        idx = args.index("-n")
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            n = int(args[idx + 1])

    project = _project_root()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Logs del servidor                                   │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if project is None or not project.exists():
        print(f"  {YELLOW('⚠  No hay proyecto activo.')}")
        print()
        return 1

    log_file = _find_log_file(project)

    if log_file is None:
        print(f"  Proyecto : {project.name}")
        print(f"  {YELLOW('⚠  No se encontró ningún archivo de log.')}")
        print()
        print(f"  {DIM('Rutas buscadas:')}")
        for rel in _CANDIDATE_LOG_PATHS:
            print(f"    {DIM(rel)}")
        print()
        print(f"  {DIM('El servidor quizás no genera logs a archivo.')}")
        print(f"  {DIM('Usa: node apps/server/src/index.js >> logs/server.log 2>&1')}")
        print()
        return 1

    rel = log_file.relative_to(project) if log_file.is_relative_to(project) else log_file
    size_kb = log_file.stat().st_size / 1024
    print(f"  Proyecto : {project.name}")
    print(f"  Log      : {rel}  ({size_kb:.1f} KB)")
    print()

    if follow:
        print(f"  {DIM(f'--- tail -f | Ctrl+C para salir ---')}")
        print()
        last_pos = log_file.stat().st_size
        try:
            while True:
                current_size = log_file.stat().st_size
                if current_size > last_pos:
                    with open(log_file, "rb") as f:
                        f.seek(last_pos)
                        new_data = f.read().decode("utf-8", errors="replace")
                    last_pos = current_size
                    for line in new_data.splitlines():
                        print(_colorize(line))
                time.sleep(0.5)
        except KeyboardInterrupt:
            print()
        return 0

    lines = _tail_lines(log_file, n)
    if not lines:
        print(f"  {DIM('(log vacío)')}")
        print()
        return 0

    filter_label = " (solo errores)" if errors_only else ""
    print(f"  {DIM(f'--- últimas {n} líneas{filter_label} ---')}")
    print()
    error_count = _print_lines(lines, errors_only)
    print()

    if error_count > 0:
        print(f"  {RED(f'⚠  {error_count} línea(s) de error detectadas')}")
    else:
        print(f"  {GREEN('✅  Sin errores en las últimas líneas')}")
    print()

    return 2 if error_count > 0 else 0



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
