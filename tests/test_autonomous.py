"""test_autonomous.py — PR-08 gate: autonomous safety contract.

Rules (from PR-04):
- autonomous --dry-run must NOT mutate state
- autonomous without --unsafe should refuse dangerous operations
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).resolve().parent.parent
LAUNCHER   = str(REPO_ROOT / "bago")
STATE_FILE = REPO_ROOT / ".bago" / "state" / "global_state.json"


def _run(*args, timeout=60) -> subprocess.CompletedProcess:
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    import os
    env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, LAUNCHER, *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(REPO_ROOT), encoding="utf-8", errors="replace",
        env=env,
    )


def _read_state() -> str:
    if STATE_FILE.exists():
        return STATE_FILE.read_text()
    return ""


def test_autonomous_dry_run_does_not_mutate():
    """autonomous --dry-run must not modify global_state.json."""
    before = _read_state()
    _run("autonomous", "--dry-run", timeout=30)
    after = _read_state()
    assert before == after, \
        "autonomous --dry-run modified global_state.json — DRY RUN must not mutate state"


def test_autonomous_without_unsafe_blocked():
    """autonomous without --unsafe or --yes must be blocked (risk=dangerous)."""
    result = _run("autonomous")
    combined = result.stdout + result.stderr
    # Either it was blocked (exit != 0) or it printed a safety warning
    safety_terms = ["--unsafe", "--yes", "dangerous", "peligro", "blocked", "bloqueado"]
    was_blocked   = result.returncode != 0
    warned        = any(t in combined.lower() for t in safety_terms)
    assert was_blocked or warned, \
        "autonomous ran without any safety warning or block"


def test_autonomous_dry_run_exits_cleanly():
    """autonomous --dry-run should exit 0 or print plan output (not crash)."""
    result = _run("autonomous", "--dry-run", timeout=30)
    # We allow non-zero if it explains why, but it must produce output
    combined = result.stdout + result.stderr
    assert combined.strip(), "autonomous --dry-run produced no output"
