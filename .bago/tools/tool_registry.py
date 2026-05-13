#!/usr/bin/env python3
"""tool_registry.py — Registro central de herramientas BAGO.

Fuente ÚNICA de verdad para:
  - Mapping cmd → módulo Python (reemplaza COMMANDS dict en bago)
  - Descripción por herramienta
  - Pre-flight checks declarativos por comando
  - Lista canónica de tools internas (excluidas de guardian/manifest)

Importado por: bago (script), tool_guardian.py, auto_register.py,
               contracts.py, ci_generator.py

Uso:
    python3 tool_registry.py --list          # lista todos los comandos
    python3 tool_registry.py --json          # JSON del registro completo
    python3 tool_registry.py --test          # self-tests (7/7)

Arquitectura interna (sub-módulos privados en el mismo directorio):
    _registry_paths.py    — constantes de ruta (TOOLS_DIR, BAGO_ROOT, PYTHON)
    _registry_models.py   — dataclasses PreflightCheck + ToolEntry
    _registry_entries.py  — dict REGISTRY con las 111 entradas de herramientas
    _registry_taxonomy.py — mapas layer/scope/agent + post-procesado de entradas
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure sub-modules in this directory are importable even when this file is
# loaded via importlib.util.spec_from_file_location (which does NOT add the
# file's directory to sys.path automatically).
_TOOLS_DIR = Path(__file__).parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

# ── Imports from sub-modules ───────────────────────────────────────────────────
# Public re-exports — consumers import from tool_registry, not sub-modules.

from _registry_models import PreflightCheck, ToolEntry          # noqa: E402, F401
from _registry_paths import BAGO_ROOT, PYTHON, REPO_ROOT, TOOLS_DIR  # noqa: E402, F401
from _registry_taxonomy import LAYERS, REGISTRY, SCOPE_BADGE   # noqa: E402, F401

# ── Internal tools — excluded from guardian / manifest / integration_tests ─────
# Single canonical source; all other files should import this set.
INTERNAL_TOOLS: frozenset[str] = frozenset({
    "tool_registry",
    "preflight_engine",
    "session_logger",
    "integration_tests",
    "bago_utils",
    "bago_banner",
    "auto_register",
    "ci_generator",
    "tool_guardian",
    "bago_start",
    "bago_on",
    "bago_debug",
    "bago_watch",
    "bago_chat_server",
    "bago_ask",
    "bago_lint_cli",
    "bago_search",
    "legacy_fixer",
    "bago_config",
    "audit_state_pointers",
    # registry sub-modules (private, not user-facing tools)
    "_registry_paths",
    "_registry_models",
    "_registry_entries",
    "_registry_taxonomy",
})


# ── Public API functions ───────────────────────────────────────────────────────

def get_deprecated_map() -> dict[str, str]:
    """Returns {cmd: see_also} for deprecated commands."""
    return {
        name: entry.see_also
        for name, entry in REGISTRY.items()
        if entry.deprecated
    }


def get_by_layer(include_deprecated: bool = False) -> dict[str, list[ToolEntry]]:
    """Returns commands grouped by layer.

    Keys match LAYERS dict order. Only non-deprecated entries unless
    include_deprecated=True.
    """
    result: dict[str, list[ToolEntry]] = {k: [] for k in LAYERS}
    result[""] = []  # bucket for entries with unknown layer
    for entry in REGISTRY.values():
        if not include_deprecated and entry.deprecated:
            continue
        bucket = entry.layer if entry.layer in result else ""
        result[bucket].append(entry)
    for bucket in result:
        result[bucket].sort(key=lambda e: e.cmd)
    return result


def get_commands() -> dict[str, list[str]]:
    """Returns COMMANDS-compatible dict for the bago script.

    Format: {"cmd": ["python3", "/path/to/module.py", ...extra_args]}
    Searches TOOLS_DIR first, then BAGO_ROOT/core/, then rglob anywhere under
    BAGO_ROOT as fallback (resilient to subdirectory reorganisation).
    """
    _extra_args: dict[str, list[str]] = {
        "done":           ["--done"],
        "status":         ["status"],
        "project-init":   ["project-init"],
        "project-link":   ["project-link"],
        "project-unlink": ["project-unlink"],
        "project-state":  ["project-state"],
        "report":         ["report"],
        "session_close":  ["close"],
        "deactivate":     ["deactivate"],
        "promote":        ["promote"],
        "learn":          ["learn"],
    }

    def _resolve_module(stem: str) -> Path:
        """Return the first existing path for module stem or package __main__.py."""
        candidates = [
            TOOLS_DIR / f"{stem}.py",
            TOOLS_DIR / stem / "__main__.py",
            BAGO_ROOT / "core" / f"{stem}.py",
            BAGO_ROOT / "core" / stem / "__main__.py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        file_hits = list(BAGO_ROOT.rglob(f"{stem}.py"))
        if file_hits:
            return file_hits[0]

        package_hits = [p for p in BAGO_ROOT.rglob("__main__.py") if p.parent.name == stem]
        if package_hits:
            return package_hits[0]

        return TOOLS_DIR / f"{stem}.py"

    result = {}
    for name, entry in REGISTRY.items():
        module_path = _resolve_module(entry.module)
        cmd = [PYTHON, str(module_path)]
        if name in _extra_args:
            cmd += _extra_args[name]
        result[name] = cmd
    return result


def get_cmd_names() -> list[str]:
    """Sorted list of all registered public command names."""
    return sorted(REGISTRY.keys())


def load_registry(registry_path: "Path | None" = None) -> "dict[str, ToolEntry]":
    """Load REGISTRY from an explicit path via importlib (no sys.path needed).

    Falls back to this module's REGISTRY if registry_path is None or missing.
    """
    import importlib.util
    if registry_path is None:
        return REGISTRY
    path = registry_path
    if not path.exists():
        return REGISTRY
    # Ensure the target's directory is importable (sub-modules need it)
    target_dir = str(path.parent)
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)
    spec = importlib.util.spec_from_file_location("_tool_registry_loaded", path)
    if spec is None:
        return REGISTRY
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return getattr(mod, "REGISTRY", REGISTRY)
    except Exception:
        return REGISTRY


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cmd_list() -> None:
    print("  BAGO — Registro central de herramientas")
    print(f"  {'CMD':<18} {'MÓDULO':<28} DESCRIPCIÓN")
    print("  " + "─" * 76)
    for name, entry in sorted(REGISTRY.items()):
        print(f"  {name:<18} {entry.module:<28} {entry.description}")
    print(f"\n  Comandos registrados: {len(REGISTRY)}")
    print(f"  Herramientas internas: {len(INTERNAL_TOOLS)}")


def _cmd_json() -> None:
    out = {
        "total": len(REGISTRY),
        "internal_count": len(INTERNAL_TOOLS),
        "internal_tools": sorted(INTERNAL_TOOLS),
        "tools": {
            name: {
                "cmd": e.cmd,
                "module": e.module,
                "description": e.description,
                "preflight": [
                    {"kind": p.kind, "value": p.value, "severity": p.severity}
                    for p in e.preflight
                ],
            }
            for name, e in sorted(REGISTRY.items())
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _self_tests() -> None:
    results: list[dict] = []

    def _check(name: str, cond: bool, msg: str) -> None:
        results.append({"name": name, "passed": cond, "message": msg})
        print(f"  {'✅' if cond else '❌'} {name}: {msg}")

    # T1: REGISTRY non-empty
    _check("T1:registry-non-empty", len(REGISTRY) > 0,
           f"{len(REGISTRY)} entries in REGISTRY")

    # T2: every entry's cmd matches its dict key
    mismatches = [k for k, v in REGISTRY.items() if v.cmd != k]
    _check("T2:cmd-key-consistency", not mismatches,
           "all cmd == key" if not mismatches else f"mismatches: {mismatches}")

    # T3: no duplicate modules except explicit public aliases
    allowed_alias_modules = {"flow", "show_task", "project_memory", "autonomous_loop", "health", "session"}
    modules = [e.module for e in REGISTRY.values()]
    dupes = {m for m in modules if modules.count(m) > 1 and m not in allowed_alias_modules}
    _check("T3:no-duplicate-modules", not dupes,
           "no unexpected duplicate modules" if not dupes else f"duplicates: {dupes}")

    # T4: get_commands() returns current Python + .py format
    cmds = get_commands()
    fmt_ok = all(
        isinstance(v, list) and len(v) >= 2
        and v[0] in (PYTHON, "python3") and v[1].endswith(".py")
        for v in cmds.values()
    )
    _check("T4:get-commands-format", fmt_ok,
           f"{len(cmds)} commands with current-python+.py format")

    # T5: INTERNAL_TOOLS are all strings and non-empty
    _check("T5:internal-tools-valid",
           bool(INTERNAL_TOOLS) and all(isinstance(t, str) for t in INTERNAL_TOOLS),
           f"{len(INTERNAL_TOOLS)} internal tools, all strings")

    # T6: new framework modules are in INTERNAL_TOOLS
    new_mods = {"preflight_engine", "session_logger", "tool_registry"}
    ok = new_mods.issubset(INTERNAL_TOOLS)
    _check("T6:new-modules-in-internal", ok,
           f"{new_mods} ⊆ INTERNAL_TOOLS")

    # T7: get_cmd_names() == REGISTRY keys
    _check("T7:cmd-names-consistent",
           set(get_cmd_names()) == set(REGISTRY.keys()),
           "get_cmd_names() matches REGISTRY keys")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n  {passed}/{total} tests pasaron")
    print(json.dumps({"tool": "tool_registry", "status": "ok" if passed == total else "fail",
                      "checks": results}))
    sys.exit(0 if passed == total else 1)


def main() -> None:
    if "--test" in sys.argv:
        _self_tests()
    elif "--json" in sys.argv:
        _cmd_json()
    else:
        _cmd_list()


if __name__ == "__main__":
    main()
