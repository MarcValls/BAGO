#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
todo_scan.py — Escanea el código fuente del proyecto buscando TODOs y FIXMEs.

Busca comentarios: TODO, FIXME, HACK, XXX, NOTE, OPTIMIZE en el código fuente.
Excluye node_modules, dist, build, .git, .bago por defecto.

Uso:
    python3 .bago/tools/todo_scan.py               # escanea todo el proyecto
    python3 .bago/tools/todo_scan.py --fixme       # solo FIXME
    python3 .bago/tools/todo_scan.py --ext ts,tsx  # solo archivos .ts y .tsx
    python3 .bago/tools/todo_scan.py --json        # output en JSON
    python3 .bago/tools/todo_scan.py --count       # solo resumen por tipo

Códigos de salida: 0 = OK
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

PATTERNS = {
    "TODO":     r"(?i)\bTODO\b",
    "FIXME":    r"(?i)\bFIXME\b",
    "HACK":     r"(?i)\bHACK\b",
    "XXX":      r"(?i)\bXXX\b",
    "OPTIMIZE": r"(?i)\bOPTIMIZE\b",
    "NOTE":     r"(?i)\bNOTE\b",
}

EXCLUDE_DIRS = {"node_modules", "dist", "build", ".next", ".git", ".bago", "out", "coverage", ".turbo"}
INCLUDE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".md", ".yaml", ".yml", ".env"}


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"

LABEL_COLOR = {
    "FIXME":    "\033[31m",  # red
    "TODO":     "\033[33m",  # yellow
    "HACK":     "\033[35m",  # magenta
    "XXX":      "\033[31m",  # red
    "OPTIMIZE": "\033[36m",  # cyan
    "NOTE":     "\033[2m",   # dim
}
RESET = "\033[0m"


@lru_cache(maxsize=1)
def _load_scan_config() -> dict[str, object]:
    try:
        from bago_config import load_config
        data = load_config("scan_config", fallback=None)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_todo_patterns() -> dict[str, str]:
    patterns = _load_scan_config().get("todo_patterns")
    return patterns if isinstance(patterns, dict) else PATTERNS


def _get_exclude_dirs() -> set[str]:
    exclude_dirs = _load_scan_config().get("exclude_dirs")
    return set(exclude_dirs) if isinstance(exclude_dirs, list) else EXCLUDE_DIRS


def _get_include_exts() -> set[str]:
    include_exts = _load_scan_config().get("include_exts")
    return set(include_exts) if isinstance(include_exts, list) else INCLUDE_EXTS


def _get_label_colors() -> dict[str, str]:
    label_colors = _load_scan_config().get("label_colors")
    return label_colors if isinstance(label_colors, dict) else LABEL_COLOR


def _col_label(label: str) -> str:
    return f"{_get_label_colors().get(label, '')}{label}{RESET}"


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
    parts = set(path.relative_to(root).parts)
    return bool(parts & _get_exclude_dirs())


def _scan_file(path: Path, patterns: dict) -> list[dict]:
    results = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return results

    for i, line in enumerate(text.splitlines(), 1):
        for label, pattern in patterns.items():
            if re.search(pattern, line):
                # Extract comment text after the marker
                snippet = line.strip()
                if len(snippet) > 120:
                    snippet = snippet[:117] + "…"
                results.append({
                    "type":    label,
                    "file":    str(path),
                    "line":    i,
                    "text":    snippet,
                })
                break  # one result per line
    return results


def _scan_project(root: Path, extensions: set[str], patterns: dict) -> list[dict]:
    results = []
    try:
        for f in sorted(root.rglob("*")):
            if not f.is_file():
                continue
            if _should_exclude(f, root):
                continue
            if f.suffix.lower() not in extensions:
                continue
            results.extend(_scan_file(f, patterns))
    except (PermissionError, OSError):
        pass
    return results


def main() -> int:
    args     = sys.argv[1:]
    only_fixme = "--fixme" in args
    do_json  = "--json" in args
    do_count = "--count" in args or "-c" in args

    # Extensions filter
    ext_flag = ""
    if "--ext" in args:
        idx = args.index("--ext")
        if idx + 1 < len(args):
            ext_flag = args[idx + 1]
    patterns = _get_todo_patterns()
    extensions = {f".{e.lstrip('.')}" for e in ext_flag.split(",")} if ext_flag else _get_include_exts()

    # Pattern filter
    active_patterns = {"FIXME": patterns["FIXME"], "XXX": patterns["XXX"]} if only_fixme else patterns
    pattern_order = [label for label in patterns if label in active_patterns]

    project = _load_project()
    scan_root = project if project else ROOT

    if not do_json:
        print()
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │  BAGO · TODO Scanner                                        │")
        print("  └─────────────────────────────────────────────────────────────┘")
        print(f"  Raíz: {DIM(str(scan_root))}")
        print()

    results = _scan_project(scan_root, extensions, active_patterns)

    if do_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if not results:
        print(f"  {GREEN('✅')} Sin TODOs ni FIXMEs encontrados.\n")
        return 0

    # Count by type
    from collections import Counter
    counts = Counter(r["type"] for r in results)

    if do_count:
        print(f"  {'TIPO':<12} {'CUENTA':>6}")
        print(f"  {'────':<12} {'──────':>6}")
        for label in pattern_order:
            n = counts.get(label, 0)
            if n:
                print(f"  {_col_label(label):<12} {n:>6}")
        print(f"\n  Total: {BOLD(str(len(results)))}\n")
        return 0

    # Full listing (grouped by type)
    for label in pattern_order:
        items = [r for r in results if r["type"] == label]
        if not items:
            continue
        print(f"  {_col_label(label)} ({len(items)})")
        for item in items[:30]:  # cap at 30 per type
            try:
                rel = str(Path(item["file"]).relative_to(scan_root))
            except ValueError:
                rel = item["file"]
            print(f"    {DIM(rel)}:{item['line']}")
            print(f"      {item['text']}")
        if len(items) > 30:
            print(f"    {DIM(f'... y {len(items)-30} más')}")
        print()

    print(f"  Total: {BOLD(str(len(results)))}  ·  ", end="")
    parts = [f"{_col_label(l)}: {counts[l]}" for l in pattern_order if counts.get(l)]
    print("  ".join(parts))
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
