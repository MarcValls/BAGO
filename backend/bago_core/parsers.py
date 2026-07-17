#!/usr/bin/env python3
"""parsers.py -- BAGO CLI surface.

FASE 6.1 facade: este modulo es una **fachada fina** que delega toda la
construccion de subparsers a :mod:`bago_core.parsers_sections`. La forma
del parser (argparse) sigue siendo unica -- vive en `parsers_sections.py`
seccion por seccion -- pero `build_parser()` la compone en un solo
ArgumentParser para que `bago_core.launcher` solo tenga que importarlo.

Reglas de modulizacion (R0-R10):
- R0: este modulo < 200 lineas. Solo delega, no contiene logica.
- R1: cada seccion de parser vive en `parsers_sections.py`.
- R8: cero I/O directo, cero `print()` -- solo argparse.

Uso:
    from bago_core.parsers import build_parser
    parser = build_parser(version, base, default_provider, default_model)
    args = parser.parse_args(argv)
"""
from __future__ import annotations

import argparse

from bago_core.parsers_sections import (
    add_session_parsers,
    add_ops_parsers,
    add_node_parsers,
)


def build_parser(
    version: str,
    base: str,
    default_provider: str,
    default_model: str,
) -> argparse.ArgumentParser:
    """Compose the BAGO ArgumentParser from the parsers_sections sections.

    Layout:
      1. top-level + global flags (provider, model, base-path)
      2. session parsers (chat/launch/start/validate, install/uninstall,
         claim, config, llm, engine, appdata, cmd-rl, rl, serve, evidence,
         monitor) -- `add_session_parsers`
      3. ops parsers (orchestrate, issues, scan, canary, backup, project,
         preflight, toolsmith, issues-gh, agent, guard, route, inventory,
         list-installs) -- `add_ops_parsers`
      4. node parsers (status, validate, pieces, connectors, matrix,
         connect, disconnect, set-mode, export, tui, translator) --
         `add_node_parsers`
    """
    parser = argparse.ArgumentParser(
        prog="bago",
        description=f"BAGO {version} -- Session-First AI Chat",
    )
    parser.add_argument("--version", action="version", version=f"bago {version}")
    parser.add_argument("--provider",  default=default_provider, help="Provider por defecto")
    parser.add_argument("--model",     default=default_model,    help="Modelo por defecto")
    parser.add_argument("--base-path", default=base,             help="Directorio base del proyecto")
    sub = parser.add_subparsers(dest="command", help="Comandos disponibles")

    add_session_parsers(sub)
    add_ops_parsers(sub)
    add_node_parsers(sub)
    return parser
