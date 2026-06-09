#!/usr/bin/env python3
"""
version.py — BAGO Version Index Reader

Lee la versión actual desde versions.json (raíz de BAGO).
Es la única fuente de verdad de la versión en runtime.

Uso:
    from version import CURRENT          # "4.3.0"
    from version import at_date          # versión activa en una fecha dada
    from version import history          # lista completa de versiones
"""

from __future__ import annotations

_CREATED_VERSION = "4.5.0"

import json
from datetime import date
from paths import resource_path

# versions.json vive en la raiz fuente o en el bundle empaquetado.
_INDEX_PATH = resource_path("versions.json")


def _load() -> dict:
    return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))


def current() -> str:
    """Devuelve la versión actual de BAGO."""
    return _load()["current"]


def at_date(date_str: str) -> str:
    """Devuelve la versión que estaba activa en la fecha ISO dada (YYYY-MM-DD)."""
    data = _load()
    target = date.fromisoformat(date_str)
    for entry in reversed(data["history"]):
        if target >= date.fromisoformat(entry["released"]):
            return entry["version"]
    return data["history"][0]["version"]


def history() -> list[dict]:
    """Devuelve el historial completo de versiones."""
    return _load()["history"]


# Constante de módulo: versión actual en el momento de importar
CURRENT: str = current()
