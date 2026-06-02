#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from bago_core.node_control_render import render_connectors, render_matrix, render_pieces, render_text

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

def interactive_tui(
    base_path: str | Path,
    api: dict[str, Callable[..., Any]],
) -> int:
    status_fn = api["status"]
    list_pieces_fn = api["list_pieces"]
    list_connectors_fn = api["list_connectors"]
    matrix_fn = api["matrix"]
    validate_fn = api["validate"]
    export_fn = api["export_bundle"]
    connect_fn = api["connect"]
    disconnect_fn = api["disconnect"]
    set_mode_fn = api["set_mode"]

    if not __import__("sys").stdin.isatty():
        print(render_text(status_fn(base_path)))
        return 0

    while True:
        summary = status_fn(base_path)
        _print_tui_header(summary)
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
        choice_raw = _read_input("\nOpcion: ")
        if choice_raw is None:
            print("\nEntrada cerrada. Saliendo del gestor de instalaciones.")
            return 0
        choice = choice_raw.strip().lower()

        if choice in {"0", "q", "quit", "salir"}:
            print("Saliendo del gestor de instalaciones.")
            return 0
        if choice in {"1", "status", ""}:
            _print_block("Estado", render_text(summary))
            _pause()
            continue
        if choice in {"2", "pieces"}:
            payload = list_pieces_fn(base_path)
            _print_block("Piezas", render_pieces(payload))
            _pause()
            continue
        if choice in {"3", "connectors"}:
            payload = list_connectors_fn(base_path)
            _print_block("Conectores", render_connectors(payload))
            _pause()
            continue
        if choice in {"4", "matrix"}:
            payload = matrix_fn(base_path)
            _print_block("Matriz", render_matrix(payload))
            _pause()
            continue
        if choice in {"5", "validate"}:
            ok, payload = validate_fn(base_path)
            _print_block("Validacion", __import__("json").dumps(payload, indent=2, ensure_ascii=False))
            print(f"\nResultado: {'OK' if ok else 'FAIL'}")
            _pause()
            continue
        if choice in {"6", "export"}:
            default_name = f"node-control-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            output = _prompt_text("Ruta de exportacion", default_name)
            target = export_fn(base_path, output)
            print(f"Exportado en: {target}")
            _pause()
            continue
        if choice in {"7", "connect"}:
            install = _select_installation(summary)
            if install is None:
                _pause()
                continue
            piece = _select_piece(summary)
            if piece is None:
                _pause()
                continue
            mode_idx = _prompt_choice(
                "Modo",
                ["connected", "shadow", "locked", "read-only", "writable overlay"],
                0,
            )
            if mode_idx < 0:
                _pause()
                continue
            mode = ["connected", "shadow", "locked", "readonly", "overlay"][mode_idx]
            payload = connect_fn(base_path, install["installation_id"], piece["piece_id"], mode)
            _print_block("Conexion", __import__("json").dumps(payload, indent=2, ensure_ascii=False))
            _pause()
            continue
        if choice in {"8", "disconnect"}:
            install = _select_installation(summary)
            if install is None:
                _pause()
                continue
            piece = _select_piece(summary)
            if piece is None:
                _pause()
                continue
            payload = disconnect_fn(base_path, install["installation_id"], piece["piece_id"])
            _print_block("Desconexion", __import__("json").dumps(payload, indent=2, ensure_ascii=False))
            _pause()
            continue
        if choice in {"9", "set-mode"}:
            install = _select_installation(summary)
            if install is None:
                _pause()
                continue
            piece = _select_piece(summary)
            if piece is None:
                _pause()
                continue
            mode_idx = _prompt_choice(
                "Nuevo modo",
                ["connected", "shadow", "locked", "read-only", "writable overlay"],
                0,
            )
            if mode_idx < 0:
                _pause()
                continue
            mode = ["connected", "shadow", "locked", "readonly", "overlay"][mode_idx]
            payload = set_mode_fn(base_path, install["installation_id"], piece["piece_id"], mode)
            _print_block("Cambio de modo", __import__("json").dumps(payload, indent=2, ensure_ascii=False))
            _pause()
            continue

        print("Opcion no valida.")
        _pause()
