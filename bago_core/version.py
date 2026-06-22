#!/usr/bin/env python3
"""bago_core/version.py — Version shim for wheel entry point.

When BAGO runs from source, launcher.py inserts .bago/core into sys.path and
imports version.CURRENT from there. When BAGO runs as an installed wheel, that
path is unavailable; this shim provides the same interface.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the wheel/source package importable when this file is run standalone.
_pkg_root = Path(__file__).resolve().parent
_repo_root = _pkg_root.parent
for _candidate in (_pkg_root, _repo_root):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from bago_core.versioning import at_date, current, history  # noqa: F401

CURRENT: str = current()
