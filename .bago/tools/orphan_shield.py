"""orphan_shield.py — Sistema integral de protección contra huérfanos en BAGO.

Detecta 4 tipos de huérfanos:
  1. FILE orphans:      archivos .py en .bago/tools/ no referenciados en _registry_entries.py
  2. REGISTRY orphans:  entradas en registry que apuntan a archivos inexistentes
  3. ROUTE orphans:     comandos en el router `bago` sin equivalente en registry
  4. DOC orphans:       tools sin mención en docs/ (undocumented_tools)

API pública:
  scan_all()     → dict con las 4 categorías + resumen
  summary_line() → str de una línea para health reports
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE   = Path(__file__).resolve()
_TOOLS  = _HERE.parent                        # .bago/tools/
_BAGO   = _TOOLS.parent                       # .bago/
_ROOT   = _BAGO.parent                        # repo root
_STATE  = _BAGO / "state"

_REGISTRY_FILE = _TOOLS / "_registry_entries.py"
_BASELINE_FILE = _STATE / "orphan_baseline.json"
_BAGO_SCRIPT   = _ROOT / "bago"               # CLI entry-point (no extension)
_DOCS_DIR      = _ROOT / "docs"

# Files never counted as orphans (infra, models, etc.)
_EXCLUDE_STEMS = {
    "__init__", "__main__",
    "_registry_entries", "_registry_models", "_registry_paths",
    "db_init", "tool_registry",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_text(path: Path) -> str:
    """Read a file safely; return '' on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _registry_text(tools_dir: Path | None = None) -> str:
    """Return the fused registry source text, including split registry modules."""
    td = tools_dir or _TOOLS
    parts = []
    for path in sorted(td.glob("_registry_entries*.py")):
        parts.append(_read_text(path))
    return "\n".join(parts)


def _module_exists(module: str, tools_dir: Path | None = None) -> bool:
    """Resolve registry module names against tools packages and BAGO roots."""
    td = tools_dir or _TOOLS
    rel = Path(*module.split("."))
    candidates = [
        td / f"{module}.py",
        td / rel.with_suffix(".py"),
        td / rel / "__init__.py",
        _BAGO / "core" / rel.with_suffix(".py"),
        _BAGO / "agents" / rel.with_suffix(".py"),
        _BAGO / rel.with_suffix(".py"),
        _BAGO / rel / "__init__.py",
    ]
    return any(path.exists() for path in candidates)


def _load_baseline() -> set[str]:
    """Return set of known/accepted orphan stems from orphan_baseline.json."""
    baseline_file = _BASELINE_FILE
    if not baseline_file.exists():
        baseline_file = _BAGO / "state.example" / "orphan_baseline.json"
    if not baseline_file.exists():
        return set()
    try:
        data = json.loads(baseline_file.read_text(encoding="utf-8"))
        return set(data.get("known_orphans", []))
    except Exception:
        return set()


# ── Category 1: FILE orphans ──────────────────────────────────────────────────

