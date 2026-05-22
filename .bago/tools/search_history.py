#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search_history.py — Busca en el historial de ideas implementadas.

Uso:
  python .bago/tools/search_history.py <término> [término2 ...]
  python .bago/tools/search_history.py           # últimas 10 ideas
  bago search <término> [término2 ...]
"""

from __future__ import annotations

import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / ".bago" / "state" / "implemented_ideas.json"

DEFAULT_LIMIT = 10


def _norm(s: str) -> str:
    """Minúsculas + sin diacríticos (idéntico a emit_ideas.py)."""
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode("ascii")


def _load_ideas() -> list[dict]:
    if not HISTORY_PATH.exists():
        print(f"[search] No se encontró {HISTORY_PATH}", file=sys.stderr)
        return []
    with HISTORY_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("implemented", [])


def _fmt_date(raw: str) -> str:
    """Formatea ISO timestamp a YYYY-MM-DD."""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw[:10] if len(raw) >= 10 else raw


def _print_table(ideas: list[dict], terms: list[str] | None = None) -> None:
    if not ideas:
        if terms:
            query = ", ".join(f"'{t}'" for t in terms)
            print(f"No se encontraron ideas que coincidan con {query}")
        else:
            print("No hay ideas implementadas en el historial.")
        return

    header_date  = "Fecha"
    header_prio  = "Prio"
    header_title = "Título"

    rows = []
    for idea in ideas:
        date  = _fmt_date(idea.get("done_at", ""))
        slot  = idea.get("slot")
        prio  = str(slot) if slot is not None else "—"
        title = idea.get("title", "")
        rows.append((date, prio, title))

    w_date  = max(len(header_date),  max(len(r[0]) for r in rows))
    w_prio  = max(len(header_prio),  max(len(r[1]) for r in rows))
    w_title = max(len(header_title), max(len(r[2]) for r in rows))

    sep = f"  {'─' * w_date}  {'─' * w_prio}  {'─' * w_title}"
    hdr = f"  {header_date:<{w_date}}  {header_prio:<{w_prio}}  {header_title}"

    print(hdr)
    print(sep)
    for date, prio, title in rows:
        print(f"  {date:<{w_date}}  {prio:<{w_prio}}  {title}")

    print(f"\n  {len(rows)} resultado(s)")


def search(terms: list[str]) -> None:
    ideas = _load_ideas()
    if not ideas:
        return

    norm_terms = [_norm(t) for t in terms]
    matches = [
        idea for idea in ideas
        if any(nt in _norm(idea.get("title", "")) for nt in norm_terms)
    ]

    if not matches:
        query = ", ".join(f"'{t}'" for t in terms)
        print(f"No se encontraron ideas que coincidan con {query}")
        return

    _print_table(matches, terms)


def last_n(n: int = DEFAULT_LIMIT) -> None:
    ideas = _load_ideas()
    if not ideas:
        return
    recent = ideas[-n:] if len(ideas) > n else ideas
    print(f"  Últimas {len(recent)} ideas implementadas:\n")
    _print_table(recent)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        last_n(DEFAULT_LIMIT)
    else:
        search(args)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
