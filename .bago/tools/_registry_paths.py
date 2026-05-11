"""_registry_paths.py — Path constants shared across registry sub-modules.

Internal module: import via tool_registry, not directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent   # .bago/tools/
BAGO_ROOT = TOOLS_DIR.parent        # .bago/
REPO_ROOT = BAGO_ROOT.parent        # repo raíz
PYTHON: str = sys.executable or "python3"
