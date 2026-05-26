#!/usr/bin/env python3
"""preflight_engine.py — Fail-closed preflight enforcement + declarative checks (BAGO).

Merged from preflight_engine.py + preflight.py. The bago CLI loads this file by path
and calls enforce(cmd). preflight.py no longer exists as a separate file.

Preflight policy enforcement:
  "required"  → if checks missing or fail: BLOCK (sys.exit)
  "optional"  → if checks fail: WARNING, execution continues
  "none"      → skip all preflight silently

Declarative preflight API:
    from preflight_engine import Preflight
    pf = Preflight("mi_tool")
    pf.require_file(".bago/state/global_state.json")
    pf.require_env("GITHUB_TOKEN", severity="warning")
    pf.require_cmd("git")
    ok = pf.run(exit_on_fail=True)

CLI (for testing):
    python3 preflight_engine.py --test
    python3 preflight_engine.py --tool cosecha
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import NamedTuple

TOOLS_DIR = Path(__file__).parent


# ── Path helpers ──────────────────────────────────────────────────────────────

def _find_sibling(stem: str) -> Path:
    """Find a .py file by stem — direct first, rglob fallback."""
    direct = TOOLS_DIR / f"{stem}.py"
    if direct.exists():
        return direct
    for found in TOOLS_DIR.parent.rglob(f"{stem}.py"):
        if not found.name.startswith(".") and ".healer.bak" not in found.name:
            return found
    return direct  # non-existent path — callers handle "missing" uniformly


def _find_tool_dynamic(stem: str) -> "Path | None":
    """Locate a .py file by stem searching recursively from tools/.

    Uses _bago_paths.find_tool() if available; falls back to rglob.
    """
    bago_paths_candidates = [
        TOOLS_DIR / "_bago_paths.py",
        *TOOLS_DIR.rglob("_bago_paths.py"),
    ]
    for bp in bago_paths_candidates:
        if bp.exists():
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location("_bago_paths_pf", str(bp))
                if _spec:
                    _mod = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_mod)  # type: ignore
                    result = _mod.find_tool(stem)
                    return result if result and result.exists() else None
            except Exception:
                break
    bago_root = TOOLS_DIR.parent
    for found in bago_root.rglob(f"{stem}.py"):
        if not found.name.startswith(".") and ".healer.bak" not in found.name:
            return found
    return None


def _find_registry_dynamic() -> "Path | None":
    """Find tool_registry.py recursively — survives reorganisation."""
    direct = TOOLS_DIR / "tool_registry.py"
    if direct.exists():
        return direct
    for found in TOOLS_DIR.parent.rglob("tool_registry.py"):
        return found
    return None


# ── Module loader ─────────────────────────────────────────────────────────────

def _load_mod(path: Path, name: str):
    """Load a Python module from path without polluting sys.path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        sys.modules.pop(name, None)
        return None


# ── CheckResult ───────────────────────────────────────────────────────────────

class CheckResult(NamedTuple):
    name: str
    kind: str
    passed: bool
    severity: str     # "error" | "warning"
    message: str


# ── Preflight builder ─────────────────────────────────────────────────────────

