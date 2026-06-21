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

from bago_core.versioning import at_date, current, history  # noqa: E402


# Constante de módulo: versión actual en el momento de importar
CURRENT: str = current()
