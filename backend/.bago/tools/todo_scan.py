#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""todo_scan.py — Escanea el código fuente del proyecto buscando TODOs y FIXMEs.

Herramienta PORTABLE: funciona en cualquier proyecto, no requiere BAGO instalado.

Busca comentarios: TODO, FIXME, HACK, XXX, NOTE, OPTIMIZE en el código fuente.
Excluye node_modules, dist, build, .git, .bago por defecto.

Uso:
    python todo_scan.py [--root DIR] [--fixme] [--ext ts,tsx] [--json] [--count]

    --root DIR    Directorio raiz a escanear (default: directorio actual)
    --fixme       Solo FIXME y XXX (los urgentes)
    --ext ts,tsx  Filtrar por extension(es)
    --json        Output en JSON estructurado
    --count       Solo resumen por tipo (sin detalle de lineas)
    --test        Self-tests internos (4/4)

Codigo de salida: 0 = OK
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PATTERNS: dict[str, str] = {
    "TODO":     r"(?i)\bTODO\b",
    "FIXME":    r"(?i)\bFIXME\b",
    "HACK":     r"(?i)\bHACK\b",
    "XXX":      r"(?i)\bXXX\b",
    "OPTIMIZE": r"(?i)\bOPTIMIZE\b",
    "NOTE":     r"(?i)\bNOTE\b",
}

EXCLUDE_DIRS: set[str] = {
    "node_modules", "dist", "build", ".next", ".git", ".bago",
    "out", "coverage", ".turbo", "__pycache__", "venv", ".venv",
}
INCLUDE_EXTS: set[str] = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".json",
    ".md", ".yaml", ".yml", ".env",
}

_GRN  = "\033[32m"
_RED  = "\033[31m"
_YEL  = "\033[33m"
_DIM  = "\033[2m"
_BOLD = "\033[1m"
_CYN  = "\033[36m"
_MAG  = "\033[35m"
_RST  = "\033[0m"

_LABEL_COLOR: dict[str, str] = {
    "FIXME":    _RED,
    "TODO":     _YEL,
    "HACK":     _MAG,
    "XXX":      _RED,
    "OPTIMIZE": _CYN,
    "NOTE":     _DIM,
}


def _col(label: str) -> str:
    return f"{_LABEL_COLOR.get(label, '')}{label}{_RST}"


def _should_exclude(path: Path, root: Path) -> bool:
    try:
        parts = set(path.relative_to(root).parts)
    except ValueError:
        parts = set(path.parts)
    return bool(parts & EXCLUDE_DIRS)


def _scan_file(path: Path, patterns: dict[str, str]) -> list[dict]:
    results: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return results
    for i, line in enumerate(text.splitlines(), 1):
        for label, pattern in patterns.items():
            if re.search(pattern, line):
                snippet = line.strip()
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                results.append({"type": label, "file": str(path), "line": i, "text": snippet})
                break
    return results


def scan_project(
    root: Path,
    extensions: set[str] = INCLUDE_EXTS,
    patterns: dict[str, str] | None = None,
) -> list[dict]:
    if patterns is None:
        patterns = PATTERNS
    results: list[dict] = []
    try:
        for f in sorted(root.rglob("*")):
            if not f.is_file() or _should_exclude(f, root):
                continue
            if f.suffix.lower() not in extensions:
                continue
            results.extend(_scan_file(f, patterns))
    except (PermissionError, OSError):
        pass
    return results


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:]) if argv is None else list(argv)

    only_fixme = "--fixme" in args
    do_json    = "--json" in args
    do_count   = "--count" in args or "-c" in args

    # --root DIR
    root = Path.cwd()
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 < len(args):
            root = Path(args[idx + 1]).resolve()

    # --ext ts,tsx,...
    ext_flag = ""
    if "--ext" in args:
        idx = args.index("--ext")
        if idx + 1 < len(args):
            ext_flag = args[idx + 1]
    extensions = (
        {f".{e.lstrip('.')}" for e in ext_flag.split(",")}
        if ext_flag else INCLUDE_EXTS
    )

    active_patterns = (
        {"FIXME": PATTERNS["FIXME"], "XXX": PATTERNS["XXX"]}
        if only_fixme else PATTERNS
    )
    pattern_order = [lbl for lbl in PATTERNS if lbl in active_patterns]

    if not do_json:
        print()
        print("  +-------------------------------------------------------------+")
        print("  |  BAGO * TODO Scanner                                        |")
        print("  +-------------------------------------------------------------+")
        print(f"  Raiz: {_DIM}{root}{_RST}")
        print()

    results = scan_project(root, extensions, active_patterns)

    if do_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if not results:
        print(f"  {_GRN}[OK] Sin TODOs ni FIXMEs encontrados.{_RST}\n")
        return 0

    counts = Counter(r["type"] for r in results)

    if do_count:
        print(f"  {'TIPO':<12} {'CUENTA':>6}")
        print(f"  {'----':<12} {'------':>6}")
        for lbl in pattern_order:
            n = counts.get(lbl, 0)
            if n:
                print(f"  {_col(lbl):<12} {n:>6}")
        print(f"\n  Total: {_BOLD}{len(results)}{_RST}\n")
        return 0

    for lbl in pattern_order:
        items = [r for r in results if r["type"] == lbl]
        if not items:
            continue
        print(f"  {_col(lbl)} ({len(items)})")
        for item in items[:30]:
            try:
                rel = str(Path(item["file"]).relative_to(root))
            except ValueError:
                rel = item["file"]
            print(f"    {_DIM}{rel}:{item['line']}{_RST}")
            print(f"      {item['text']}")
        if len(items) > 30:
            print(f"    {_DIM}... y {len(items) - 30} mas{_RST}")
        print()

    parts = [f"{_col(l)}: {counts[l]}" for l in pattern_order if counts.get(l)]
    print(f"  Total: {_BOLD}{len(results)}{_RST}  *  " + "  ".join(parts))
    print()
    return 0


def _self_test() -> None:
    import contextlib
    import io
    import tempfile

    print("Tests de todo_scan.py...")
    fails: list[str] = []

    def ok(n: str) -> None:
        print(f"  OK: {n}")

    def fail(n: str, m: str) -> None:
        fails.append(n)
        print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "main.py").write_text("# TODO: implement this\nx = 1\n", encoding="utf-8")
        (root / "app.ts").write_text("// FIXME: broken\n", encoding="utf-8")

        results = scan_project(root, INCLUDE_EXTS, PATTERNS)
        todos  = [r for r in results if r["type"] == "TODO"]
        fixmes = [r for r in results if r["type"] == "FIXME"]

        if todos:
            ok("todo_scan:todo_detected")
        else:
            fail("todo_scan:todo_detected", f"results={results}")

        if fixmes:
            ok("todo_scan:fixme_detected")
        else:
            fail("todo_scan:fixme_detected", f"results={results}")

        rc = main(["--root", td, "--count"])
        if rc == 0:
            ok("todo_scan:root_arg_works")
        else:
            fail("todo_scan:root_arg_works", f"rc={rc}")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["--root", td, "--json"])
        try:
            parsed = json.loads(buf.getvalue())
            if isinstance(parsed, list) and len(parsed) >= 2:
                ok("todo_scan:json_output")
            else:
                fail("todo_scan:json_output", f"parsed={parsed}")
        except json.JSONDecodeError as e:
            fail("todo_scan:json_output", str(e))

    total = 4
    passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main())
