#!/usr/bin/env python3
"""recientes_cli.py — UX layer para `bago recientes`.

Lee eventos vía recientes_aggregator.aggregate() y los pagina
interactivamente sobre el TTY:
    [Enter]  → siguiente página
    [q] / Ctrl-D → salir

Sin TTY (output redirigido o --no-pager): vuelca todo de golpe.

Imported by: bago.cli (`bago recientes`).
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import os
import sys
from pathlib import Path

# permite ejecución directa: añade .bago/tools al path
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from recientes_aggregator import (  # noqa: E402
    VALID_TYPES,
    _parse_since,
    aggregate,
    fmt_event,
)

DEFAULT_PAGE = 10


def _is_tty() -> bool:
    return sys.stdout.isatty() and sys.stdin.isatty()


def _paginate(events: list[dict], page_size: int) -> int:
    if not events:
        print("(sin eventos)")
        return 0
    total = len(events)
    i = 0
    while i < total:
        chunk = events[i : i + page_size]
        for ev in chunk:
            print(fmt_event(ev))
        i += page_size
        if i >= total:
            print(f"\n(fin · {total} eventos)")
            break
        # prompt
        try:
            sys.stdout.write(
                f"\n— [{i}/{total}]  Enter=siguiente · q=salir — "
            )
            sys.stdout.flush()
            line = sys.stdin.readline()
        except (KeyboardInterrupt, EOFError):
            print()
            return 0
        if line == "":  # EOF
            print()
            return 0
        cmd = line.strip().lower()
        if cmd in {"q", "quit", "exit"}:
            print(f"(salida · mostrados {i}/{total})")
            return 0
        # cualquier otra cosa = continuar
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bago recientes",
        description="Bitácora paginada de últimos trabajos (sesiones, sprints, ideas, cierres, commits).",
    )
    p.add_argument("--type", default="all",
                   help="comma-list: session,sprint,idea,close,commit,all (def all)")
    p.add_argument("--since", default="", help="duración: 2w/3d/6h/90m")
    p.add_argument("--no-git", action="store_true", help="omitir git log")
    p.add_argument("--git-limit", type=int, default=50)
    p.add_argument("--limit", type=int, default=200, help="máximo total de eventos")
    p.add_argument("--page", type=int, default=DEFAULT_PAGE,
                   help=f"eventos por página (def {DEFAULT_PAGE})")
    p.add_argument("--no-pager", action="store_true",
                   help="volcar todo sin paginar (también auto-on cuando no hay TTY)")
    p.add_argument("--json", action="store_true", help="salida JSON")
    p.add_argument("--test", action="store_true", help="self-test mínimo")
    return p


def _self_test() -> int:
    """Tests del layer CLI (no del aggregator)."""
    fails: list[str] = []
    # paginate vacío
    if _paginate([], 5) != 0:
        fails.append("paginate empty")
    # paginate con datos en no-tty: ya iremos por --no-pager
    if fails:
        for f in fails:
            print("  FAIL:", f)
        return 1
    print("OK: cli self-test")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test:
        return _self_test()
    types = [t.strip() for t in args.type.split(",") if t.strip()]
    bad = [t for t in types if t not in VALID_TYPES]
    if bad:
        sys.exit(f"recientes: tipos inválidos: {bad}. Acepta: {sorted(VALID_TYPES)}")
    since = _parse_since(args.since) if args.since else None
    if args.since and since is None:
        sys.exit(f"recientes: --since '{args.since}' inválido (usa 2w/3d/6h/90m)")
    events = aggregate(
        types=types,
        since=since,
        use_git=not args.no_git,
        git_limit=args.git_limit,
    )
    events = events[: args.limit]
    if args.json:
        import json as _json
        _json.dump(events, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if args.no_pager or not _is_tty():
        if not events:
            print("(sin eventos)")
            return 0
        for ev in events:
            print(fmt_event(ev))
        return 0
    return _paginate(events, page_size=args.page)


if __name__ == "__main__":
    sys.exit(main())
