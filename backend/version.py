#!/usr/bin/env python3
"""Root version shim for source and release trees."""
from __future__ import annotations

from bago_core.versioning import current

CURRENT: str = current()
