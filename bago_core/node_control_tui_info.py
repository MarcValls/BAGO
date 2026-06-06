#!/usr/bin/env python3
"""FASE 10: read-only menus for the Node Control TUI (R0, R1, R8).

This module owns the *information* menus: status, pieces, connectors,
matrix, validate. They never mutate the registry; the API dict passed
in is the only side-channel for rendering (no prints outside this
module's helpers).

Owns:
- `_render_status`, `_render_pieces_menu`, `_render_connectors_menu`,
  `_render_matrix_menu`, `_render_validate_menu`
- `_run_info_menus` -- top-level dispatch (R4)

R0-R10:
- R0: <120 lines target
- R1: imports from `node_control_tui_io` (printing) and
  `node_control_render` (text rendering); no business logic.
- R8: every menu returns after `_pause()`; no ``print()`` outside the
  IO helpers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from bago_core.node_control_render import (
    render_connectors,
    render_matrix,
    render_pieces,
    render_text,
)
from bago_core.node_control_tui_io import (
    _pause,
    _print_block,
    _print_tui_header,
    _read_input,
)


def _render_status(summary: dict[str, Any]) -> None:
    _print_block("Estado", render_text(summary))
    _pause()


def _render_pieces_menu(base_path: Path, list_pieces_fn: Callable[..., Any]) -> None:
    payload = list_pieces_fn(base_path)
    _print_block("Piezas", render_pieces(payload))
    _pause()


def _render_connectors_menu(base_path: Path, list_connectors_fn: Callable[..., Any]) -> None:
    payload = list_connectors_fn(base_path)
    _print_block("Conectores", render_connectors(payload))
    _pause()


def _render_matrix_menu(base_path: Path, matrix_fn: Callable[..., Any]) -> None:
    payload = matrix_fn(base_path)
    _print_block("Matriz", render_matrix(payload))
    _pause()


def _render_validate_menu(base_path: Path, validate_fn: Callable[..., Any]) -> None:
    ok, payload = validate_fn(base_path)
    _print_block("Validacion", json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nResultado: {'OK' if ok else 'FAIL'}")
    _pause()


def _run_info_menus(
    *,
    choice: str,
    base_path: Path,
    summary: dict[str, Any],
    api: dict[str, Callable[..., Any]],
) -> bool:
    """Handle a single read-only menu selection. Returns True if handled."""
    if choice in {"1", "status", ""}:
        _render_status(summary)
        return True
    if choice in {"2", "pieces"}:
        _render_pieces_menu(base_path, api["list_pieces"])
        return True
    if choice in {"3", "connectors"}:
        _render_connectors_menu(base_path, api["list_connectors"])
        return True
    if choice in {"4", "matrix"}:
        _render_matrix_menu(base_path, api["matrix"])
        return True
    if choice in {"5", "validate"}:
        _render_validate_menu(base_path, api["validate"])
        return True
    return False
