#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_grep_smart.py — grep contextual que entiende código y puede buscar
llamadas, definiciones, imports, asignaciones, comentarios o strings.

Uso:
    python .bago/tools/bago_grep_smart.py <patrón> [directorio] [opciones]

Opciones:
    --def               Solo definiciones (funciones, clases, variables)
    --call              Solo invocaciones / llamadas
    --import            Solo imports / requires / includes
    --assign            Solo asignaciones
    --comment           Solo comentarios
    --string            Solo strings literales
    --type              Solo declaraciones de tipo (TypeScript/Java)
    --decorator         Solo decoradores / anotaciones
    --test              Solo archivos de test (filtra por nombre)
    --no-test           Excluye archivos de test
    --ext EXT           Filtra por extensión
    --context N         Líneas de contexto (default: 2)
    --max M             Máx matches por archivo (default: 10)
    --files             Solo nombres de archivo
    --json              Salida JSON
    --count             Solo cuenta total
    --invert            Invertir match (líneas que NO coinciden)

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

DEFAULT_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json",
                ".md", ".yaml", ".yml", ".sql", ".css", ".scss", ".html", ".xml",
                ".php", ".rb", ".java", ".go", ".rs", ".cs", ".swift", ".kt"}

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

def _is_test_file(path: Path) -> bool:
    name = path.name.lower()
    return any(x in name for x in ["test_", "_test.", "_spec.", ".test.", ".spec.", "__tests__", "tests/"])

# ── Smart context detectors ──
def _detect_context(line: str, ext: str) -> str:
    stripped = line.strip()
    low = ext.lower().lstrip(".")

    # Comments first
    if low in ("py", "pyw", "pyi", "rb"):
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            return "comment"
    if low in ("ts", "tsx", "js", "jsx", "mjs", "cjs", "java", "go", "cs", "swift", "kt", "php"):
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            return "comment"
    if low in ("css", "scss", "less"):
        if stripped.startswith("/*"):
            return "comment"
    if low == "sql":
        if stripped.startswith("--"):
            return "comment"
    if low in ("yaml", "yml", "ini", "cfg", "toml"):
        if stripped.startswith("#"):
            return "comment"

    # Strings
    if re.search(r"^\s*['\"`].*['\"`]|\s*=\s*['\"`]|return\s+['\"`]|:\s*['\"`],", line):
        return "string"

    # Imports
    if low in ("py", "rb"):
        if re.search(r"^\s*(import\s|from\s+\S+\s+import)", stripped):
            return "import"
    if low in ("ts", "tsx", "js", "jsx", "mjs", "cjs"):
        if re.search(r"^\s*(import\s|require\s*\(|from\s+.*?\s+import)", stripped):
            return "import"
    if low == "php":
        if re.search(r"^\s*(include|require|use)\s", stripped):
            return "import"
    if low in ("java", "cs", "swift", "kt"):
        if re.search(r"^\s*import\s", stripped):
            return "import"
    if low == "go":
        if re.search(r"^\s*import\s", stripped):
            return "import"
    if low == "rs":
        if re.search(r"^\s*(use\s|extern\s+crate)", stripped):
            return "import"

    # Definitions
    if low in ("py", "rb"):
        if re.search(r"^\s*(def\s|class\s)", stripped):
            return "def"
    if low in ("ts", "tsx", "js", "jsx", "mjs", "cjs"):
        if re.search(r"\b(function\s|class\s|const\s|let\s|var\s|interface\s|type\s|enum\s)\b", stripped):
            return "def"
    if low == "php":
        if re.search(r"\b(function\s|class\s)\b", stripped):
            return "def"
    if low == "java":
        if re.search(r"\b(class\s|interface\s|enum\s|(?:public|private|protected|static|\s)*\w+\s+\w+\s*\()", stripped):
            return "def"
    if low == "go":
        if re.search(r"^\s*(func\s|type\s+\w+\s+(struct|interface))\b", stripped):
            return "def"
    if low == "rs":
        if re.search(r"\b(fn\s|struct\s|impl\s|trait\s|enum\s)\b", stripped):
            return "def"
    if low in ("cs", "swift", "kt"):
        if re.search(r"\b(class\s|struct\s|interface\s|func\s|fun\s|def\s|var\s|let\s)\b", stripped):
            return "def"

    # Type declarations
    if low in ("ts", "tsx"):
        if re.search(r":\s*(string|number|boolean|any|void|unknown|never|Record|Array|Map|Set|Promise)\b", stripped):
            return "type"
    if low in ("java", "cs", "swift", "kt"):
        if re.search(r"\b(String|int|bool|float|double|void|char|byte|short|long|Object|List|Map|Set|Array)\b", stripped):
            return "type"

    # Decorators / annotations
    if low in ("py", "rb"):
        if stripped.startswith("@"):
            return "decorator"
    if low in ("ts", "tsx", "js", "jsx", "java", "cs", "swift", "kt"):
        if stripped.startswith("@"):
            return "decorator"
    if low == "rs":
        if stripped.startswith("#"):
            return "decorator"

    # Assignments
    if re.search(r"^\s*\w+\s*[=:]\s*", stripped):
        return "assign"

    # Calls (heuristic: word followed by parenthesis)
    if re.search(r"\b\w+\s*\(", stripped):
        return "call"

    return "other"

