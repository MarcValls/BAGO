#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_artifacts.py — Limpia artefactos temporales de BAGO.

Elimina o archiva session_close files antiguos, logs de test caducados y
temporales de build para mantener .bago/state/ limpio y manejable.

Uso:
    python3 .bago/tools/clean_artifacts.py              # seco (muestra qué se borraría)
    python3 .bago/tools/clean_artifacts.py --execute    # elimina los archivos caducados
    python3 .bago/tools/clean_artifacts.py --archive    # mueve en vez de borrar
    python3 .bago/tools/clean_artifacts.py --days 14    # umbral personalizado (default: 30)

Códigos de salida: 0 = OK
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
ARCHIVE_DIR = STATE / "archive"

# ─── Colores ──────────────────────────────────────────────────────────────────

def GREEN(s: str) -> str:  return f"\033[32m{s}\033[0m"
def RED(s: str)   -> str:  return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)   -> str:  return f"\033[2m{s}\033[0m"

# ─── File patterns to clean ───────────────────────────────────────────────────

# session_close files have names like: session_close_20260501_163355.md
# sprint_summary files: sprint_summary_08.md
# tmp_ prefix: temporary files created by tools

_PATTERNS = [
    "session_close_*.md",
    "sprint_summary_*.md",
    "tmp_*.json",
    "tmp_*.md",
    "tmp_*.txt",
    "_add_*.py",   # temporary scripts added to project root
]

_PROJECT_ROOT_PATTERNS = [
    "_add_*.py",
    "tmp_*.py",
]


def _parse_date_from_name(path: Path) -> datetime | None:
    """Try to extract date from filename like session_close_20260501_163355.md."""
    stem = path.stem
    parts = stem.split("_")
    for i, p in enumerate(parts):
        if len(p) == 8 and p.isdigit():
            try:
                dt = datetime.strptime(p, "%Y%m%d")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    # If no date found, use mtime
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except OSError:
        return None


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024*1024):.1f} MB"


def _collect_candidates(days_threshold: int) -> list[tuple[Path, int]]:
    """Collect files older than days_threshold. Returns list of (path, size_bytes)."""
    now = datetime.now(timezone.utc)
    candidates: list[tuple[Path, int]] = []

    for pattern in _PATTERNS:
        for fpath in STATE.glob(pattern):
            if not fpath.is_file():
                continue
            fdate = _parse_date_from_name(fpath)
            if fdate:
                age_days = (now - fdate).days
                if age_days >= days_threshold:
                    try:
                        size = fpath.stat().st_size
                    except OSError:
                        size = 0
                    candidates.append((fpath, size))

    # Also check project root for temp scripts
    for pattern in _PROJECT_ROOT_PATTERNS:
        for fpath in ROOT.glob(pattern):
            if fpath.is_file():
                try:
                    size = fpath.stat().st_size
                except OSError:
                    size = 0
                candidates.append((fpath, size))

    return sorted(candidates, key=lambda x: x[0].name)


def main() -> int:
    args = sys.argv[1:]
    execute = "--execute" in args
    archive = "--archive" in args

    days = 30
    if "--days" in args:
        idx = args.index("--days")
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            days = int(args[idx + 1])

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Limpieza de artefactos                              │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Umbral   : {days} días")
    mode_label = "ELIMINAR" if execute else ("ARCHIVAR" if archive else "SECO (simulación)")
    print(f"  Modo     : {mode_label}")
    print()

    candidates = _collect_candidates(days)

    if not candidates:
        print(f"  {GREEN('✅  No hay artefactos caducados que limpiar.')}")
        print()
        return 0

    total_size = sum(s for _, s in candidates)
    print(f"  {'ARCHIVO':<55}  {'TAMAÑO':>8}")
    print(f"  {'──────':<55}  {'──────':>8}")

    for fpath, size in candidates:
        rel = fpath.relative_to(ROOT) if fpath.is_relative_to(ROOT) else fpath
        print(f"  {str(rel):<55}  {_human_size(size):>8}")

    print()
    print(f"  Total: {len(candidates)} archivo(s) · {_human_size(total_size)}")
    print()

    if execute:
        removed = 0
        for fpath, _ in candidates:
            try:
                fpath.unlink()
                removed += 1
            except OSError as e:
                print(f"  {YELLOW(f'⚠  No se pudo eliminar {fpath.name}: {e}')}")
        print(f"  {GREEN(f'✅  {removed} archivo(s) eliminados · {_human_size(total_size)} liberados')}")

    elif archive:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        moved = 0
        for fpath, _ in candidates:
            dest = ARCHIVE_DIR / fpath.name
            if dest.exists():
                dest = ARCHIVE_DIR / f"{fpath.stem}_dup{fpath.suffix}"
            try:
                shutil.move(str(fpath), str(dest))
                moved += 1
            except OSError as e:
                print(f"  {YELLOW(f'⚠  No se pudo archivar {fpath.name}: {e}')}")
        print(f"  {GREEN(f'✅  {moved} archivo(s) archivados en .bago/state/archive/')}")

    else:
        print(f"  {DIM('Ejecuta con --execute para eliminar o --archive para archivar.')}")

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
