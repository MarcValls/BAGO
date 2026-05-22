#!/usr/bin/env python3
"""
bago_diff.py — Muestra cambios entre las dos últimas sesiones BAGO.
# BAGO_DIFF_SESSIONS_IMPLEMENTED

Uso:
  bago diff           → muestra ficheros modificados desde la sesión anterior
  bago diff --list    → lista las sesiones disponibles con timestamps
  bago diff --n N     → compara las últimas N sesiones (por defecto 2)
"""

import re
import subprocess
import sys
from datetime import timezone
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = BAGO_ROOT / "state" / "sessions"

USE_COLOR = sys.stdout.isatty() and "--plain" not in sys.argv


def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t


GREEN  = lambda t: _c("1;32", t)
CYAN   = lambda t: _c("1;36", t)
YELLOW = lambda t: _c("1;33", t)
BOLD   = lambda t: _c("1", t)
DIM    = lambda t: _c("2", t)


def _session_files() -> list[Path]:
    """Devuelve SESSION_CLOSE_*.md ordenados de más antiguo a más reciente."""
    if not STATE_DIR.exists():
        return []
    files = sorted(STATE_DIR.glob("SESSION_CLOSE_*.md"))
    return files


def _extract_timestamp(path: Path) -> str | None:
    """Extrae el timestamp ISO del contenido o del nombre del fichero."""
    try:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text)
        if m:
            return m.group(0)
    except OSError:
        pass
    m = re.search(r"(\d{8})_(\d{6})", path.name)
    if m:
        d, t = m.group(1), m.group(2)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}T{t[:2]}:{t[2:4]}:{t[4:]}"
    return None


def _git_log_files(since: str, until: str | None = None) -> list[str]:
    """Devuelve los ficheros modificados entre dos commits usando git log."""
    repo_root = BAGO_ROOT.parent
    cmd = ["git", "-C", str(repo_root), "log", "--name-only", "--format=", f"--after={since}"]
    if until:
        cmd.append(f"--before={until}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        files = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        # deduplicate preserving order
        seen: set[str] = set()
        unique = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique.append(f)
        return unique
    except Exception:
        return []


def _list_sessions(sessions: list[Path]) -> None:
    print(f"\n  {CYAN(BOLD('bago diff'))} — sesiones disponibles\n")
    for i, s in enumerate(sessions, 1):
        ts = _extract_timestamp(s) or "?"
        print(f"  {DIM(str(i).rjust(2))}. {GREEN(ts)}  {DIM(s.name)}")
    print()


def _show_diff(sessions: list[Path], n: int = 2) -> int:
    if len(sessions) < 2:
        print(f"\n  {YELLOW('⚠')}  Se necesitan al menos 2 sesiones para comparar.\n")
        return 1

    targets = sessions[-n:] if n <= len(sessions) else sessions
    since_ts = _extract_timestamp(targets[0])
    until_ts = _extract_timestamp(targets[-1]) if len(targets) > 1 else None

    if not since_ts:
        print(f"\n  {YELLOW('⚠')}  No se pudo extraer timestamp de {targets[0].name}\n")
        return 1

    files = _git_log_files(since_ts, until_ts)

    ts_from = _extract_timestamp(targets[0]) or targets[0].name
    ts_to   = until_ts or "ahora"
    print(f"\n  {CYAN(BOLD('bago diff'))} — cambios entre sesiones\n")
    print(f"  {DIM('desde')} {GREEN(ts_from)}  {DIM('hasta')} {GREEN(ts_to)}\n")

    if not files:
        print(f"  {DIM('(sin cambios rastreados en git para este rango)')}\n")
        return 0

    # Group by directory prefix
    groups: dict[str, list[str]] = {}
    for f in files:
        prefix = str(Path(f).parent) if "/" in f else "."
        groups.setdefault(prefix, []).append(Path(f).name)

    for prefix, names in sorted(groups.items()):
        print(f"  {BOLD(prefix)}/")
        for name in names:
            print(f"    {DIM('·')} {name}")
    print(f"\n  {DIM(str(len(files)) + ' ficheros modificados')}\n")
    return 0


def main() -> int:
    args = sys.argv[1:]
    list_mode = "--list" in args
    n = 2
    for i, a in enumerate(args):
        if a == "--n" and i + 1 < len(args):
            try:
                n = max(2, int(args[i + 1]))
            except ValueError:
                pass

    sessions = _session_files()
    if not sessions:
        print(f"\n  {YELLOW('⚠')}  No se encontraron sesiones en {STATE_DIR}\n")
        return 1

    if list_mode:
        _list_sessions(sessions)
        return 0

    return _show_diff(sessions, n)


if __name__ == "__main__":
    sys.exit(main())
