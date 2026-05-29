#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_call_search.py — Busca llamadas a funciones, métodos, clases o APIs
según el contexto del archivo.

Uso:
    python .bago/tools/bago_call_search.py <nombre_funcion> [directorio] [opciones]

Opciones:
    --class             Busca definiciones de clase
    --function          Busca definiciones de función (default)
    --method            Busca métodos dentro de clases
    --call              Busca llamadas (invocaciones) en lugar de definiciones
    --import            Busca importaciones / require / include
    --decorator         Busca decoradores que envuelven la función
    --assign            Busca asignaciones a la variable/función
    --regex             Trata el nombre como expresión regular
    --ext EXT1,EXT2     Extensiones a escanear (default: py,ts,tsx,js,jsx)
    --context C         Líneas de contexto alrededor del match (default: 3)
    --json              Salida JSON
    --files             Solo archivos que contienen matches
    --summary           Resumen por archivo: cuántas llamadas de cada tipo
    --depth N           Profundidad máxima de análisis (default: 5)

Códigos de salida: 0 = encontrado, 1 = sin resultados, 2 = error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

from bago_utils import get_repo_root

ROOT = get_repo_root()

EXCLUDE_DIRS = {"node_modules", "dist", "build", ".next", ".git", ".bago", "out",
                "coverage", ".turbo", "__pycache__", ".pytest_cache", ".mypy_cache",
                "venv", ".venv", "env", ".env"}

DEFAULT_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".php", ".rb", ".java", ".go", ".rs"}

# ── Pattern builders per language ──
_PATTERNS = {
    "py": {
        "class": r"^\s*class\s+{name}\b",
        "function": r"^\s*def\s+{name}\b",
        "method": r"^\s*def\s+{name}\b",
        "call": r"\b{name}\s*\(",
        "import": r"(^\s*from\s+\S+\s+import\s+.*\b{name}\b|^\s*import\s+.*\b{name}\b)",
        "decorator": r"^\s*@{name}\b",
        "assign": r"\b{name}\s*=",
    },
    "ts": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\bfunction\s+{name}\b",
        "method": r"\b{name}\s*\([^)]*\)\s*[:\{]",
        "call": r"\b{name}\s*\(",
        "import": r"(import\s+.*\b{name}\b\s+from|require\s*\(\s*['\"].*?{name}.*?['\"]\s*\)|from\s+.*?\s+import\s+.*?{name})",
        "decorator": r"@{name}\b",
        "assign": r"\b(?:const|let|var)?\s*{name}\s*[=:]",
    },
    "js": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\bfunction\s+{name}\b|\b{name}\s*=\s*(?:async\s*)?\(",
        "method": r"\b{name}\s*\([^)]*\)\s*[:\{]",
        "call": r"\b{name}\s*\(",
        "import": r"(import\s+.*\b{name}\b\s+from|require\s*\(\s*['\"].*?{name}.*?['\"]\s*\))",
        "decorator": r"@{name}\b",
        "assign": r"\b(?:const|let|var)?\s*{name}\s*[=:]",
    },
    "tsx": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\bfunction\s+{name}\b|\b{name}\s*=\s*(?:async\s*)?\(",
        "method": r"\b{name}\s*\([^)]*\)\s*[:\{]",
        "call": r"\b{name}\s*\(",
        "import": r"(import\s+.*\b{name}\b\s+from|require\s*\(\s*['\"].*?{name}.*?['\"]\s*\))",
        "decorator": r"@{name}\b",
        "assign": r"\b(?:const|let|var)?\s*{name}\s*[=:]",
    },
    "jsx": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\bfunction\s+{name}\b|\b{name}\s*=\s*(?:async\s*)?\(",
        "method": r"\b{name}\s*\([^)]*\)\s*[:\{]",
        "call": r"\b{name}\s*\(",
        "import": r"(import\s+.*\b{name}\b\s+from|require\s*\(\s*['\"].*?{name}.*?['\"]\s*\))",
        "decorator": r"@{name}\b",
        "assign": r"\b(?:const|let|var)?\s*{name}\s*[=:]",
    },
    "php": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\bfunction\s+{name}\b",
        "method": r"\bfunction\s+{name}\b",
        "call": r"\b{name}\s*\(",
        "import": r"(include|require|use)\s*.*?{name}",
        "decorator": r"@{name}\b",
        "assign": r"\${name}\s*=",
    },
    "java": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\b(?:public|private|protected|static|\s)*[\w<>\[\]]+\s+{name}\s*\(",
        "method": r"\b(?:public|private|protected|static|\s)*[\w<>\[\]]+\s+{name}\s*\(",
        "call": r"\b{name}\s*\(",
        "import": r"import\s+.*?{name}",
        "decorator": r"@{name}\b",
        "assign": r"\b{name}\s*=",
    },
    "go": {
        "class": r"\btype\s+{name}\s+struct\b",
        "function": r"^\s*func\s+{name}\b",
        "method": r"^\s*func\s+\([^)]*\)\s*{name}\b",
        "call": r"\b{name}\s*\(",
        "import": r"import\s*\(\s*.*?{name}|import\s+['\"].*?{name}.*?['\"]",
        "decorator": r"@{name}\b",
        "assign": r"\b{name}\s*:=|\b{name}\s*=",
    },
    "rs": {
        "class": r"\bstruct\s+{name}\b",
        "function": r"\bfn\s+{name}\b",
        "method": r"\bimpl\s+.*?\bfor\s+.*?\{\s*\n\s*fn\s+{name}\b",
        "call": r"\b{name}\s*\(",
        "import": r"use\s+.*?{name}|extern\s+crate\s+{name}",
        "decorator": r"#{name}\b",
        "assign": r"\b(?:let|mut|const)?\s*{name}\s*=",
    },
    "rb": {
        "class": r"\bclass\s+{name}\b",
        "function": r"\bdef\s+{name}\b",
        "method": r"\bdef\s+{name}\b",
        "call": r"\b{name}\b",
        "import": r"(require|load|include).*?{name}",
        "decorator": r"@{name}\b",
        "assign": r"@{name}\s*=|{name}\s*=",
    },
}

