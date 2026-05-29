#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_read.py — Lee archivos del proyecto con manejo contextual de formato.

Uso:
    python .bago/tools/bago_read.py <archivo> [opciones]
    python .bago/tools/bago_read.py <patrón> --auto        # detecta formato por extensión

Opciones:
    --auto              Detección automática de formato por extensión
    --lines N,M         Lee solo líneas N a M (1-based, inclusive)
    --head N            Primeras N líneas
    --tail N            Últimas N líneas
    --json              Salida como JSON (para piping)
    --strip             Elimina comentarios y docstrings (solo .py)
    --no-color          Desactiva resaltado de sintaxis
    --encoding E         Fuerza encoding (default: utf-8)
    --binary            Muestra hex dump si es binario
    --all               Lee todos los archivos que coincidan con patrón

Códigos de salida: 0 = OK, 1 = archivo no encontrado, 2 = error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bago_utils import get_repo_root

ROOT = get_repo_root()

# ── Syntax highlighters (simple regex-based) ──
_CSHARP = ("cs",)
_TS_JS = ("ts", "tsx", "js", "jsx", "mjs", "cjs")
_PY = ("py", "pyw", "pyi")
_MD = ("md", "mdx", "rst")
_JSON = ("json", "jsonc", "json5")
_YAML = ("yaml", "yml")
_SQL = ("sql",)
_CSS = ("css", "scss", "sass", "less")
_HTML = ("html", "htm", "xhtml", "xml", "svg")

