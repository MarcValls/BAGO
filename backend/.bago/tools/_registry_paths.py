"""_registry_paths.py — Path constants shared across registry sub-modules.

Internal module: import via tool_registry, not directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent   # .bago/tools/
BAGO_ROOT = TOOLS_DIR.parent        # .bago/
REPO_ROOT = BAGO_ROOT.parent        # repo raíz
PYTHON: str = sys.executable or "python"


def _self_test() -> int:
    """Minimal R001 self-test: verify this tool compiles."""
    import py_compile
    py_compile.compile(__file__, doraise=True)
    print(f"{__file__}: self-test ok")
    return 0

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_self_test())
