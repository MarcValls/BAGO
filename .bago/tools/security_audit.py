#!/usr/bin/env python3
"""DEPRECATED thin wrapper — use `bago audit security` or `audit/_security.py` directly.

Este archivo se conserva para compatibilidad con scripts que invocan
security_audit.py directamente. No añadir lógica nueva aquí.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit._security import *  # noqa: F401,F403
from audit._security import _self_test, main  # noqa: F401

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv[1:]))
