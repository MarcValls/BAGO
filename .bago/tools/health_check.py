#!/usr/bin/env python3
"""DEPRECATED thin wrapper — use `bago health check` or `health/_check.py` directly.

Este archivo se conserva para compatibilidad con scripts que invocan
health_check.py directamente. No añadir lógica nueva aquí. Ver
`health/README.md` para el índice completo de health tools.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from health._check import *  # noqa: F401,F403
from health._check import _self_test, main  # noqa: F401

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