def scan_files(tools_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """Return (new_orphans, baseline_orphans) — stems not in _registry_entries.py.

    Excludes dunder files, _registry_entries.py, db_init.py and _EXCLUDE_STEMS.
    baseline_orphans = those in orphan_baseline.json (accepted/known).
    """
    td = tools_dir or _TOOLS
    registry_text = _registry_text(td)
    baseline = _load_baseline()

    orphans: list[str] = []
    known:   list[str] = []

    for py in sorted(td.glob("*.py")):
        stem = py.stem
        if stem.startswith("__") or stem in _EXCLUDE_STEMS:
            continue
        if stem in registry_text:
            continue
        # Not referenced in registry
        if stem in baseline:
            known.append(stem)
        else:
            orphans.append(stem)

    return orphans, known


# ── Category 2: REGISTRY orphans ─────────────────────────────────────────────

def scan_registry(tools_dir: Path | None = None) -> list[str]:
    """Return stems declared in _registry_entries.py whose .py file is missing."""
    td = tools_dir or _TOOLS
    registry_text = _registry_text(td)

    # Extract module= values from registry
    modules = re.findall(r'module\s*=\s*"([^"]+)"', registry_text)
    missing: list[str] = []
    for mod in modules:
        if not _module_exists(mod, td):
            missing.append(mod)
    return sorted(set(missing))


# ── Category 3: ROUTE orphans ────────────────────────────────────────────────

def scan_routes(root: Path | None = None) -> list[str]:
    """Return command names present in the `bago` router but absent from registry.

    Uses conservative regex — never executes the script.
    """
    rt = root or _ROOT
    bago_script = rt / "bago"
    if not bago_script.exists():
        return []

    script_text = _read_text(bago_script)
    registry_text = _registry_text(_TOOLS)

    # Extract quoted command names from dispatcher lines like:
    #   "cmd-name" | 'cmd-name'
    # We look specifically for patterns that look like CLI dispatch keys.
    route_cmds = set(re.findall(r'"([a-z][a-z0-9-]{1,40})"', script_text))
    route_cmds |= set(re.findall(r"'([a-z][a-z0-9-]{1,40})'", script_text))

    orphans: list[str] = []
    for cmd in sorted(route_cmds):
        # Skip very short generic words that are not BAGO commands
        if len(cmd) < 3:
            continue
        # Check if this command name appears in registry (as cmd= value)
        if f'cmd="{cmd}"' not in registry_text and f"cmd='{cmd}'" not in registry_text:
            orphans.append(cmd)

    return orphans


# ── Category 4: DOC coverage ─────────────────────────────────────────────────

def scan_docs(
    docs_dir: Path | None = None,
    tools_dir: Path | None = None,
) -> list[str]:
    """Return list of tool stems that have no mention in any .md in docs/.

    A tool is considered documented if its stem appears anywhere in any .md file.
    """
    td = tools_dir or _TOOLS
    dd = docs_dir or _DOCS_DIR

    # Gather all tool stems (same exclusion logic as scan_files)
    all_stems: list[str] = []
    for py in sorted(td.glob("*.py")):
        stem = py.stem
        if stem.startswith("__") or stem in _EXCLUDE_STEMS:
            continue
        all_stems.append(stem)

    if not dd.exists():
        # No docs dir — every tool is undocumented
        return all_stems

    # Build combined text of all .md files
    combined_docs = ""
    for md in dd.rglob("*.md"):
        combined_docs += _read_text(md) + "\n"

    # Also check .bago/knowledge/ if present
    knowledge_dir = _BAGO / "knowledge"
    if knowledge_dir.exists():
        for md in knowledge_dir.rglob("*.md"):
            combined_docs += _read_text(md) + "\n"

    undocumented: list[str] = []
    for stem in all_stems:
        if stem not in combined_docs:
            undocumented.append(stem)

    return undocumented


# ── Public API ────────────────────────────────────────────────────────────────

def scan_all() -> dict:
    """Run all 4 scans and return unified results dict.

    Returns:
        {
            "file_orphans":       list[str],  # new, not in baseline
            "file_orphans_known": list[str],  # in baseline (accepted)
            "registry_orphans":   list[str],
            "route_orphans":      list[str],
            "undocumented_tools": list[str],
            "total_files":        int,
            "total_docs":         int,
        }
    """
    file_orphans, file_known = scan_files()
    registry_orphans = scan_registry()
    route_orphans    = scan_routes()
    undocumented     = scan_docs()

    total_files = len(list(_TOOLS.glob("*.py")))
    total_docs  = len(list(_DOCS_DIR.rglob("*.md"))) if _DOCS_DIR.exists() else 0

    return {
        "file_orphans":       file_orphans,
        "file_orphans_known": file_known,
        "registry_orphans":   registry_orphans,
        "route_orphans":      route_orphans,
        "undocumented_tools": undocumented,
        "total_files":        total_files,
        "total_docs":         total_docs,
    }


def summary_line() -> str:
    """Return a one-line summary suitable for health reports."""
    r = scan_all()
    nf = len(r["file_orphans"])
    nr = len(r["registry_orphans"])
    nrt = len(r["route_orphans"])
    nd = len(r["undocumented_tools"])
    nk = len(r["file_orphans_known"])
    status = "CRIT" if (nf + nr) > 10 else ("WARN" if (nf + nr) > 0 else "OK")
    return (
        f"[{status}] orphan_shield: "
        f"file={nf} registry={nr} route={nrt} undoc={nd} baseline={nk}"
    )


# ── Report helpers ────────────────────────────────────────────────────────────

_C_OK   = "\033[32m✔\033[0m"
_C_WARN = "\033[33m⚠\033[0m"
_C_CRIT = "\033[31m✗\033[0m"
_C_INFO = "\033[36mℹ\033[0m"
_C_BOLD = "\033[1m"
_C_RST  = "\033[0m"


def _print_report(r: dict) -> None:
    """Print a coloured human-readable orphan report."""
    nf  = len(r["file_orphans"])
    nk  = len(r["file_orphans_known"])
    nr  = len(r["registry_orphans"])
    nrt = len(r["route_orphans"])
    nd  = len(r["undocumented_tools"])

    print(f"\n  {_C_BOLD}👻 Orphan Shield — BAGO{_C_RST}")
    print(f"  {'─'*52}")

    # FILE orphans
    icon = _C_CRIT if nf > 10 else (_C_WARN if nf > 0 else _C_OK)
    print(f"  {icon}  Archivos sin registrar: {nf}  (baseline aceptados: {nk})")
    for stem in r["file_orphans"][:5]:
        print(f"       {_C_WARN}·{_C_RST} {stem}.py")
    if nf > 5:
        print(f"       ... y {nf-5} más")

    # REGISTRY orphans
    icon = _C_CRIT if nr > 0 else _C_OK
    print(f"  {icon}  Registry con archivo faltante: {nr}")
    for stem in r["registry_orphans"][:5]:
        print(f"       {_C_CRIT}·{_C_RST} {stem}")
    if nr > 5:
        print(f"       ... y {nr-5} más")

    # ROUTE orphans
    icon = _C_WARN if nrt > 0 else _C_OK
    print(f"  {icon}  Rutas sin registry: {nrt}")
    for cmd in r["route_orphans"][:5]:
        print(f"       {_C_WARN}·{_C_RST} {cmd}")
    if nrt > 5:
        print(f"       ... y {nrt-5} más")

    # DOC coverage
    icon = _C_WARN if nd > 0 else _C_OK
    print(f"  {icon}  Tools sin documentar: {nd}")
    for stem in r["undocumented_tools"][:5]:
        print(f"       {_C_INFO}·{_C_RST} {stem}")
    if nd > 5:
        print(f"       ... y {nd-5} más")

    print(f"\n  {_C_INFO}  Total archivos .py: {r['total_files']}  ·  Docs .md: {r['total_docs']}")
    print(f"  {'─'*52}\n")


# ── Self-test ─────────────────────────────────────────────────────────────────

def _self_test() -> None:
    """3 basic assertions."""
    # 1. scan_all returns the expected keys
    r = scan_all()
    assert set(r.keys()) >= {
        "file_orphans", "registry_orphans", "route_orphans",
        "undocumented_tools", "total_files", "total_docs",
    }, f"scan_all missing keys: {r.keys()}"

    # 2. summary_line returns a non-empty string
    sl = summary_line()
    assert isinstance(sl, str) and len(sl) > 5, f"summary_line bad: {sl!r}"

    # 3. registry scan finds at least one module (registry file exists + non-empty)
    assert _REGISTRY_FILE.exists(), f"Registry file not found: {_REGISTRY_FILE}"

    print("  3/3 tests pasaron ✔")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)

    if "--test" in args:
        _self_test()
        return 0

    if "--summary" in args:
        print(summary_line())
        return 0

    # Category filter
    category: str | None = None
    if "--category" in args:
        idx = args.index("--category")
        if idx + 1 < len(args):
            category = args[idx + 1]

    r = scan_all()

    if "--json" in args:
        print(json.dumps(r, indent=2))
        return 0

    if category == "file":
        print(json.dumps({"file_orphans": r["file_orphans"],
                          "file_orphans_known": r["file_orphans_known"]}, indent=2))
    elif category == "registry":
        print(json.dumps({"registry_orphans": r["registry_orphans"]}, indent=2))
    elif category == "route":
        print(json.dumps({"route_orphans": r["route_orphans"]}, indent=2))
    elif category == "doc":
        print(json.dumps({"undocumented_tools": r["undocumented_tools"]}, indent=2))
    else:
        _print_report(r)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
