#!/usr/bin/env python3
"""FASE 6.4: filesystem facts for BAGO installation scanning.

Pure data: takes a Path, returns a dict of metadata. No I/O orchestration,
no CLI. Used by :mod:`bago_core.cli_installs_discovery`.

R0-R10:
- R0: <100 lines
- R1: zero business logic, zero formatting
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import supervisor_state_file, legacy_user_root


def pid_alive(pid: int) -> bool:
    """Return True if a Windows process with the given pid is still running.

    Uses ctypes to call OpenProcess + GetExitCodeProcess. Returns False on
    any error (missing pid, no permissions, etc.). On non-Windows platforms
    this always returns False; the install scanner is Windows-only.
    """
    if not pid:
        return False
    try:
        PROCESS_QUERY_LIMITED = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            return False
        STILL_ACTIVE = 259
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == STILL_ACTIVE
    except Exception:
        return False


def short_sig(p: Path) -> str:
    """Return the first 16 hex chars of sha256 of a file, or empty string."""
    if not p.is_file():
        return ""
    try:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        return h[:16] + "..."
    except Exception:
        return ""


def read_version(root: Path) -> str:
    """Read `release_version.txt` if it exists, else empty string."""
    rv = root / "release_version.txt"
    if rv.is_file():
        return rv.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def read_tag(root: Path) -> str:
    """Return the stem of the most recent v*.json in bago_core/tags, or ''."""
    tags_dir = root / "bago_core" / "tags"
    if not tags_dir.is_dir():
        return ""
    versions = []
    for f in tags_dir.glob("v*.json"):
        versions.append((f.stat().st_mtime, f.stem))
    if not versions:
        return ""
    versions.sort(reverse=True)
    return versions[0][1]


def supervisor_state(root: Path) -> tuple[dict[str, Any] | None, bool]:
    """Return (state_dict, alive_bool) for the supervisor of `root`.

    Tries `<root>/state/supervisor.json` first (per-installation state), then
    falls back to `~/.bago/state/supervisor.json` (global state). Returns
    (None, False) if neither exists or the file is malformed.
    """
    state = supervisor_state_file()
    if not state.is_file():
        state = root / "state" / "supervisor.json"
    if not state.is_file():
        state = legacy_user_root() / "state" / "supervisor.json"
    if not state.is_file():
        return None, False
    try:
        payload = json.loads(state.read_text(encoding="utf-8"))
        info = {
            "pid":     payload.get("pid"),
            "version": payload.get("version"),
            "started": payload.get("started_at"),
            "events":  payload.get("events", 0),
        }
        alive = bool(payload.get("pid")) and pid_alive(int(payload["pid"]))
        return info, alive
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}, False
