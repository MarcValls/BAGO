"""_registry_paths.py — Path constants shared across registry sub-modules.

Internal module: import via tool_registry, not directly.
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

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent   # .bago/tools/
BAGO_ROOT = TOOLS_DIR.parent        # .bago/
REPO_ROOT = BAGO_ROOT.parent        # repo raíz
PYTHON: str = sys.executable or "python3"
