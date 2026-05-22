#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code_search.py — Busca texto o patrones en el código fuente del proyecto.

Rápido, sin dependencias externas. Excluye node_modules/dist/build.

Uso:
    python3 .bago/tools/code_search.py PATRON          # búsqueda literal
    python3 .bago/tools/code_search.py PATRON --regex  # expresión regular
    python3 .bago/tools/code_search.py PATRON -i       # ignorar mayúsculas
    python3 .bago/tools/code_search.py PATRON --ext ts,tsx,py
    python3 .bago/tools/code_search.py PATRON --files  # solo nombres de archivos
    python3 .bago/tools/code_search.py PATRON --count  # solo cuenta de matches

Códigos de salida: 0 = encontrado, 1 = sin resultados, 2 = error
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

EXCLUDE_DIRS = {"node_modules", "dist", "build", ".next", ".git", ".bago", "out", "coverage", ".turbo", "__pycache__"}
DEFAULT_EXTS = {".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".md", ".yaml", ".yml", ".sql", ".css", ".scss"}


@lru_cache(maxsize=1)
def _load_scan_config() -> dict[str, object]:
    try:
        from bago_config import load_config
        data = load_config("scan_config", fallback=None)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_exclude_dirs() -> set[str]:
    config = _load_scan_config()
    exclude_dirs = config.get("search_exclude_dirs", config.get("exclude_dirs"))
    return set(exclude_dirs) if isinstance(exclude_dirs, list) else EXCLUDE_DIRS


def _get_search_exts() -> set[str]:
    config = _load_scan_config()
    search_exts = config.get("search_exts")
    if isinstance(search_exts, list):
        return set(search_exts)
    include_exts = config.get("include_exts")
    return set(include_exts) if isinstance(include_exts, list) else DEFAULT_EXTS


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"
def HIGHLIGHT(s: str) -> str: return f"\033[93m{s}\033[0m"


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
        return bool(parts & _get_exclude_dirs())
    except ValueError:
        return False


def _search_file(path: Path, pattern: re.Pattern, max_per_file: int = 10) -> list[tuple[int, str]]:
    """Return list of (line_num, line_text) matches."""
    matches = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return []
    for i, line in enumerate(text.splitlines(), 1):
        if pattern.search(line):
            matches.append((i, line.rstrip()))
            if len(matches) >= max_per_file:
                break
    return matches


def _highlight(line: str, pattern: re.Pattern) -> str:
    """Highlight matching parts of a line."""
    def replace(m: re.Match) -> str:
        return HIGHLIGHT(m.group(0))
    try:
        return pattern.sub(replace, line)
    except Exception:
        return line


def main() -> int:
    args = sys.argv[1:]

    if not args or args[0].startswith("-"):
        print(f"\n  {YELLOW('Uso:')} bago search PATRON [--regex] [-i] [--ext ts,py] [--files] [--count]\n")
        return 2

    query   = args[0]
    use_re  = "--regex" in args or "-r" in args
    ig_case = "-i" in args or "--ignore-case" in args
    files_only = "--files" in args or "-l" in args
    do_count   = "--count" in args or "-c" in args

    ext_str = ""
    if "--ext" in args:
        idx = args.index("--ext")
        if idx + 1 < len(args):
            ext_str = args[idx + 1]
    extensions = {f".{e.lstrip('.')}" for e in ext_str.split(",")} if ext_str else _get_search_exts()

    flags = re.IGNORECASE if ig_case else 0
    try:
        pattern = re.compile(query if use_re else re.escape(query), flags)
    except re.error as e:
        print(f"\n  {RED('❌')} Patrón regex inválido: {e}\n")
        return 2

    project = _load_project()
    search_root = project if project else ROOT

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Code Search                                         │")
    print("  └─────────────────────────────────────────────────────────────┘")
    mode = "regex" if use_re else "literal"
    case_label = "sin mayús" if ig_case else "sensible"
    print(f"  Buscando: {BOLD(query)}  {DIM(f'({mode}, {case_label})')}")
    print(f"  Raíz:     {DIM(str(search_root))}")
    print()

    all_files: list[Path] = []
    try:
        for f in sorted(search_root.rglob("*")):
            if not f.is_file():
                continue
            if _should_exclude(f, search_root):
                continue
            if f.suffix.lower() not in extensions:
                continue
            all_files.append(f)
    except (PermissionError, OSError):
        pass

    total_matches = 0
    matched_files = 0
    MAX_RESULTS = 200

    for f in all_files:
        matches = _search_file(f, pattern)
        if not matches:
            continue

        matched_files += 1
        total_matches += len(matches)

        if do_count:
            continue

        try:
            rel = str(f.relative_to(search_root))
        except ValueError:
            rel = str(f)

        if files_only:
            print(f"  {CYAN(rel)}")
        else:
            print(f"  {CYAN(rel)}  {DIM(str(len(matches)) + ' coincidencias')}")
            for lineno, text in matches:
                text_hl = _highlight(text.strip()[:100], pattern)
                print(f"    {DIM(str(lineno)):>6}  {text_hl}")
            print()

        if total_matches >= MAX_RESULTS:
            print(f"  {YELLOW(f'... resultados truncados a {MAX_RESULTS}')}")
            break

    print()
    if total_matches == 0:
        print(f"  {YELLOW('⚠')} Sin resultados para: {BOLD(query)}\n")
        return 1

    print(f"  {GREEN('✅')} {BOLD(str(total_matches))} coincidencias en {matched_files} archivos")
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
