#!/usr/bin/env python3
"""runtime.py — BAGO runtime path resolver (PR-06 Kernel Lockdown).

Provides a single authoritative source for runtime path resolution.
All tools should import from here instead of hardcoding paths.

Environment variables (override defaults):
    BAGO_ROOT      — repo root (parent of .bago/), auto-detected if unset
    BAGO_STATE_DIR — runtime state directory, defaults to <root>/.bago/state

Usage:
    from runtime import get_state_dir, get_root, state_path

    state = get_state_dir()
    global_state = state_path("global_state.json")
    sessions_dir = state_path("sessions")
"""
from __future__ import annotations

import os
from pathlib import Path

from bago_core.server_effects import ensure_runtime_state_dirs, seed_runtime_state_examples


def get_root() -> Path:
    """Return BAGO repo root (parent of .bago/).

    Resolution order:
    1. BAGO_ROOT env var
    2. Walk up from this file until we find .bago/
    3. CWD fallback
    """
    env_root = os.environ.get("BAGO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    # Walk up from this file (runtime.py lives in .bago/core/)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".bago").is_dir():
            return parent

    return Path.cwd()


def get_state_dir() -> Path:
    """Return BAGO runtime state directory.

    Resolution order:
    1. BAGO_STATE_DIR env var
    2. <bago_root>/.bago/state
    """
    env_state = os.environ.get("BAGO_STATE_DIR")
    if env_state:
        return Path(env_state).resolve()
    return get_root() / ".bago" / "state"


def state_path(*parts: str) -> Path:
    """Return an absolute path inside the state directory.

    Example:
        state_path("global_state.json")      → .bago/state/global_state.json
        state_path("sessions", "my_session") → .bago/state/sessions/my_session
    """
    return get_state_dir().joinpath(*parts)


def ensure_state_dir() -> Path:
    """Ensure the state directory exists (with required subdirs). Returns it."""
    state = get_state_dir()
    ensure_runtime_state_dirs(state)
    return state


def init_state_from_example() -> bool:
    """Copy state.example/ files to state/ if state/ is missing or empty.

    Returns True if files were copied, False if state already existed.
    """
    root  = get_root()
    state = get_state_dir()
    example = root / ".bago" / "state.example"

    result = seed_runtime_state_examples(state, example)
    return bool(result.get("copied"))
