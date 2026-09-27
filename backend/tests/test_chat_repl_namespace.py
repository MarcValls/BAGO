from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_production_repl_import_resolves_chat_commands_before_core_commands() -> None:
    script = r"""
from pathlib import Path
from bago_core.resolver import add_piece_paths, resolve_piece_path

add_piece_paths("core.package", "chat.package", "providers.package")
import repl

expected = (resolve_piece_path("chat.package") / "commands.py").resolve()
actual = Path(repl.commands.__file__).resolve()
assert actual == expected, f"REPL loaded {actual}, expected chat command module {expected}"
assert repl.execute_local_tty.__module__ == repl.commands.__name__
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
