#!/usr/bin/env python3
"""Startup inventory helpers for the BAGO REPL."""

from __future__ import annotations

import sys
from pathlib import Path

import renderer as R


def _bago_install_root() -> Path | None:
    """Resuelve el directorio raíz de BAGO (donde están .bago/tools/)."""
    # .bago/chat/repl_inventory.py → parents[2] es el raíz de BAGO (BAG4.8/)
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2],           # .../BAG4.8/ from .bago/chat/repl_inventory.py
    ]
    for c in candidates:
        if (c / ".bago" / "tools").is_dir():
            return c
    return None


def print_workspace_inventory(base_path: Path) -> None:
    try:
        import bago_inventory
        data = bago_inventory.gather_inventory(base_path)

        # También contar tools de la instalación de BAGO
        bago_root = _bago_install_root()
        if bago_root and bago_root != base_path:
            bago_data = bago_inventory.gather_inventory(bago_root)
            bago_tools = bago_data.get("tools", [])
            bago_agents = bago_data.get("agents", [])
            bago_scripts = bago_data.get("scripts", [])
            bago_modules = bago_data.get("modules", [])
            if bago_tools:
                data["tools"] = data.get("tools", []) + bago_tools
            if bago_agents:
                data["agents"] = data.get("agents", []) + bago_agents
            if bago_modules:
                data["modules"] = data.get("modules", []) + bago_modules
            s = data.get("summary", {})
            s["tool_files"] = len(data.get("tools", []))
            s["agent_files"] = len(data.get("agents", []))
            s["module_files"] = len(data.get("modules", []))
            s["total_pieces"] = s["tool_files"] + s["agent_files"] + s.get("script_files", 0) + s["module_files"]
            data["summary"] = s

        print(R.bold("\nInventario del workspace"))
        print(R.dim(bago_inventory.format_startup_text(data, limit=4)))
        print()
        print(R.dim("Usa `bago inventory` para ver el catalogo completo."))
        print()
    except Exception as exc:  # noqa: BLE001
        print(R.warn(f"Inventario no disponible: {exc}"))
        print()
