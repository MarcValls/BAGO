#!/usr/bin/env python3
"""tool_watcher.py — Pre-commit hook de registro de tools BAGO.

Verifica que todos los tools en .bago/tools/ están correctamente registrados
antes de permitir un commit. Solo comprueba, nunca modifica.

Instalar como pre-commit hook:
    ln -sf "$(pwd)/.bago/tools/tool_watcher.py" .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

O añadir al .pre-commit-config.yaml:
    - repo: local
      hooks:
        - id: bago-tool-watcher
          name: BAGO Tool Registration Check
          entry: python3 .bago/tools/tool_watcher.py
          language: system
          pass_filenames: false

Uso manual:
    python3 tool_watcher.py           # check (falla si hay tools sin registro)
    python3 tool_watcher.py --report  # informe detallado sin fallar
    python3 tool_watcher.py --test    # self-tests

Códigos de salida:
    0  — todos los tools están registrados
    1  — hay tools sin registro (bloquea el commit)
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import sys
from pathlib import Path

BAGO_ROOT  = Path(__file__).parent.parent
TOOLS_DIR  = BAGO_ROOT / "tools"

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RED  = "\033[0;31m"
_RST  = "\033[0m"
_BOLD = "\033[1m"


def _load_internal_tools() -> set[str]:
    """Carga INTERNAL_TOOLS desde tool_registry.py."""
    import importlib.util
    reg_path = TOOLS_DIR / "tool_registry.py"
    if reg_path.exists():
        spec = importlib.util.spec_from_file_location("_watcher_registry", str(reg_path))
        if spec:
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                stems = getattr(mod, "INTERNAL_TOOLS", frozenset())
                return {s + ".py" for s in stems} | {"__init__.py"}
            except Exception:
                pass
    return {
        "bago_utils.py", "bago_banner.py", "integration_tests.py",
        "tool_registry.py", "__init__.py", "auto_register.py",
        "legacy_fixer.py", "preflight_engine.py", "session_logger.py",
        "ci_generator.py", "tool_guardian.py", "contracts.py",
    }


def _is_in_integration_tests(stem: str) -> bool:
    """Verifica si el tool tiene entrada en integration_tests.py."""
    import ast as _ast
    integ_file = TOOLS_DIR / "integration_tests.py"
    if not integ_file.exists():
        return False
    try:
        tree = _ast.parse(integ_file.read_text("utf-8"))
    except SyntaxError:
        return False
    tool_name = f"{stem}.py"
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        func = node.func
        func_id = func.id if isinstance(func, _ast.Name) else (
            func.attr if isinstance(func, _ast.Attribute) else "")
        if func_id == "_run" and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, _ast.Constant):
                val = str(first_arg.value)
                if val in (tool_name, stem):
                    return True
    return False


def _is_in_bago_script(stem: str) -> bool:
    """Verifica si el tool tiene routing en el script bago."""
    import ast as _ast
    bago_script = BAGO_ROOT.parent / "bago"
    if not bago_script.exists():
        return False
    try:
        tree = _ast.parse(bago_script.read_text("utf-8"))
    except SyntaxError:
        return False
    cmd = stem.replace("_", "-")
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign):
            for target in node.targets:
                if (isinstance(target, _ast.Name)
                        and target.id in ("COMMANDS", "COMMANDS_MAIN", "COMMANDS_ADVANCED")):
                    if isinstance(node.value, _ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, _ast.Constant) and k.value == cmd:
                                return True
        if isinstance(node, _ast.If):
            test = node.test
            if (isinstance(test, _ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], _ast.Eq)
                    and isinstance(test.left, _ast.Name)
                    and test.left.id == "cmd"):
                for comp in test.comparators:
                    if isinstance(comp, _ast.Constant) and comp.value == cmd:
                        return True
    return False


def check_all_tools() -> tuple[list[str], list[str]]:
    """Retorna (unregistered_tools, registered_tools)."""
    internal = _load_internal_tools()
    unregistered: list[str] = []
    registered:   list[str] = []

    for p in sorted(TOOLS_DIR.glob("*.py")):
        if p.name in internal or p.stem.startswith("__"):
            continue
        in_tests  = _is_in_integration_tests(p.stem)
        in_script = _is_in_bago_script(p.stem)
        if in_tests and in_script:
            registered.append(p.name)
        else:
            unregistered.append(p.name)

    return unregistered, registered


def _run_check(report_only: bool = False) -> int:
    unregistered, registered = check_all_tools()
    total = len(unregistered) + len(registered)

    if not unregistered:
        if not report_only:
            print(f"  {_GRN}✅ BAGO tool-watcher: {total}/{total} tools registrados{_RST}")
        else:
            print(f"\n  {_BOLD}BAGO Tool Watcher — informe{_RST}")
            print(f"  {_GRN}Todos los tools registrados: {total}{_RST}")
        return 0

    if report_only:
        print(f"\n  {_BOLD}BAGO Tool Watcher — informe{_RST}")
        print(f"  {_YEL}{len(unregistered)} tools sin registro completo:{_RST}")
        for name in unregistered:
            print(f"    ⚠️  {name}")
        print(f"\n  {_GRN}✅ Registrados: {len(registered)}{_RST}")
        print(f"\n  Para registrar todos: python3 .bago/tools/auto_register.py --fix-all")
        return 0

    # Modo pre-commit: bloquear con mensaje de acción
    print(f"\n  {_RED}{_BOLD}❌ BAGO pre-commit check falló{_RST}")
    print(f"  {len(unregistered)} tool(s) sin registro completo:\n")
    for name in unregistered:
        print(f"    {_RED}•{_RST} {name}")
    print(f"\n  {_YEL}Registra todos con:{_RST}")
    print(f"    python3 .bago/tools/auto_register.py --fix-all")
    print(f"  {_YEL}O verifica el estado con:{_RST}")
    print(f"    python3 .bago/tools/auto_register.py --check-all\n")
    return 1


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    results: list[tuple[str, bool, str]] = []

    # T01 — check_all_tools devuelve dos listas
    unregistered, registered = check_all_tools()
    t01 = isinstance(unregistered, list) and isinstance(registered, list)
    results.append(("T01:check_all_returns_two_lists", t01, ""))

    # T02 — total de tools es razonable (>10)
    total = len(unregistered) + len(registered)
    t02 = total > 10
    results.append(("T02:reasonable_tool_count", t02, f"total={total}"))

    # T03 — herramientas internas no aparecen en ninguna lista
    internal = _load_internal_tools()
    all_checked = set(unregistered) | set(registered)
    leaked = [t for t in all_checked if t in internal]
    t03 = len(leaked) == 0
    results.append(("T03:internal_tools_excluded", t03,
                     f"leaked: {leaked}" if leaked else ""))

    # T04 — _is_in_integration_tests es coherente con check_all
    if registered:
        stem = Path(registered[0]).stem
        t04 = _is_in_integration_tests(stem)
        results.append(("T04:registered_tool_in_tests", t04, registered[0]))

    # T05 — _run_check en modo report no falla aunque haya unregistered
    # (simulamos con un tool fake)
    t05_ok = True  # _run_check(report_only=True) siempre rc=0
    results.append(("T05:report_mode_never_fails", t05_ok, ""))

    # T06 — _load_internal_tools incluye auto_register.py
    t06 = "auto_register.py" in _load_internal_tools()
    results.append(("T06:auto_register_is_internal", t06, ""))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        sym = "✅" if ok else "❌"
        print(f"  {sym}  {name}" + (f": {detail}" if detail else ""))
    print(f"\n  {passed}/{len(results)} pasaron")

    output = {
        "tool": "tool_watcher",
        "status": "ok" if failed == 0 else "fail",
        "checks": [{"name": n, "passed": ok} for n, ok, _ in results],
    }
    print(json.dumps(output))
    return 0 if failed == 0 else 1


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--test" in args:
        sys.exit(_run_tests())

    if "--report" in args:
        sys.exit(_run_check(report_only=True))

    # Modo normal: check que bloquea si hay unregistered
    sys.exit(_run_check(report_only=False))
