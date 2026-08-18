#!/usr/bin/env python3
"""
version.py — BAGO Version Index Reader

Lee la versión actual desde release_version.txt y, si no existe,
cae a versions.json. Es la fuente de verdad del runtime.

Uso:
    from version import CURRENT          # "4.7.0"
    from version import at_date          # versión activa en una fecha dada
    from version import history          # lista completa de versiones
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.versioning import at_date, current, history  # noqa: E402


# Constante de módulo: versión actual en el momento de importar
CURRENT: str = current()
