#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bago_why — Explica el propósito y contexto de un comando BAGO.

Consulta tool_registry.py (contratos) y tool_catalog.json (semántica)
para dar una respuesta unificada sobre qué hace un comando, cuándo usarlo
y con qué otros comandos se relaciona.

Usage:
    bago why <cmd>
    python3 bago_why.py <cmd>
    python3 bago_why.py --test
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import sys
from pathlib import Path

ROOT      = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / ".bago" / "tools"
STATE_DIR = ROOT / ".bago" / "state"

# ANSI helpers
_BOLD = "\033[1m"
_CYN  = "\033[36m"
_GRN  = "\033[32m"
_DIM  = "\033[2m"
_RST  = "\033[0m"


# ── Data sources ──────────────────────────────────────────────────────────────

def _load_registry() -> dict[str, dict]:
    """Load REGISTRY from tool_registry.py and flatten to plain dicts."""
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from tool_registry import REGISTRY  # type: ignore
        return {
            k: {"cmd": e.cmd, "module": e.module, "description": e.description}
            for k, e in REGISTRY.items()
        }
    except Exception:
        return {}


def _load_catalog() -> dict[str, dict]:
    """Load tools from tool_catalog.json keyed by command name."""
    catalog_path = STATE_DIR / "config" / "tool_catalog.json"
    if not catalog_path.exists():
        return {}
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        return {t["command"]: t for t in data.get("tools", [])}
    except Exception:
        return {}


def _load_module_docstring(module: str) -> str:
    """Read the module-level docstring from the tool's .py file."""
    py_file = TOOLS_DIR / f"{module}.py"
    if not py_file.exists():
        return ""
    try:
        src = py_file.read_text(encoding="utf-8")
        # Extract first triple-quoted string at top
        for delim in ('"""', "'''"):
            if delim in src:
                start = src.find(delim)
                end   = src.find(delim, start + 3)
                if end != -1:
                    return src[start + 3:end].strip()
        return ""
    except Exception:
        return ""


# ── Display ───────────────────────────────────────────────────────────────────

def _print_why(cmd: str, registry: dict, catalog: dict) -> int:
    reg_entry = registry.get(cmd) or registry.get(cmd.replace("-", "_"))
    cat_entry = catalog.get(cmd)

    if not reg_entry and not cat_entry:
        print(f"  {cmd}: comando no encontrado en registry ni en catálogo.")
        print(f"  Tip: ejecuta `bago tool-guardian` para verificar integridad.")
        return 1

    module = (reg_entry or {}).get("module", cmd.replace("-", "_"))
    docstring = _load_module_docstring(module)

    print()
    print(f"  {_BOLD}{_CYN}bago {cmd}{_RST}")

    if reg_entry:
        print(f"  {_BOLD}Descripción:{_RST} {reg_entry['description']}")
        print(f"  {_DIM}Módulo: {module}.py{_RST}")

    if cat_entry:
        cat_desc = cat_entry.get("description", "")
        if cat_desc and cat_desc != reg_entry.get("description", "") if reg_entry else True:
            print(f"  {_BOLD}Catálogo:{_RST}    {cat_desc}")

        keywords = cat_entry.get("keywords", [])
        if keywords:
            print(f"  {_BOLD}Keywords:{_RST}    {', '.join(keywords)}")

        category = cat_entry.get("category", "")
        if category:
            print(f"  {_BOLD}Categoría:{_RST}   {category}")

        codes = cat_entry.get("codes", [])
        if codes:
            print(f"  {_BOLD}Códigos:{_RST}     {', '.join(codes)}")

    if docstring:
        # Show first non-empty paragraph of docstring
        paragraphs = [p.strip() for p in docstring.split("\n\n") if p.strip()]
        if paragraphs:
            print(f"  {_BOLD}Módulo dice:{_RST}")
            for line in paragraphs[0].splitlines():
                print(f"    {_DIM}{line}{_RST}")

    # Related commands: look for tools in same category
    if cat_entry:
        cat = cat_entry.get("category", "")
        if cat:
            related = [
                t["command"] for t in catalog.values()
                if t.get("category") == cat and t["command"] != cmd
            ]
            if related:
                print(f"  {_BOLD}Relacionados:{_RST} {', '.join(related[:6])}")

    print()
    return 0


def _search_similar(query: str, registry: dict, catalog: dict) -> None:
    """Show commands that match the query by keywords or category."""
    q = query.lower()
    matches: list[tuple[int, str, str]] = []

    for cmd_name, entry in catalog.items():
        score = 0
        if q in cmd_name:
            score += 10
        if q in entry.get("description", "").lower():
            score += 5
        for kw in entry.get("keywords", []):
            if q in kw.lower():
                score += 3
        if q in entry.get("category", "").lower():
            score += 2
        if score > 0:
            matches.append((score, cmd_name, entry.get("description", "")))

    if matches:
        matches.sort(reverse=True)
        print(f"  Comandos relacionados con '{query}':")
        for _, name, desc in matches[:5]:
            print(f"    {_GRN}bago {name}{_RST}  — {desc[:60]}")
        print()


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(
            "\n  Usage: bago why <cmd>\n\n"
            "  Muestra qué hace un comando BAGO, cuándo usarlo\n"
            "  y con qué otros comandos se relaciona.\n\n"
            "  Ejemplo: bago why tool-guardian\n"
        )
        return 0

    if argv[1] == "--test":
        return _self_test()

    cmd = argv[1]
    if cmd.startswith("bago "):
        cmd = cmd[5:]
    cmd = cmd.strip()

    registry = _load_registry()
    catalog  = _load_catalog()

    rc = _print_why(cmd, registry, catalog)
    if rc != 0:
        _search_similar(cmd, registry, catalog)
    return rc


# ── Self-test ─────────────────────────────────────────────────────────────────

def _self_test() -> int:
    print("Tests de bago_why.py...")
    fails: list[str] = []

    def ok(n: str)              -> None: print(f"  OK: {n}")
    def fail(n: str, m: str)    -> None: fails.append(n); print(f"  FAIL: {n}: {m}")

    registry = _load_registry()
    catalog  = _load_catalog()

    # T1: registry loads and has at least 5 entries
    if len(registry) >= 5:
        ok("registry_loads")
    else:
        fail("registry_loads", f"only {len(registry)} entries")

    # T2: catalog loads and has entries
    if len(catalog) >= 5:
        ok("catalog_loads")
    else:
        fail("catalog_loads", f"only {len(catalog)} entries")

    # T3: known command resolves
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _print_why("lint", registry, catalog)
    out = buf.getvalue()
    if rc == 0 and "lint" in out:
        ok("known_cmd_resolves")
    else:
        fail("known_cmd_resolves", f"rc={rc}, output={out[:80]}")

    # T4: unknown command returns 1
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        rc2 = _print_why("nonexistent-xyz", registry, catalog)
    if rc2 == 1:
        ok("unknown_cmd_returns_1")
    else:
        fail("unknown_cmd_returns_1", f"got rc={rc2}")

    # T5: search similar
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        _search_similar("lint", registry, catalog)
    out3 = buf3.getvalue()
    if "lint" in out3.lower() or "relacionados" in out3.lower():
        ok("search_similar_finds_lint")
    else:
        fail("search_similar_finds_lint", f"output={out3[:80]}")

    total = 5
    passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
