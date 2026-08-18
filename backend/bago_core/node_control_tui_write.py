#!/usr/bin/env python3
"""FASE 10: write-side menus for the Node Control TUI (R0, R1, R8).

This module owns the *mutation* menus: export, connect, disconnect,
set_mode. Each menu is a small R4 helper that delegates the actual
side-effect to a callable from the API dict; the menu only handles
prompting, rendering, and pause.

Owns:
- `_render_export_menu` -- export the registry
- `_render_connect_menu` -- pick install + piece + mode, then connect
- `_render_disconnect_menu` -- pick install + piece, then disconnect
- `_render_set_mode_menu` -- pick install + piece + mode, then set_mode
- `_select_installation`, `_select_piece`, `_prompt_mode`
- `_run_write_menus` -- top-level dispatch (R4)

R0-R10:
- R0: <200 lines target
- R1: imports from `node_control_tui_io` (printing) and
  `node_control_tui_info` (read-only helpers).
- R8: side effects go through the API dict, never ``open()`` /
  ``subprocess`` here.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from bago_core.node_control_tui_io import (
    _pause,
    _print_block,
    _print_tui_header,
    _prompt_choice,
    _prompt_text,
)

# Canonical mode labels shown to the user. The first list is for display;
# the second is the wire mode name passed to the API.
_DISPLAY_MODES = ["connected", "shadow", "locked", "read-only", "writable overlay"]
_WIRE_MODES = ["connected", "shadow", "locked", "readonly", "overlay"]


def _select_installation(summary: dict[str, Any]) -> dict[str, Any] | None:
    installs = summary.get("installations_data", [])
    if not installs:
        print("No hay instalaciones registradas.")
        return None
    options = [
        f"{item['installation_id']} | {item['path']} | {item.get('version', '')} | {item.get('profile', '')}"
        for item in installs
    ]
    index = _prompt_choice("Elige una installation", options, 0)
    if index < 0:
        return None
    return installs[index]


def _select_piece(summary: dict[str, Any]) -> dict[str, Any] | None:
    pieces = summary.get("pieces_data", [])
    if not pieces:
        print("No hay piezas registradas.")
        return None
    options = [
        f"{item['piece_id']} | {item['type']} | {item['scope']} | {item['version']}"
        for item in pieces
    ]
    index = _prompt_choice("Elige una piece", options, 0)
    if index < 0:
        return None
    return pieces[index]


def _prompt_mode(label: str) -> str | None:
    idx = _prompt_choice(label, _DISPLAY_MODES, 0)
    if idx < 0:
        return None
    return _WIRE_MODES[idx]


def _render_export_menu(base_path: Path, export_fn: Callable[..., Any]) -> None:
    default_name = f"node-control-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    output = _prompt_text("Ruta de exportacion", default_name)
    target = export_fn(base_path, output)
    print(f"Exportado en: {target}")
    _pause()


def _render_connect_menu(
    base_path: Path, summary: dict[str, Any], api: dict[str, Callable[..., Any]],
) -> None:
    install = _select_installation(summary)
    if install is None:
        _pause()
        return
    piece = _select_piece(summary)
    if piece is None:
        _pause()
        return
    mode = _prompt_mode("Modo")
    if mode is None:
        _pause()
        return
    payload = api["connect"](base_path, install["installation_id"], piece["piece_id"], mode)
    _print_block("Conexion", json.dumps(payload, indent=2, ensure_ascii=False))
    _pause()


def _render_disconnect_menu(
    base_path: Path, summary: dict[str, Any], api: dict[str, Callable[..., Any]],
) -> None:
    install = _select_installation(summary)
    if install is None:
        _pause()
        return
    piece = _select_piece(summary)
    if piece is None:
        _pause()
        return
    payload = api["disconnect"](base_path, install["installation_id"], piece["piece_id"])
    _print_block("Desconexion", json.dumps(payload, indent=2, ensure_ascii=False))
    _pause()


def _render_set_mode_menu(
    base_path: Path, summary: dict[str, Any], api: dict[str, Callable[..., Any]],
) -> None:
    install = _select_installation(summary)
    if install is None:
        _pause()
        return
    piece = _select_piece(summary)
    if piece is None:
        _pause()
        return
    mode = _prompt_mode("Nuevo modo")
    if mode is None:
        _pause()
        return
    payload = api["set_mode"](base_path, install["installation_id"], piece["piece_id"], mode)
    _print_block("Cambio de modo", json.dumps(payload, indent=2, ensure_ascii=False))
    _pause()


def _run_write_menus(
    *,
    choice: str,
    base_path: Path,
    summary: dict[str, Any],
    api: dict[str, Callable[..., Any]],
) -> bool:
    """Handle a single mutation menu selection. Returns True if handled."""
    if choice in {"6", "export"}:
        _render_export_menu(base_path, api["export_bundle"])
        return True
    if choice in {"7", "connect"}:
        _render_connect_menu(base_path, summary, api)
        return True
    if choice in {"8", "disconnect"}:
        _render_disconnect_menu(base_path, summary, api)
        return True
    if choice in {"9", "set-mode"}:
        _render_set_mode_menu(base_path, summary, api)
        return True
    return False
