#!/usr/bin/env python3
"""FASE 6.4: aggregate counters for the install scan output.

Pure reduction: takes a list of installation dicts, returns a summary dict.
No I/O, no JSON. Consumed by :mod:`bago_core.cli_installs_cli`.

R0-R10:
- R0: <50 lines
- R1: zero side-effects
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any


def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce installation dicts into an aggregate summary."""
    alive = [i for i in items if i.get("supervisor_alive")]
    has_sup = [i for i in items if i.get("has_supervisor")]
    return {
        "scanned_at":   datetime.datetime.now().isoformat(timespec="seconds"),
        "platform":     sys.platform,
        "python":       sys.version.split()[0],
        "home":         str(Path.home()),
        "total_paths":  len(items),
        "existing":     sum(1 for i in items if i["exists"]),
        "missing":      sum(1 for i in items if not i["exists"]),
        "with_supervisor":   len(has_sup),
        "with_supervisor_alive": len(alive),
    }
