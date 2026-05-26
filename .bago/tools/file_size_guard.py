from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

"""file_size_guard.py — Detecta monolitos candidatos a dividir en .bago/tools/."""

import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
WARN_LIMIT = 600
CRIT_LIMIT = 800

# Archivos legítimamente grandes excluidos del scanner
_EXCLUDE: frozenset[str] = frozenset({
    "integration_tests.py",
    "_registry_entries.py",
    "emit_ideas.py",
    "bago_menu_loaders.py",
})


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def scan() -> dict:
    """Devuelve {total, clean, warn: list[tuple[name,lines]], crit: list[tuple[name,lines]]}."""
    warn: list[tuple[str, int]] = []
    crit: list[tuple[str, int]] = []
    total = 0
    for path in sorted(TOOLS_DIR.rglob("*.py")):
        if path.name.startswith("_") and path.name not in ("__main__.py",):
            pass  # include underscore files except excluded
        if path.name in _EXCLUDE:
            continue
        lines = _count_lines(path)
        total += 1
        if lines >= CRIT_LIMIT:
            crit.append((path.name, lines))
        elif lines >= WARN_LIMIT:
            warn.append((path.name, lines))
    clean = total - len(warn) - len(crit)
    return {"total": total, "clean": clean, "warn": warn, "crit": crit}


def summary_line() -> str:
    r = scan()
    return (f"Anti-monolito: {r['total']} archivos · {r['clean']} OK · "
            f"{len(r['warn'])} WARN · {len(r['crit'])} CRIT")


def _print_text(r: dict) -> None:
    print(f"  .bago/tools/ — monolito candidates (WARN>{WARN_LIMIT} / CRIT>{CRIT_LIMIT} líneas)")
    if not r["warn"] and not r["crit"]:
        print("  GO — no se detectaron monolitos")
        return
    for name, lines in r["crit"]:
        print(f"  CRIT {name}: {lines} líneas")
    for name, lines in r["warn"]:
        print(f"  WARN {name}: {lines} líneas")


def _self_test() -> None:
    r = scan()
    assert isinstance(r, dict), "scan() debe retornar dict"
    assert "total" in r and "warn" in r and "crit" in r and "clean" in r
    s = summary_line()
    assert "Anti-monolito" in s
    assert _EXCLUDE  # set no vacío
    print(f"  3/3 tests pasaron  ({r['total']} archivos, {len(r['crit'])} CRIT, {len(r['warn'])} WARN)")


def main() -> int:
    args = sys.argv[1:]
    if "--test" in args:
        _self_test()
        return 0
    r = scan()
    if "--json" in args:
        print(json.dumps({
            "total": r["total"], "clean": r["clean"],
            "warn": [{"file": n, "lines": l} for n, l in r["warn"]],
            "crit": [{"file": n, "lines": l} for n, l in r["crit"]],
        }, indent=2, ensure_ascii=False))
        return 0
    if "--summary" in args:
        print(summary_line())
        return 0
    _print_text(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
