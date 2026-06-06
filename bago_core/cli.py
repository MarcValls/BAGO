#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Version en que fue creado este archivo
cli.py -- BAGO 4.3.0 CLI Entrypoint

Wrapper ligero sobre launcher.py para compatibilidad con entrypoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Insert bago_core path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from launcher import main

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        # Smoke test: launcher importable
        from launcher import main
        print("cli.py --test: ALL PASS")
        raise SystemExit(0)
    raise SystemExit(main())
