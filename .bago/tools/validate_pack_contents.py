#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim — validate_pack_contents merged into validate.py (contents subcommand)."""

from bago_utils import load_json, save_json, timestamp_iso
import subprocess, sys
from pathlib import Path

extra = sys.argv[1:]  # pass-through zip path if provided
result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "contents", *extra],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())

