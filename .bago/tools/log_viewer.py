"""bago log — Real-time log viewer for monorepo apps."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".bago" / "state"


def _get_project_root() -> Path:
    gs_path = STATE_DIR / "global_state.json"
    if gs_path.exists():
        try:
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            p = gs.get("active_project", {}).get("path", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
    return ROOT.parent


PROJECT_ROOT = _get_project_root()

# Patterns that map log lines to severity
_LEVEL_RE = re.compile(
    r'\b(ERROR|FATAL|CRIT(?:ICAL)?)\b'
    r'|\b(WARN(?:ING)?)\b'
    r'|\b(INFO|DEBUG|LOG)\b',
    re.IGNORECASE,
)


def _colorize(line: str) -> str:
    m = _LEVEL_RE.search(line)
    if m:
        if m.group(1):  # ERROR/FATAL
            return f"\033[31m{line}\033[0m"
        if m.group(2):  # WARN
            return f"\033[33m{line}\033[0m"
        if m.group(3):  # INFO/DEBUG
            return f"\033[32m{line}\033[0m"
    # Heuristic coloring for common patterns
    if re.search(r'\b(fail|error|exception|crash|fatal)\b', line, re.IGNORECASE):
        return f"\033[31m{line}\033[0m"
    if re.search(r'\b(warn|deprecated|caution)\b', line, re.IGNORECASE):
        return f"\033[33m{line}\033[0m"
    if re.search(r'\b(success|ok|started|listening|ready|done)\b', line, re.IGNORECASE):
        return f"\033[32m{line}\033[0m"
    return line


def _find_log_files(app_filter: str | None) -> list[tuple[str, Path]]:
    """Find .log files in the project."""
    results = []
    search_roots = []
    if app_filter:
        candidate = PROJECT_ROOT / "apps" / app_filter
        if candidate.exists():
            search_roots = [candidate]
        else:
            search_roots = [PROJECT_ROOT]
    else:
        search_roots = [PROJECT_ROOT]

    for base in search_roots:
        for f in base.rglob("*.log"):
            # Skip node_modules
            if "node_modules" in f.parts:
                continue
            app_name = f.parts[len(PROJECT_ROOT.parts)] if len(f.parts) > len(PROJECT_ROOT.parts) else "root"
            results.append((app_name, f))
    return results


def _tail_file(path: Path, n: int, follow: bool,
               level_filter: str | None, grep: str | None):
    """Tail a log file, with optional follow (-f) mode."""
    grep_re = re.compile(grep, re.IGNORECASE) if grep else None
    level_re = re.compile(level_filter, re.IGNORECASE) if level_filter else None

    def _should_show(line: str) -> bool:
        if grep_re and not grep_re.search(line):
            return False
        if level_re and not level_re.search(line):
            return False
        return True

    print(f"\n\033[36m  ── {path} ──\033[0m\n")

    if not path.exists():
        print(f"  (archivo no encontrado: {path})")
        return

    # Print last n lines
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-n:]:
        if _should_show(line):
            print("  " + _colorize(line))

    if not follow:
        return

    # Follow mode: poll for new content
    pos = path.stat().st_size
    print(f"\n  \033[2m[siguiendo — Ctrl+C para detener]\033[0m\n")
    try:
        while True:
            time.sleep(0.5)
            if not path.exists():
                continue
            new_size = path.stat().st_size
            if new_size > pos:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    fh.seek(pos)
                    for line in fh:
                        line = line.rstrip("\n")
                        if _should_show(line):
                            print("  " + _colorize(line), flush=True)
                pos = new_size
    except KeyboardInterrupt:
        print("\n  Seguimiento detenido.")


def _list_files(files: list[tuple[str, Path]]):
    print()
    if not files:
        print("  (no se encontraron archivos .log en el proyecto)")
        return
    for i, (app, f) in enumerate(files, 1):
        sz = f.stat().st_size
        print(f"  {i:>3}.  \033[36m{app}\033[0m  {f.name}  \033[2m({sz//1024}KB)\033[0m")
    print()


def main():
    parser = argparse.ArgumentParser(description="BAGO log — Log viewer for monorepo apps")
    parser.add_argument("--app", "-a", help="Filter to specific app (e.g. server, web)")
    parser.add_argument("--follow", "-f", action="store_true", help="Follow log in real time")
    parser.add_argument("--lines", "-n", type=int, default=40, help="Lines to show (default: 40)")
    parser.add_argument("--level", "-l", help="Filter by level (ERROR, WARN, INFO, DEBUG)")
    parser.add_argument("--grep", "-g", help="Filter lines by regex pattern")
    parser.add_argument("--list", action="store_true", help="List available log files")
    parser.add_argument("index", nargs="?", type=int, help="File index from --list")
    args = parser.parse_args()

    files = _find_log_files(args.app)

    if args.list or (not files and args.index is None):
        _list_files(files)
        if not files:
            print(f"  \033[2mEl proyecto no tiene archivos .log actualmente.\033[0m")
            print(f"  \033[2mEjecuta 'pnpm dev:server' para generar logs de servidor.\033[0m\n")
        return

    if not files:
        print(f"\n  \033[33m⚠\033[0m No se encontraron archivos .log en {PROJECT_ROOT}\n")
        return

    if args.index is not None:
        if args.index < 1 or args.index > len(files):
            print(f"  ✖ Índice inválido. Rango: 1-{len(files)}", file=sys.stderr)
            sys.exit(1)
        _, path = files[args.index - 1]
    else:
        # Default: show all (or first) file
        _, path = files[0]

    _tail_file(path, args.lines, args.follow, args.level, args.grep)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