class Preflight:
    """Accumulates and runs pre-flight checks for a named tool."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self._results: list[CheckResult] = []

    def require_file(
        self, path: "str | Path", msg: str = "", severity: str = "error"
    ) -> "Preflight":
        """Assert that a file or directory exists.

        Falls back to recursive stem search if the direct path doesn't exist,
        so checks stay valid after files are reorganised into subdirectories.
        """
        p = Path(path)
        ok = p.exists()
        resolved = p
        if not ok:
            resolved = _find_tool_dynamic(p.stem) or p
            ok = resolved.exists()
        self._results.append(CheckResult(
            name=f"file:{p.name}", kind="file", passed=ok, severity=severity,
            message=msg or (
                f"✓ {resolved}" if ok
                else f"✗ Archivo requerido no existe: {p}"
            ),
        ))
        return self

    def require_env(
        self, var: str, msg: str = "", severity: str = "error"
    ) -> "Preflight":
        """Assert that an environment variable is set and non-empty."""
        ok = bool(os.environ.get(var))
        self._results.append(CheckResult(
            name=f"env:{var}", kind="env", passed=ok, severity=severity,
            message=msg or (f"✓ ${var} definida" if ok else
                            f"✗ Variable de entorno requerida no definida: {var}"),
        ))
        return self

    def require_cmd(
        self, cmd: str, msg: str = "", severity: str = "error"
    ) -> "Preflight":
        """Assert that a shell command is available on PATH."""
        ok = shutil.which(cmd) is not None
        self._results.append(CheckResult(
            name=f"cmd:{cmd}", kind="cmd", passed=ok, severity=severity,
            message=msg or (f"✓ {cmd} disponible" if ok else
                            f"✗ Comando requerido no encontrado en PATH: {cmd}"),
        ))
        return self

    @property
    def passed(self) -> bool:
        """True when no error-severity check has failed."""
        return all(r.passed for r in self._results if r.severity == "error")

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self._results if not r.passed and r.severity == "warning"]

    def run(self, exit_on_fail: bool = True, silent: bool = False) -> bool:
        """Run all accumulated checks.

        Prints warning-severity failures to stdout (unless silent=True).
        Prints error-severity failures to stderr.
        If exit_on_fail=True and any error check failed, calls sys.exit(1).
        Returns True when all error checks passed.
        """
        warns  = [r for r in self._results if not r.passed and r.severity == "warning"]
        errors = [r for r in self._results if not r.passed and r.severity == "error"]

        if not silent and warns:
            print(f"  ⚠  Preflight warnings para '{self.tool_name}':")
            for r in warns:
                print(f"     {r.message}")

        if not errors:
            return True

        print(f"\n  ⛔ Preflight FAILED para '{self.tool_name}':", file=sys.stderr)
        for r in errors:
            print(f"     {r.message}", file=sys.stderr)

        if exit_on_fail:
            sys.exit(1)
        return False

    def to_json_checks(self) -> list[dict]:
        """Returns check results compatible with BAGO --test JSON schema."""
        return [
            {
                "name": r.name,
                "passed": r.passed,
                "message": r.message,
                "severity": r.severity,
            }
            for r in self._results
        ]


# ── Registry-driven dispatcher preflight ─────────────────────────────────────

def run_from_registry(cmd: str, exit_on_fail: bool = True) -> bool:
    """Load preflight checks from tool_registry.py for `cmd` and run them.

    Uses importlib to avoid sys.path pollution. Returns True if all checks pass.
    Safe no-op when tool_registry.py doesn't exist or has no entry for `cmd`.
    """
    registry_path = _find_registry_dynamic()
    if not registry_path:
        return True

    spec = importlib.util.spec_from_file_location("_tool_registry_pf", registry_path)
    if spec is None:
        return True
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        return True

    entry = getattr(mod, "REGISTRY", {}).get(cmd)
    if not entry or not entry.preflight:
        return True

    pf = Preflight(cmd)
    for check in entry.preflight:
        if check.kind == "file":
            pf.require_file(check.value, check.message, check.severity)
        elif check.kind == "env":
            pf.require_env(check.value, check.message, check.severity)
        elif check.kind == "cmd":
            pf.require_cmd(check.value, check.message, check.severity)

    return pf.run(exit_on_fail=exit_on_fail)


# ── Policy enforcement (called by bago CLI) ───────────────────────────────────

def _get_policy(cmd: str) -> str:
    """Return preflight_policy for cmd from tool_registry. Defaults to 'optional'."""
    reg_path = _find_sibling("tool_registry")
    if not reg_path.exists():
        return "optional"
    mod = _load_mod(reg_path, "_bago_pfe_registry")
    if mod is None:
        return "optional"
    entry = getattr(mod, "REGISTRY", {}).get(cmd)
    if entry is None:
        return "optional"
    return getattr(entry, "preflight_policy", "optional")


def enforce(cmd: str, skip_preflight: bool = False) -> None:
    """Enforce preflight policy for cmd. May call sys.exit(1) if fail-closed.

    Args:
        cmd: The BAGO command being dispatched.
        skip_preflight: If True, skip checks (only honoured when policy != "required").

    Behaviour:
        policy="required"  → run checks; if missing/fail → sys.exit(1) with clear error
        policy="optional"  → run checks; if fail → print warning, continue
        policy="none"      → skip all checks silently
    """
    policy = _get_policy(cmd)

    if policy == "none":
        return

    if skip_preflight:
        if policy == "required":
            print(
                f"❌ --skip-preflight no está permitido para '{cmd}' (preflight_policy=required).",
                file=sys.stderr,
            )
            print("   Ejecuta: python3 bago doctor", file=sys.stderr)
            sys.exit(1)
        return

    ok = run_from_registry(cmd, exit_on_fail=False)

    if ok:
        return

    if policy == "required":
        print(
            f"\n❌ Preflight failed closed.\n"
            f"   Command: bago {cmd}\n"
            f"   Reason:  preflight checks fallaron (ver arriba).\n"
            f"   Usa:     python3 bago doctor",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  ⚠  Preflight warnings para '{cmd}' — continuando de todos modos.", file=sys.stderr)


# ── Self-tests ────────────────────────────────────────────────────────────────

def _self_tests() -> None:
    results: list[dict] = []

    def _check(name: str, cond: bool, msg: str) -> None:
        results.append({"name": name, "passed": cond, "message": msg})
        print(f"  {'✅' if cond else '❌'} {name}: {msg}")

    pf = Preflight("test")
    pf.require_file("/nonexistent/bago_test_xyz_99999.json")
    _check("T1:file-missing-detected", not pf.passed, "missing file → not passed")

    pf2 = Preflight("test")
    pf2.require_file(__file__)
    _check("T2:file-exists-passes", pf2.passed, "existing file → passed")

    pf3 = Preflight("test")
    pf3.require_env("_BAGO_NONEXISTENT_VAR_XYZ_12345")
    _check("T3:env-missing-detected", not pf3.passed, "missing env var → not passed")

    pf4 = Preflight("test")
    pf4.require_env("PATH")
    _check("T4:env-exists-passes", pf4.passed, "$PATH defined → passed")

    pf5 = Preflight("test")
    pf5.require_cmd("python3")
    _check("T5:cmd-exists-passes", pf5.passed, "python3 found → passed")

    pf6 = Preflight("test")
    pf6.require_file("/nonexistent/warn_only.json", severity="warning")
    ok = pf6.run(exit_on_fail=False, silent=True)
    _check("T6:warning-does-not-block", ok, "warning-only check → run() returns True")

    pf7 = Preflight("test")
    pf7.require_file("/nonexistent/schema_test.json")
    checks = pf7.to_json_checks()
    schema_ok = (
        len(checks) == 1
        and all(k in checks[0] for k in ("name", "passed", "message", "severity"))
    )
    _check("T7:json-schema-correct", schema_ok,
           "to_json_checks() returns {name, passed, message, severity}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n  {passed}/{total} tests pasaron")
    print(json.dumps({"tool": "preflight_engine", "status": "ok" if passed == total else "fail",
                      "checks": results}))
    sys.exit(0 if passed == total else 1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if "--test" in args:
        _self_tests()
    elif "--tool" in args:
        idx = args.index("--tool")
        if idx + 1 >= len(args):
            print("  ✗ --tool requiere un nombre de comando", file=sys.stderr)
            sys.exit(1)
        cmd = args[idx + 1]
        run_from_registry(cmd)
        print(f"  ✅ Preflight OK para '{cmd}'")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
