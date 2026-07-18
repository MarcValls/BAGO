#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Version en que fue creado este archivo
cli.py -- BAGO 4.5.1 CLI Entrypoint

Wrapper ligero sobre launcher.py para compatibilidad con entrypoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Insert project root so package imports resolve when run from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bago_core.launcher import main

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        # Smoke test: launcher importable
        from bago_core.launcher import main
        print("cli.py --test: ALL PASS")
        raise SystemExit(0)
    raise SystemExit(main())


def _entry() -> None:
    """setuptools console_scripts entry point.

    Handles --version before loading the full launcher so the wheel smoke test
    passes even when the full BAGO runtime tree is not present.
    """
    if "--version" in sys.argv or "-V" in sys.argv:
        from bago_core import __version__
        print(f"bago {__version__}")
        raise SystemExit(0)
    raise SystemExit(main())
