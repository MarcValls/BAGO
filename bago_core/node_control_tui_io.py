#!/usr/bin/env python3
"""FASE 10: low-level input primitives for the Node Control TUI (R0, R1).

This module owns only the side-effecting IO of the TUI: reading stdin
and writing stdout. It does not know about Node Control state or the
BAGO API; it is reused by the higher-level menu loops in
:mod:`bago_core.node_control_tui`.

Owns:
- `_read_input` -- one-line read with EOF handling
- `_prompt_text` -- read a free-form string
- `_prompt_choice` -- numbered choice from a list (with 0=back)
- `_pause` -- "Enter to continue"
- `_print_tui_header` -- the per-screen header
- `_print_block` -- title + separator + body

R0-R10:
- R0: <80 lines target
- R1: no business logic, no Node Control imports
- R8: the only place in the TUI stack allowed to call ``print()`` and
  ``input()``.
"""
from __future__ import annotations

import sys
from typing import Any


def _read_input(prompt: str) -> str | None:
    try:
        return input(prompt)
    except EOFError:
        return None


def _prompt_text(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = _read_input(f"{prompt}{suffix}: ")
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _prompt_choice(prompt: str, options: list[str], default_index: int = 0) -> int:
    if not options:
        raise ValueError("options cannot be empty")
    default_index = max(0, min(default_index, len(options) - 1))
    for idx, option in enumerate(options, start=1):
        print(f"  {idx}. {option}")
    print("  0. Volver")
    while True:
        raw_value = _read_input(f"{prompt} [{default_index + 1}]: ")
        if raw_value is None:
            return -1
        raw = raw_value.strip().lower()
        if raw == "":
            return default_index
        if raw in {"0", "q", "quit", "salir", "esc"}:
            return -1
        if raw.isdigit():
            selected = int(raw) - 1
            if 0 <= selected < len(options):
                return selected
        print("Selecciona un numero valido.")


def _pause() -> None:
    try:
        input("\nEnter para continuar...")
    except EOFError:
        pass


def _print_tui_header(summary: dict[str, Any]) -> None:
    print("\nBAGO NODE CONTROL · TERMINAL")
    print("=" * 72)
    print(f"Base path   : {summary['base_path']}")
    print(f"Store root  : {summary['store_root']}")
    print(f"Installs    : {summary['installations']}")
    print(f"Pieces      : {summary['pieces']}")
    print(f"Connectors  : {summary['connectors']}")
    print(f"Compat rows : {summary['compatibility_rows']}")
    print(f"Evidence    : {summary['evidence_file']}")
    mode_bits = ", ".join(f"{k}={v}" for k, v in summary["modes"].items() if v)
    if mode_bits:
        print(f"Modes       : {mode_bits}")
    print("=" * 72)


def _print_block(title: str, text: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    print(text)


# Public aliases (R1) for use by other tui modules
read_input = _read_input
pause = _pause
print_header = _print_tui_header
print_block = _print_block
