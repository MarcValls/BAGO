"""Argparse + dispatch handlers for the `bago node` CLI.

This module owns the CLI surface (argument shape and command dispatch)
for :mod:`bago_core.node_control`. The runtime logic lives in
:mod:`bago_core.node_control` (facade) and its dispatch siblings
(:mod:`bago_core.node_control_translator`, etc.).

R8 says dispatch must not contain business logic, but the CLI plumbing
(parsers, command-to-function mapping, print vs JSON) is allowed here.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from bago_core import node_control as _nc

BAGO_ROOT = _nc.BAGO_ROOT

def build_parser() -> argparse.ArgumentParser:
    """Build the full argparse tree for `bago node`."""
    parser = argparse.ArgumentParser(description="BAGO Node Control")
    parser.add_argument("--base-path", default=str(BAGO_ROOT), help="Base path del runtime")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Muestra el registry, policy y evidence state").add_argument(
        "--json", action="store_true", help=argparse.SUPPRESS
    )
    sub.add_parser("validate", help="Valida el registry/policy/compatibility/evidence").add_argument(
        "--json", action="store_true", help=argparse.SUPPRESS
    )

    pieces_p = sub.add_parser("pieces", help="Lista piezas del PieceStore")
    pieces_p.add_argument("--type", default="")
    pieces_p.add_argument("--scope", default="")
    pieces_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    connectors_p = sub.add_parser("connectors", help="Lista conectores del registry")
    connectors_p.add_argument("--installation", default="")
    connectors_p.add_argument("--piece", default="")
    connectors_p.add_argument("--mode", default="")
    connectors_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    matrix_p = sub.add_parser("matrix", help="Muestra la matriz Installation x Piece")
    matrix_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    evidence_p = sub.add_parser("evidence", help="Muestra el tail real del evidence ledger")
    evidence_p.add_argument("--limit", type=int, default=25)
    evidence_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    preview_p = sub.add_parser("preview", help="Previsualiza una mutacion sin aplicarla")
    preview_p.add_argument("--installation", required=True)
    preview_p.add_argument("--piece", required=True)
    preview_p.add_argument("--mode", required=True, choices=list(_nc.CLI_MODES.keys()))
    preview_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    connect_p = sub.add_parser("connect", help="Conecta una installation con una piece")
    connect_p.add_argument("--installation", required=True)
    connect_p.add_argument("--piece", required=True)
    connect_p.add_argument("--mode", default="connected", choices=list(_nc.CLI_MODES.keys()))
    connect_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    disconnect_p = sub.add_parser("disconnect", help="Desconecta una installation de una piece")
    disconnect_p.add_argument("--installation", required=True)
    disconnect_p.add_argument("--piece", required=True)
    disconnect_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    setmode_p = sub.add_parser("set-mode", help="Cambia el modo de un connector")
    setmode_p.add_argument("--installation", required=True)
    setmode_p.add_argument("--piece", required=True)
    setmode_p.add_argument("--mode", required=True, choices=list(_nc.CLI_MODES.keys()))
    setmode_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    export_p = sub.add_parser("export", help="Exporta el estado a un bundle JSON")
    export_p.add_argument("--output", default="")

    sub.add_parser("tui", aliases=("terminal",), help="Interfaz de terminal del gestor de instalaciones")

    # Translator subcommand group (FASE 12). The argparse shape lives here
    # (this is node_control.py's own local CLI), but the runtime dispatch is
    # factored into :mod:`bago_core.node_control_translator` to respect the
    # rule: facade -> renders / dispatches / delegates, never contains logic.
    from bago_core.parsers_sections import add_translator_parser
    add_translator_parser(sub)
    return parser

def _write(payload: str | bytes) -> None:
    if isinstance(payload, bytes):
        sys.stdout.buffer.write(payload)
    else:
        sys.stdout.write(payload)

def _emit_json(payload: Any, *, compact: bool) -> None:
    _write(json.dumps(payload, indent=None if compact else 2, ensure_ascii=False))

def _emit_human(text: str) -> None:
    _write(text if text.endswith("\n") else text + "\n")

def _run_status(args: argparse.Namespace) -> int:
    payload = _nc.status(args.base_path)
    json_flag = args.json or getattr(args, "json", False)
    _emit_json(payload, compact=json_flag)
    return 0

def _run_validate(args: argparse.Namespace) -> int:
    ok, payload = _nc.validate(args.base_path)
    json_flag = getattr(args, "json", False)
    if json_flag:
        _emit_json(payload, compact=True)
    else:
        lines = []
        for c in payload.get("checks", []):
            mark = "OK" if c.get("ok") else "FAIL"
            lines.append(f"[{mark}] {c['name']} -- {c['detail']}")
        _emit_human("\n".join(lines))
    return 0 if ok else 1

def _run_pieces(args: argparse.Namespace) -> int:
    payload = _nc.list_pieces(args.base_path, getattr(args, "type", ""), getattr(args, "scope", ""))
    if getattr(args, "json", False):
        _emit_json(payload, compact=True)
    else:
        _emit_human(_nc._render_pieces_mod(payload))
    return 0

def _run_connectors(args: argparse.Namespace) -> int:
    payload = _nc.list_connectors(
        args.base_path,
        getattr(args, "installation", ""),
        getattr(args, "piece", ""),
        getattr(args, "mode", ""),
    )
    if getattr(args, "json", False):
        _emit_json(payload, compact=True)
    else:
        _emit_human(_nc._render_connectors_mod(payload))
    return 0

def _run_matrix(args: argparse.Namespace) -> int:
    payload = _nc.matrix(args.base_path)
    if getattr(args, "json", False):
        _emit_json(payload, compact=True)
    else:
        _emit_human(_nc._render_matrix_mod(payload))
    return 0

def _run_evidence(args: argparse.Namespace) -> int:
    payload = _nc.evidence_tail(args.base_path, getattr(args, "limit", 25))
    _emit_json(payload, compact=bool(getattr(args, "json", False)))
    return 0

def _run_preview(args: argparse.Namespace) -> int:
    payload = _nc.preview_mutation(
        args.base_path,
        args.installation,
        args.piece,
        args.mode,
    )
    _emit_json(payload, compact=bool(getattr(args, "json", False)))
    return 0

def _run_connect(args: argparse.Namespace) -> int:
    payload = _nc.connect(args.base_path, args.installation, args.piece, args.mode)
    _emit_json(payload, compact=bool(getattr(args, "json", False)))
    return 0

def _run_disconnect(args: argparse.Namespace) -> int:
    payload = _nc.disconnect(args.base_path, args.installation, args.piece)
    _emit_json(payload, compact=bool(getattr(args, "json", False)))
    return 0

def _run_set_mode(args: argparse.Namespace) -> int:
    payload = _nc.set_mode(args.base_path, args.installation, args.piece, args.mode)
    _emit_json(payload, compact=bool(getattr(args, "json", False)))
    return 0

def _run_export(args: argparse.Namespace) -> int:
    target = _nc.export_bundle(args.base_path, args.output or None)
    _emit_human(str(target))
    return 0

def _run_tui(args: argparse.Namespace) -> int:
    return _nc._interactive_tui_mod(
        args.base_path,
        {
            "status": _nc.status,
            "list_pieces": _nc.list_pieces,
            "list_connectors": _nc.list_connectors,
            "matrix": _nc.matrix,
            "validate": _nc.validate,
            "export_bundle": _nc.export_bundle,
            "connect": _nc.connect,
            "disconnect": _nc.disconnect,
            "set_mode": _nc.set_mode,
        },
    )

def _run_translator(args: argparse.Namespace) -> int:
    from bago_core.node_control_translator import run_translator
    return run_translator(args)

# Command router: command name -> handler.
HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "status": _run_status,
    "validate": _run_validate,
    "pieces": _run_pieces,
    "connectors": _run_connectors,
    "matrix": _run_matrix,
    "evidence": _run_evidence,
    "preview": _run_preview,
    "connect": _run_connect,
    "disconnect": _run_disconnect,
    "set-mode": _run_set_mode,
    "export": _run_export,
    "tui": _run_tui,
    "terminal": _run_tui,
    "translator": _run_translator,
}

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "status"
    handler = HANDLERS.get(command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)

if __name__ == "__main__":
    raise SystemExit(main())