def _color(code: int, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"

KEYWORD = lambda s: _color(35, s)
STRING = lambda s: _color(33, s)
COMMENT = lambda s: _color(2, s)
NUMBER = lambda s: _color(36, s)
FUNCTION = lambda s: _color(1, s)
TYPE = lambda s: _color(32, s)

def _highlight_py(line: str) -> str:
    # Comments
    line = re.sub(r"(#.*)$", lambda m: COMMENT(m.group(1)), line)
    # Strings
    line = re.sub(r"([rfbu]?)('.*?[^\\]'|\".*?[^\\]\")", lambda m: STRING(m.group(0)), line)
    # Keywords
    keywords = r"\b(def|class|return|if|elif|else|for|while|try|except|finally|with|as|import|from|raise|yield|lambda|assert|break|continue|pass|global|nonlocal|del|and|or|not|in|is|None|True|False|await|async)\b"
    line = re.sub(keywords, lambda m: KEYWORD(m.group(0)), line)
    # Numbers
    line = re.sub(r"\b(\d+\.?\d*)\b", lambda m: NUMBER(m.group(0)), line)
    # Function calls
    line = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", lambda m: FUNCTION(m.group(1)) + "(", line)
    return line

def _highlight_ts_js(line: str) -> str:
    line = re.sub(r"(//.*)$", lambda m: COMMENT(m.group(1)), line)
    line = re.sub(r"(/\*.*?\*/|/\*.*)$", lambda m: COMMENT(m.group(0)), line)
    line = re.sub(r"('.*?[^\\]'|\".*?[^\\]\"|`.*?[^\\]`)", lambda m: STRING(m.group(0)), line)
    keywords = r"\b(const|let|var|function|class|interface|type|enum|return|if|else|for|while|switch|case|default|try|catch|finally|throw|new|this|import|export|from|as|async|await|yield|typeof|instanceof|in|of|void|delete|true|false|null|undefined)\b"
    line = re.sub(keywords, lambda m: KEYWORD(m.group(0)), line)
    line = re.sub(r"\b(\d+\.?\d*)\b", lambda m: NUMBER(m.group(0)), line)
    line = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", lambda m: FUNCTION(m.group(1)) + "(", line)
    return line

def _highlight_json(line: str) -> str:
    line = re.sub(r"('.*?[^\\]'|\".*?[^\\]\")", lambda m: STRING(m.group(0)), line)
    line = re.sub(r"\b(true|false|null)\b", lambda m: KEYWORD(m.group(0)), line)
    line = re.sub(r"\b(\d+\.?\d*)\b", lambda m: NUMBER(m.group(0)), line)
    return line

def _highlight_yaml(line: str) -> str:
    line = re.sub(r"(#.*)$", lambda m: COMMENT(m.group(1)), line)
    line = re.sub(r"('.*?[^\\]'|\".*?[^\\]\")", lambda m: STRING(m.group(0)), line)
    line = re.sub(r"\b(true|false|null|yes|no|on|off)\b", lambda m: KEYWORD(m.group(0)), line)
    line = re.sub(r"\b(\d+\.?\d*)\b", lambda m: NUMBER(m.group(0)), line)
    return line

def _highlight_sql(line: str) -> str:
    line = re.sub(r"(--.*)$", lambda m: COMMENT(m.group(1)), line)
    line = re.sub(r"('.*?[^\\]'|\".*?[^\\]\")", lambda m: STRING(m.group(0)), line)
    keywords = r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|ORDER|BY|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|AS|AND|OR|NOT|NULL|IS|IN|EXISTS|BETWEEN|LIKE|CASE|WHEN|THEN|ELSE|END|IF|INT|VARCHAR|TEXT|DATE|TIME|PRIMARY|KEY|FOREIGN|REFERENCES|INDEX|CONSTRAINT)\b"
    line = re.sub(keywords, lambda m: KEYWORD(m.group(0)), line, flags=re.IGNORECASE)
    line = re.sub(r"\b(\d+\.?\d*)\b", lambda m: NUMBER(m.group(0)), line)
    return line

def _highlight_css(line: str) -> str:
    line = re.sub(r"(/\*.*?\*/)", lambda m: COMMENT(m.group(0)), line)
    line = re.sub(r"('.*?[^\\]'|\".*?[^\\]\")", lambda m: STRING(m.group(0)), line)
    line = re.sub(r"\b(\d+(?:px|em|rem|%|vh|vw|pt|cm|mm|in|s|ms|hz|khz)?)\b", lambda m: NUMBER(m.group(0)), line)
    return line

def _highlight_md(line: str) -> str:
    line = re.sub(r"^(#{1,6}\s+)(.*)$", lambda m: _color(1, m.group(1)) + _color(36, m.group(2)), line)
    line = re.sub(r"(\*\*.*?\*\*|__.*?__)", lambda m: _color(1, m.group(0)), line)
    line = re.sub(r"(\*.*?\*|_.*?_)", lambda m: _color(3, m.group(0)), line)
    line = re.sub(r"(`.*?`)", lambda m: _color(33, m.group(0)), line)
    line = re.sub(r"(!?\[.*?\]\(.*?\))", lambda m: _color(32, m.group(0)), line)
    return line

def _highlight_html(line: str) -> str:
    line = re.sub(r"(<!--.*?-->)", lambda m: COMMENT(m.group(0)), line)
    line = re.sub(r"(</?[a-zA-Z][a-zA-Z0-9\-]*(?:\s[^\u003e]*)?\u003e)", lambda m: _color(36, m.group(0)), line)
    line = re.sub(r"('.*?[^\\]'|\".*?[^\\]\")", lambda m: STRING(m.group(0)), line)
    return line

def _highlight(line: str, ext: str) -> str:
    ext = ext.lstrip(".").lower()
    if ext in _PY:
        return _highlight_py(line)
    if ext in _TS_JS:
        return _highlight_ts_js(line)
    if ext in _JSON:
        return _highlight_json(line)
    if ext in _YAML:
        return _highlight_yaml(line)
    if ext in _SQL:
        return _highlight_sql(line)
    if ext in _CSS:
        return _highlight_css(line)
    if ext in _MD:
        return _highlight_md(line)
    if ext in _HTML:
        return _highlight_html(line)
    return line

def _strip_python_comments(text: str) -> str:
    """Remove docstrings and comments from Python code."""
    # Remove single-line comments
    lines = []
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].rstrip()
        if stripped:
            lines.append(stripped)
    text = "\n".join(lines)
    # Remove docstrings (simple approach)
    text = re.sub(r'\n\s*""".*?"""\s*\n', "\n", text, flags=re.DOTALL)
    text = re.sub(r"\n\s*'''.*?'''\s*\n", "\n", text, flags=re.DOTALL)
    return text

def _hex_dump(data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<{width*3}}  {ascii_part}")
    return "\n".join(lines)

def _resolve_target(pattern: str) -> list[Path]:
    candidate = Path(pattern)
    if candidate.exists():
        return [candidate.resolve()]
    # Try from repo root
    from_root = ROOT / pattern
    if from_root.exists():
        return [from_root.resolve()]
    # Try glob
    matches = list(ROOT.rglob(pattern))
    if matches:
        return [m.resolve() for m in matches if m.is_file()]
    return []

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    pattern = args[0]
    auto_mode = "--auto" in args
    strip_comments = "--strip" in args
    no_color = "--no-color" in args
    json_out = "--json" in args
    binary_mode = "--binary" in args
    read_all = "--all" in args
    encoding = "utf-8"

    line_range: tuple[int, int] | None = None
    head_n: int | None = None
    tail_n: int | None = None

    for i, arg in enumerate(args):
        if arg == "--lines" and i + 1 < len(args):
            try:
                start, end = args[i + 1].split(",")
                line_range = (int(start), int(end))
            except ValueError:
                pass
        if arg == "--head" and i + 1 < len(args):
            try:
                head_n = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--tail" and i + 1 < len(args):
            try:
                tail_n = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--encoding" and i + 1 < len(args):
            encoding = args[i + 1]

    targets = _resolve_target(pattern)
    if not targets:
        print(f"\033[31mArchivo no encontrado: {pattern}\033[0m")
        return 1

    if not read_all:
        targets = targets[:1]

    results: list[dict] = []

    for target in targets:
        try:
            if binary_mode:
                data = target.read_bytes()
                if _color(1, ""):  # check if terminal supports color
                    pass
                hex_str = _hex_dump(data[:4096])
                if json_out:
                    results.append({"file": str(target), "binary": True, "hex": hex_str, "size": len(data)})
                else:
                    print(f"\033[1m📄 {target}\033[0m  ({len(data)} bytes)")
                    print(hex_str)
                    if len(data) > 4096:
                        print("\033[2m... (truncado)\033[0m")
                continue

            text = target.read_text(encoding=encoding, errors="replace")
            if strip_comments and target.suffix.lower() == ".py":
                text = _strip_python_comments(text)

            lines = text.splitlines()
            display_lines = lines[:]
            if line_range:
                start, end = line_range
                display_lines = lines[start - 1:end]
            elif head_n is not None:
                display_lines = lines[:head_n]
            elif tail_n is not None:
                display_lines = lines[-tail_n:]

            ext = target.suffix
            numbered = [(i + 1, line) for i, line in enumerate(display_lines)]

            if json_out:
                results.append({
                    "file": str(target),
                    "extension": ext,
                    "total_lines": len(lines),
                    "displayed_lines": len(display_lines),
                    "lines": [{"num": num, "text": text} for num, text in numbered],
                })
                continue

            print(f"\033[1m📄 {target}\033[0m  ({len(lines)} líneas)")
            for num, line in numbered:
                prefix = f"\033[2m{num:4}\033[0m"
                if no_color:
                    print(f"{prefix}  {line.rstrip()}")
                else:
                    highlighted = _highlight(line.rstrip(), ext)
                    print(f"{prefix}  {highlighted}")
            print()
        except Exception as e:
            print(f"\033[31mError leyendo {target}: {e}\033[0m")
            return 2

    if json_out:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
