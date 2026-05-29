#!/usr/bin/env python3
"""DEPRECATED thin wrapper — use `bago health score` or `health/_score.py` directly.

Este archivo se conserva para compatibilidad con scripts que invocan
health_score.py directamente. No añadir lógica nueva aquí. Ver
`health/README.md` para el índice completo de health tools.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from health._score import *  # noqa: F401,F403
from health._score import _self_test, main  # noqa: F401

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
