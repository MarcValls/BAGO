#!/usr/bin/env python3
"""Portable preflight check engine.

Usage:
    python .bago/tools/preflight_engine.py [--root DIR] [--cmd COMMAND]
    python .bago/tools/preflight_engine.py --test
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, NamedTuple

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root

TOOLS_DIR = Path(__file__).resolve().parent
TEST_WORKSPACE = TOOLS_DIR / "_selftest_preflight_engine"


def _find_sibling(stem: str) -> Path:
    direct = TOOLS_DIR / f"{stem}.py"
    if direct.exists():
        return direct
    for found in TOOLS_DIR.parent.rglob(f"{stem}.py"):
        if not found.name.startswith(".") and ".healer.bak" not in found.name:
            return found
    return direct


def _find_tool_dynamic(stem: str) -> Path | None:
    direct = TOOLS_DIR / f"{stem}.py"
    if direct.exists():
        return direct
    for found in TOOLS_DIR.parent.rglob(f"{stem}.py"):
        if not found.name.startswith(".") and ".healer.bak" not in found.name:
            return found
    return None


def _find_registry_dynamic() -> Path | None:
    path = _find_sibling("tool_registry")
    return path if path.exists() else None


def _load_mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(name, None)
        return None


class CheckResult(NamedTuple):
    name: str
    kind: str
    passed: bool
    severity: str
    message: str


class Preflight:
    def __init__(self, tool_name: str, root: str | Path | None = None) -> None:
        self.tool_name = tool_name
        self.root = Path(root).resolve() if root else None
        self._results: list[CheckResult] = []

    def _resolve_required_path(self, path: str | Path) -> Path:
        requested = Path(path)
        if requested.is_absolute():
            return requested
        if self.root is not None:
            return (self.root / requested).resolve()
        return requested

    def require_file(self, path: str | Path, msg: str = "", severity: str = "error") -> "Preflight":
        requested = Path(path)
        resolved = self._resolve_required_path(requested)
        ok = resolved.exists()
        if not ok and self.root is None and len(requested.parts) == 1:
            fallback = _find_tool_dynamic(requested.stem)
            if fallback is not None:
                resolved = fallback
                ok = resolved.exists()
        self._results.append(CheckResult(
            name=f"file:{requested.name}",
            kind="file",
            passed=ok,
            severity=severity,
            message=msg or (f"file present: {resolved}" if ok else f"required file missing: {resolved}"),
        ))
        return self

    def require_env(self, var: str, msg: str = "", severity: str = "error") -> "Preflight":
        ok = bool(os.environ.get(var))
        self._results.append(CheckResult(
            name=f"env:{var}",
            kind="env",
            passed=ok,
            severity=severity,
            message=msg or (f"env present: {var}" if ok else f"required env missing: {var}"),
        ))
        return self

    def require_cmd(self, cmd: str, msg: str = "", severity: str = "error") -> "Preflight":
        ok = shutil.which(cmd) is not None
        self._results.append(CheckResult(
            name=f"cmd:{cmd}",
            kind="cmd",
            passed=ok,
            severity=severity,
            message=msg or (f"command available: {cmd}" if ok else f"required command missing: {cmd}"),
        ))
        return self

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self._results if result.severity == "error")

    @property
    def warnings(self) -> list[CheckResult]:
        return [result for result in self._results if not result.passed and result.severity == "warning"]

    def run(self, exit_on_fail: bool = True, silent: bool = False) -> bool:
        warnings = [result for result in self._results if not result.passed and result.severity == "warning"]
        errors = [result for result in self._results if not result.passed and result.severity == "error"]
        if not silent:
            for result in warnings:
                print(f"[WARN] {result.message}")
        if not errors:
            return True
        if not silent:
            for result in errors:
                print(f"[ERROR] {result.message}", file=sys.stderr)
        if exit_on_fail:
            raise SystemExit(1)
        return False

    def to_json_checks(self) -> list[dict[str, Any]]:
        return [
            {
                "name": result.name,
                "passed": result.passed,
                "message": result.message,
                "severity": result.severity,
            }
            for result in self._results
        ]


def run_from_registry(cmd: str, exit_on_fail: bool = True, root: str | Path | None = None) -> bool:
    registry_path = _find_registry_dynamic()
    if registry_path is None:
        return True
    module = _load_mod(registry_path, "_tool_registry_pf")
    if module is None:
        return True
    entry = getattr(module, "REGISTRY", {}).get(cmd)
    if not entry or not getattr(entry, "preflight", None):
        return True

    preflight = Preflight(cmd, root=root)
    for check in entry.preflight:
        if check.kind == "file":
            preflight.require_file(check.value, check.message, check.severity)
        elif check.kind == "env":
            preflight.require_env(check.value, check.message, check.severity)
        elif check.kind == "cmd":
            preflight.require_cmd(check.value, check.message, check.severity)
    return preflight.run(exit_on_fail=exit_on_fail)


def _get_policy(cmd: str) -> str:
    registry_path = _find_sibling("tool_registry")
    if not registry_path.exists():
        return "optional"
    module = _load_mod(registry_path, "_bago_pfe_registry")
    if module is None:
        return "optional"
    entry = getattr(module, "REGISTRY", {}).get(cmd)
    if entry is None:
        return "optional"
    return getattr(entry, "preflight_policy", "optional")


def enforce(cmd: str, skip_preflight: bool = False, root: str | Path | None = None) -> None:
    policy = _get_policy(cmd)
    if policy == "none":
        return
    if skip_preflight and policy == "required":
        print(f"[ERROR] --skip-preflight is not allowed for '{cmd}'.", file=sys.stderr)
        raise SystemExit(1)
    if skip_preflight:
        return
    ok = run_from_registry(cmd, exit_on_fail=False, root=root)
    if ok:
        return
    if policy == "required":
        print(f"[ERROR] Preflight failed for command: {cmd}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[WARN] Preflight reported issues for '{cmd}' but execution continues.", file=sys.stderr)


def _known_command() -> str:
    candidates = [Path(sys.executable).name, "python", "py", "cmd"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return Path(sys.executable).name


def _reset_workspace() -> Path:
    if TEST_WORKSPACE.exists():
        shutil.rmtree(TEST_WORKSPACE)
    TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return TEST_WORKSPACE


def run_self_tests() -> int:
    workspace = _reset_workspace()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        results.append((name, condition, detail))

    existing_file = workspace / "present.txt"
    existing_file.write_text("ok\n", encoding="utf-8")

    pf_file_pass = Preflight("sample", root=workspace)
    pf_file_pass.require_file("present.txt")
    check("require_file_pass", pf_file_pass.passed, "existing file passes")

    pf_file_fail = Preflight("sample", root=workspace)
    pf_file_fail.require_file("missing.txt")
    check("require_file_fail", not pf_file_fail.passed, "missing file fails")

    os.environ["BAGO_PREFLIGHT_TEST_ENV"] = "1"
    pf_env_pass = Preflight("sample")
    pf_env_pass.require_env("BAGO_PREFLIGHT_TEST_ENV")
    check("require_env_pass", pf_env_pass.passed, "existing env passes")
    os.environ.pop("BAGO_PREFLIGHT_TEST_ENV", None)

    pf_env_fail = Preflight("sample")
    pf_env_fail.require_env("BAGO_PREFLIGHT_TEST_ENV")
    check("require_env_fail", not pf_env_fail.passed, "missing env fails")

    pf_cmd = Preflight("sample")
    pf_cmd.require_cmd(_known_command())
    check("require_cmd", pf_cmd.passed, "known command is found")

    pf_warning = Preflight("sample", root=workspace)
    pf_warning.require_file("missing-warning.txt", severity="warning")
    check("warnings_vs_errors", pf_warning.run(exit_on_fail=False, silent=True), "warning-only preflight does not block")

    pf_json = Preflight("sample", root=workspace)
    pf_json.require_file("missing-json.txt")
    checks = pf_json.to_json_checks()
    schema_ok = len(checks) == 1 and all(key in checks[0] for key in ("name", "passed", "message", "severity"))
    check("to_json_checks", schema_ok, "JSON schema is stable")

    pf_run = Preflight("sample", root=workspace)
    pf_run.require_file("missing-run.txt")
    check("run_return_value", pf_run.run(exit_on_fail=False, silent=True) is False, "run returns False on error")

    shutil.rmtree(workspace, ignore_errors=True)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable preflight engine")
    parser.add_argument("--root", default="", help="Project root for relative file checks")
    parser.add_argument("--cmd", default="", help="Registry command to evaluate")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.test:
        return run_self_tests()
    if args.cmd:
        ok = run_from_registry(args.cmd, exit_on_fail=False, root=get_scan_root(args.root))
        print(f"Preflight {'OK' if ok else 'FAIL'} for '{args.cmd}'")
        return 0 if ok else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
