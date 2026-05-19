"""Windows launcher smoke tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
CMD_LAUNCHER = ROOT / "bago.cmd"


@pytest.mark.skipif(sys.platform != "win32", reason="bago.cmd is Windows-only")
def test_bago_cmd_delegates_to_python_launcher():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [str(CMD_LAUNCHER), "hello", "--quick"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        env=env,
    )

    assert result.returncode == 0
    assert "BAGO" in result.stdout
    assert "hello" in result.stdout