def _color(code: int, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"

GREEN = lambda s: _color(32, s)
YELLOW = lambda s: _color(33, s)
CYAN = lambda s: _color(36, s)
DIM = lambda s: _color(2, s)
BOLD = lambda s: _color(1, s)
MAGENTA = lambda s: _color(35, s)
HIGHLIGHT = lambda s: _color(93, s)

def _should_exclude(path: Path, root: Path) -> bool:
    try:
        parts = set(path.relative_to(root).parts)
        return bool(parts & EXCLUDE_DIRS)
    except ValueError:
        return False

def _collect_files(root: Path, exts: set[str]) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts and not _should_exclude(p, root):
            yield p

def _detect_language(ext: str) -> str:
    mapping = {
        ".py": "py", ".ts": "ts", ".tsx": "tsx", ".js": "js", ".jsx": "jsx",
        ".mjs": "js", ".cjs": "js", ".php": "php", ".rb": "rb", ".java": "java",
        ".go": "go", ".rs": "rs",
    }
    return mapping.get(ext.lower(), "py")

def _build_patterns(name: str, search_types: list[str], use_regex: bool, lang: str) -> list[tuple[str, re.Pattern]]:
    patterns: list[tuple[str, re.Pattern]] = []
    lang_patterns = _PATTERNS.get(lang, _PATTERNS["py"])
    for stype in search_types:
        raw = lang_patterns.get(stype, lang_patterns.get("call", ""))
        if use_regex:
            # If regex mode, replace {name} with the raw regex
            raw_pat = raw.replace(r"{name}", name)
        else:
            raw_pat = raw.replace(r"{name}", re.escape(name))
        if not raw_pat:
            continue
        try:
            pat = re.compile(raw_pat, re.IGNORECASE)
            patterns.append((stype, pat))
        except re.error as e:
            print(DIM(f"  Regex inválida para {stype}: {e}"))
    return patterns

def _search_file(fpath: Path, patterns: list[tuple[str, re.Pattern]],
                context_lines: int, max_per_type: int) -> dict[str, list[dict]]:
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return {}
    lines = text.splitlines()
    results: dict[str, list[dict]] = {}
    for stype, pat in patterns:
        matches = []
        for i, line in enumerate(lines, 1):
            if pat.search(line):
                start = max(0, i - 1 - context_lines)
                end = min(len(lines), i + context_lines)
                ctx = [(j + 1, lines[j]) for j in range(start, end)]
                matches.append({
                    "line": i,
                    "text": line.rstrip(),
                    "context": ctx,
                })
                if len(matches) >= max_per_type:
                    break
        if matches:
            results[stype] = matches
    return results

def _highlight(line: str, name: str, use_regex: bool) -> str:
    try:
        if use_regex:
            pat = re.compile(name, re.IGNORECASE)
        else:
            pat = re.compile(re.escape(name), re.IGNORECASE)
        return pat.sub(lambda m: HIGHLIGHT(m.group(0)), line)
    except Exception:
        return line

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    name = args[0]
    search_dir = ROOT
    use_regex = "--regex" in args
    json_out = "--json" in args
    files_only = "--files" in args
    summary_mode = "--summary" in args
    context_lines = 3
    max_per_type = 20
    exts = DEFAULT_EXTS.copy()

    # Determine search types
    search_types: list[str] = []
    type_flags = {
        "--class": "class",
        "--function": "function",
        "--method": "method",
        "--call": "call",
        "--import": "import",
        "--decorator": "decorator",
        "--assign": "assign",
    }
    for flag, stype in type_flags.items():
        if flag in args:
            search_types.append(stype)
    if not search_types:
        search_types = ["call"]  # default

    # Parse --context, --max, --ext
    for i, arg in enumerate(args):
        if arg == "--context" and i + 1 < len(args):
            try:
                context_lines = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--depth" and i + 1 < len(args):
            try:
                max_per_type = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--ext" and i + 1 < len(args):
            exts = set("." + e.lstrip(".") for e in args[i + 1].split(","))

    # Parse directory
    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if candidate.exists() and candidate.is_dir():
            search_dir = candidate.resolve()
            break

    total_files = 0
    total_matches = 0
    file_results: list[dict] = []

    for fpath in _collect_files(search_dir, exts):
        lang = _detect_language(fpath.suffix)
        patterns = _build_patterns(name, search_types, use_regex, lang)
        if not patterns:
            continue
        results = _search_file(fpath, patterns, context_lines, max_per_type)
        if not results:
            continue
        total_files += 1
        file_match_count = sum(len(v) for v in results.values())
        total_matches += file_match_count
        file_results.append({
            "file": str(fpath.relative_to(search_dir)),
            "absolute": str(fpath),
            "language": lang,
            "matches": results,
        })

    if not file_results:
        if not json_out:
            print(DIM("Sin resultados."))
        else:
            print(json.dumps({"results": [], "total_files": 0, "total_matches": 0}, ensure_ascii=False))
        return 1

    if json_out:
        print(json.dumps({
            "query": name,
            "types": search_types,
            "total_files": total_files,
            "total_matches": total_matches,
            "results": file_results,
        }, ensure_ascii=False, indent=2))
        return 0

    if files_only:
        for entry in file_results:
            print(CYAN(entry["file"]))
        return 0

    if summary_mode:
        print(BOLD(f"🔍 Llamadas/contexto para: {name}") + DIM(f"  ({total_matches} matches en {total_files} archivos)"))
        for entry in file_results:
            print(f"\n{CYAN(entry['file'])} {DIM(f'({entry["language"]})')}")
            for stype, matches in entry["matches"].items():
                print(f"  {YELLOW(stype.upper()):<12} {len(matches)} matches")
        return 0

    # Full pretty output
    print(BOLD(f"🔍 Llamadas/contexto para: {name}") + DIM(f"  ({total_matches} matches en {total_files} archivos)"))
    print(DIM(f"   Tipos: {', '.join(search_types)}"))
    print()

    for entry in file_results:
        print(CYAN(entry["file"]) + DIM(f"  ({entry['language']})"))
        for stype, matches in entry["matches"].items():
            print(f"  {YELLOW('[' + stype.upper() + ']')}")
            for m in matches:
                print(f"    {DIM(str(m['line']).rjust(4))}  {_highlight(m['text'], name, use_regex)}")
                if context_lines > 0:
                    for ctx_num, ctx_line in m["context"]:
                        if ctx_num == m["line"]:
                            continue
                        print(f"        {DIM(str(ctx_num).rjust(4))}  {DIM(ctx_line.rstrip())}")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
