#!/usr/bin/env python3
"""FASE 6.4: argparse + main for the install scanner CLI.

A thin facade: parse args, call :mod:`bago_core.cli_installs_discovery`,
call :mod:`bago_core.cli_installs_summary`, dump JSON. No business logic
or filesystem work happens here.

R0-R10:
- R0: <60 lines
- R1: facade only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bago_core.install_roles import load_selection, role_paths
from bago_core.cli_installs_discovery import _scan
from bago_core.cli_installs_summary import summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Scan BAGO installations on this machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--plain", action="store_true",
                   help="JSON compacto en una sola linea (facil de copiar a la web)")
    p.add_argument("--active-only", action="store_true",
                   help="Solo listar instalaciones que existen (descarta las que faltan)")
    args = p.parse_args(argv)
    items = _scan()
    if args.active_only:
        items = [i for i in items if i["exists"]]
    payload = {
        "summary": summary(items),
        "selection": {
            "file": str(Path.home() / ".bago" / "install_selection.json"),
            "roles": role_paths(load_selection()),
        },
        "installations": items,
    }
    indent = None if args.plain else 2
    print(json.dumps(payload, indent=indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
