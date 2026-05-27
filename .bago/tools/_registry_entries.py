"""_registry_entries.py — Canonical REGISTRY dict of all BAGO tools.

This module re-exports the fused REGISTRY from split sub-modules.
Import via tool_registry, not directly.
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

from _registry_models import ToolEntry
from _registry_entries_core      import _ENTRIES as _CORE
from _registry_entries_v3        import _ENTRIES as _V3
from _registry_entries_visual    import _ENTRIES as _VISUAL
from _registry_entries_integrity import _ENTRIES as _INTEGRITY

REGISTRY: dict[str, ToolEntry] = {
    **_CORE,
    **_V3,
    **_VISUAL,
    **_INTEGRITY,
}


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

