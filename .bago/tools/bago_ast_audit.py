#!/usr/bin/env python3
"""DEPRECATED thin wrapper — use `bago audit ast` or `audit/_ast.py` directly.

Este archivo se conserva para compatibilidad con scripts que invocan
bago_ast_audit.py directamente. No añadir lógica nueva aquí.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit._ast import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
