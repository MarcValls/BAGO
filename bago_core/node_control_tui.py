#!/usr/bin/env python3
"""FASE 10: Node Control TUI dispatcher (R0, R1, R7).

This module is the *thin* top-level entry point for the interactive
TUI. It owns the main read-loop, the menu header, and the dispatch to
the read-only (``node_control_tui_info``) and write-side
(``node_control_tui_write``) menus. The actual prompts, header, and
print helpers live in :mod:`bago_core.node_control_tui_io`; the
business logic is fully delegated through the ``api`` dict.

Owns:
- `interactive_tui` -- public entry point; renders status once and
  dispatches to the per-menu helpers (R4: thin orchestrator).

R0-R10:
- R0: <80 lines target
- R1: imports the two menu siblings and the IO layer; no business
  logic, no direct registry calls.
- R7: dispatch by domain (status/pieces/connectors/matrix/validate
  for info; export/connect/disconnect/set-mode for write).
- R8: the only place allowed to call ``sys.stdin.isatty()`` for the
  TUI gate.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from bago_core.node_control_render import render_text
from bago_core.node_control_tui_info import _run_info_menus
from bago_core.node_control_tui_io import _pause, _print_tui_header, _read_input
from bago_core.node_control_tui_write import _run_write_menus


def _print_menu() -> None:
    print("1. Estado")
    print("2. Piezas")
    print("3. Conectores")
    print("4. Matriz")
    print("5. Validar")
    print("6. Exportar")
    print("7. Conectar")
    print("8. Desconectar")
    print("9. Cambiar modo")
    print("0. Salir")


def _read_choice() -> str | None:
    raw = _read_input("\nOpcion: ")
    if raw is None:
        print("\nEntrada cerrada. Saliendo del gestor de instalaciones.")
        return None
    return raw.strip().lower()


def interactive_tui(
    base_path: str | Path,
    api: dict[str, Callable[..., Any]],
) -> int:
    """Run the Node Control interactive TUI (FASE 10 dispatcher)."""
    status_fn = api["status"]

    # Non-TTY: behave like a one-shot status print, do not enter the loop.
    if not sys.stdin.isatty():
        print(render_text(status_fn(base_path)))
        return 0

    while True:
        summary = status_fn(base_path)
        _print_tui_header(summary)
        _print_menu()
        choice = _read_choice()
        if choice is None:
            return 0
        if choice in {"0", "q", "quit", "salir"}:
            print("Saliendo del gestor de instalaciones.")
            return 0

        # Read-only menus (status, pieces, connectors, matrix, validate).
        if _run_info_menus(
            choice=choice, base_path=base_path, summary=summary, api=api,
        ):
            continue
        # Write-side menus (export, connect, disconnect, set_mode).
        if _run_write_menus(
            choice=choice, base_path=base_path, summary=summary, api=api,
        ):
            continue

        print("Opcion no valida.")
        _pause()
