#!/usr/bin/env python3
"""preflight.py — Pre-flight checks declarativos para herramientas BAGO.

Permite declarar precondiciones (archivo existe, variable de entorno definida,
comando instalado) y verificarlas antes de ejecutar cualquier tool.

El dispatcher de `bago` ejecuta automáticamente los preflight checks declarados
en tool_registry.py para cada comando registrado, sin necesidad de modificar
cada tool individualmente.

Uso como biblioteca:
    from preflight import Preflight
    pf = Preflight("mi_tool")
    pf.require_file(".bago/state/global_state.json")
    pf.require_env("GITHUB_TOKEN", severity="warning")
    pf.require_cmd("git")
    ok = pf.run(exit_on_fail=True)

Uso como CLI (dispatcher feature):
    bago cosecha --preflight          # checks desde tool_registry
    python3 preflight.py --tool cosecha
    python3 preflight.py --test       # self-tests (7/7)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

TOOLS_DIR = Path(__file__).parent


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
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

    # ── Check builders ────────────────────────────────────────────────────────

    def require_file(
        self, path: "str | Path", msg: str = "", severity: str = "error"
    ) -> "Preflight":
        """Assert that a file or directory exists."""
        p = Path(path)
        ok = p.exists()
        self._results.append(CheckResult(
            name=f"file:{p.name}", kind="file", passed=ok, severity=severity,
            message=msg or (f"✓ {p}" if ok else f"✗ Archivo requerido no existe: {p}"),
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

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def passed(self) -> bool:
        """True when no error-severity check has failed."""
        return all(r.passed for r in self._results if r.severity == "error")

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self._results if not r.passed and r.severity == "warning"]

    # ── Runner ────────────────────────────────────────────────────────────────

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
    import importlib.util
    registry_path = TOOLS_DIR / "tool_registry.py"
    if not registry_path.exists():
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


# ── Self-tests ────────────────────────────────────────────────────────────────

def _self_tests() -> None:
    results: list[dict] = []

    def _check(name: str, cond: bool, msg: str) -> None:
        results.append({"name": name, "passed": cond, "message": msg})
        print(f"  {'✅' if cond else '❌'} {name}: {msg}")

    # T1: require_file — missing file → not passed
    pf = Preflight("test")
    pf.require_file("/nonexistent/bago_test_xyz_99999.json")
    _check("T1:file-missing-detected", not pf.passed, "missing file → not passed")

    # T2: require_file — this file exists → passed
    pf2 = Preflight("test")
    pf2.require_file(__file__)
    _check("T2:file-exists-passes", pf2.passed, "existing file → passed")

    # T3: require_env — non-existent var → not passed
    pf3 = Preflight("test")
    pf3.require_env("_BAGO_NONEXISTENT_VAR_XYZ_12345")
    _check("T3:env-missing-detected", not pf3.passed, "missing env var → not passed")

    # T4: require_env — PATH is always set → passed
    pf4 = Preflight("test")
    pf4.require_env("PATH")
    _check("T4:env-exists-passes", pf4.passed, "$PATH defined → passed")

    # T5: require_cmd — python3 is available → passed
    pf5 = Preflight("test")
    pf5.require_cmd("python3")
    _check("T5:cmd-exists-passes", pf5.passed, "python3 found → passed")

    # T6: warning-severity failure doesn't block run()
    pf6 = Preflight("test")
    pf6.require_file("/nonexistent/warn_only.json", severity="warning")
    ok = pf6.run(exit_on_fail=False, silent=True)
    _check("T6:warning-does-not-block", ok, "warning-only check → run() returns True")

    # T7: to_json_checks returns schema-compliant list
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
    print(json.dumps({"tool": "preflight", "status": "ok" if passed == total else "fail",
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
