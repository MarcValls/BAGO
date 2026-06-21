#!/usr/bin/env python3
"""Startup inventory helpers for the BAGO REPL."""

from __future__ import annotations

import sys
from pathlib import Path

import renderer as R


def print_workspace_inventory(base_path: Path) -> None:
    try:
        import bago_inventory
        data = bago_inventory.gather_inventory(base_path)
        print(R.bold("\nInventario del workspace"))
        print(R.dim(bago_inventory.format_startup_text(data, limit=4)))
        print()
        print(R.dim("Usa `bago inventory` para ver el catalogo completo."))
        print()
    except Exception as exc:  # noqa: BLE001
        print(R.warn(f"Inventario no disponible: {exc}"))
        print()
