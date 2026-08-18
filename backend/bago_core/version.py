#!/usr/bin/env python3
"""bago_core/version.py -- Version shim for the entry point.

When BAGO runs from source, launcher.py adds the core package to sys.path and
imports version.CURRENT from there. When BAGO runs as an installed wheel, that
path is unavailable; this shim provides the same interface.
"""
from __future__ import annotations

from bago_core.versioning import at_date, current, history  # noqa: F401

CURRENT: str = current()
