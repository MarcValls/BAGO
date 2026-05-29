#!/usr/bin/env python3
"""DEPRECATED thin wrapper — use `bago audit full` or `audit/_v2.py` directly.

Este archivo se conserva para compatibilidad con scripts y pack.json que
invocan audit_v2.py directamente. No añadir lógica nueva aquí.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit._v2 import *  # noqa: F401,F403
from audit._v2 import _self_test, main  # noqa: F401

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv[1:]))
