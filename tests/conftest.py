"""conftest.py — shared pytest fixtures for BAGO core tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Make .bago/tools and .bago/core importable from tests
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".bago" / "tools"))
sys.path.insert(0, str(REPO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(REPO_ROOT / "bago_core"))