def _search_file(fpath: Path, pattern: re.Pattern, context_lines: int,
                 max_matches: int, context_filter: str | None,
                 invert: bool) -> list[dict]:
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return []
    lines = text.splitlines()
    matches = []
    for i, line in enumerate(lines, 1):
        line_ctx = _detect_context(line, fpath.suffix)
        has_match = bool(pattern.search(line))
        if invert:
            if has_match:
                continue
            # In invert mode, we still want to show something; just skip matches
            # but we need a separate mechanism. For now, invert applies to pattern only.
            pass
        else:
            if not has_match:
                continue
        if context_filter and line_ctx != context_filter:
            continue
        start = max(0, i - 1 - context_lines)
        end = min(len(lines), i + context_lines)
        ctx = [(j + 1, lines[j]) for j in range(start, end)]
        matches.append({
            "line": i,
            "text": line.rstrip(),
            "context_type": line_ctx,
            "context": ctx,
        })
        if len(matches) >= max_matches:
            break
    return matches

def _highlight(line: str, pattern: re.Pattern) -> str:
    def repl(m: re.Match) -> str:
        return HIGHLIGHT(m.group(0))
    try:
        return pattern.sub(repl, line)
    except Exception:
        return line

def _context_icon(ctx: str) -> str:
    icons = {
        "def": "🔷",
        "call": "📞",
        "import": "📥",
        "assign": "📝",
        "comment": "💬",
        "string": "🎵",
        "type": "📐",
        "decorator": "🏷️",
        "other": "📄",
    }
    return icons.get(ctx, "📄")

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    pattern_str = args[0]
    search_dir = ROOT
    json_out = "--json" in args
    files_only = "--files" in args
    count_only = "--count" in args
    invert = "--invert" in args
    context_lines = 2
    max_matches = 10
    exts = DEFAULT_EXTS.copy()
    context_filter: str | None = None

    # Context filters
    ctx_flags = {
        "--def": "def",
        "--call": "call",
        "--import": "import",
        "--assign": "assign",
        "--comment": "comment",
        "--string": "string",
        "--type": "type",
        "--decorator": "decorator",
    }
    for flag, ctx in ctx_flags.items():
        if flag in args:
            context_filter = ctx
            break

    tests_only = "--test" in args
    no_tests = "--no-test" in args

    for i, arg in enumerate(args):
        if arg == "--context" and i + 1 < len(args):
            try:
                context_lines = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--max" and i + 1 < len(args):
            try:
                max_matches = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--ext" and i + 1 < len(args):
            exts = set("." + e.lstrip(".") for e in args[i + 1].split(","))

    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if candidate.exists() and candidate.is_dir():
            search_dir = candidate.resolve()
            break

    try:
        pattern = re.compile(pattern_str, re.IGNORECASE)
    except re.error as e:
        print(f"\033[31mRegex inválida: {e}\033[0m")
        return 2

    file_results: list[dict] = []
    total_matches = 0

    for fpath in _collect_files(search_dir, exts):
        if tests_only and not _is_test_file(fpath):
            continue
        if no_tests and _is_test_file(fpath):
            continue
        matches = _search_file(fpath, pattern, context_lines, max_matches, context_filter, invert)
        if not matches:
            continue
        total_matches += len(matches)
        file_results.append({
            "file": str(fpath.relative_to(search_dir)),
            "absolute": str(fpath),
            "count": len(matches),
            "matches": matches,
        })

    if not file_results:
        if not json_out:
            print(DIM("Sin resultados."))
        else:
            print(json.dumps({"results": [], "total": 0}, ensure_ascii=False))
        return 1

    if count_only:
        print(total_matches)
        return 0

    if json_out:
        print(json.dumps({
            "query": pattern_str,
            "filter": context_filter,
            "total_files": len(file_results),
            "total_matches": total_matches,
            "results": file_results,
        }, ensure_ascii=False, indent=2))
        return 0

    if files_only:
        for entry in file_results:
            print(CYAN(entry["file"]))
        return 0

    print(BOLD(f"🧠 BAGO Smart Grep: {pattern_str}") + DIM(f"  ({total_matches} matches en {len(file_results)} archivos)"))
    if context_filter:
        print(DIM(f"   Filtro de contexto: {context_filter}"))
    print()

    for entry in file_results:
        print(CYAN(entry["file"]) + DIM(f"  ({entry['count']} matches)"))
        for m in entry["matches"]:
            icon = _context_icon(m["context_type"])
            print(f"  {DIM(str(m['line']).rjust(4))} {icon} {_highlight(m['text'], pattern)}")
            if context_lines > 0:
                for ctx_num, ctx_line in m["context"]:
                    if ctx_num == m["line"]:
                        continue
                    print(f"      {DIM(str(ctx_num).rjust(4))}  {DIM(ctx_line.rstrip())}")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
