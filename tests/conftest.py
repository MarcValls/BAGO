"""conftest.py — shared pytest fixtures for BAGO core tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Make .bago/tools and .bago/core importable from tests
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".bago" / "tools"))
sys.path.insert(0, str(REPO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(REPO_ROOT / "bago_core"))

_SUPERVISOR = REPO_ROOT / ".bago" / "supervision" / "supervisor.py"


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    """Lanza post_test_cleanup_loop automáticamente tras cada pytest.

    Solo activo si el supervisor existe y BAGO_SUPERVISION_SKIP no está set.
    Se ejecuta en background (no bloquea el exit de pytest).
    """
    import os
    if os.environ.get("BAGO_SUPERVISION_SKIP"):
        return
    if not _SUPERVISOR.exists():
        return
    try:
        subprocess.Popen(
            [sys.executable, str(_SUPERVISOR), "run",
             "--loop", "post_test_cleanup", "--dry-run"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # nunca bloquear pytest por el supervisor
