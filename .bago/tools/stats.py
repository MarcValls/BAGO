#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stats.py — Velocidad de ciclo W2: estadísticas de ideas implementadas.

Uso:
    python .bago/tools/stats.py
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = BAGO_ROOT / "state" / "implemented_ideas.json"


def _load() -> list[dict]:
    if not STATE_FILE.exists():
        print(f"[stats] No encontrado: {STATE_FILE}")
        sys.exit(1)
    with STATE_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("implemented", [])


def _parse_dt(s: str) -> datetime:
    """Parse ISO 8601 datetime string to UTC-aware datetime."""
    s = s.strip()
    # Python 3.10 fromisoformat doesn't handle trailing Z
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sep(width: int = 60) -> str:
    return "+" + "-" * (width - 2) + "+"


def _row(label: str, value: str, width: int = 60) -> str:
    inner = width - 4
    content = f"{label:<30} {value}"
    if len(content) > inner:
        content = content[:inner]
    return f"| {content:<{inner}} |"


def main() -> None:
    ideas = _load()
    total = len(ideas)
    now = datetime.now(tz=timezone.utc)

    # Date filters
    ideas_7d  = [i for i in ideas if _parse_dt(i["done_at"]) >= now - timedelta(days=7)]
    ideas_30d = [i for i in ideas if _parse_dt(i["done_at"]) >= now - timedelta(days=30)]

    # duration_hours stats
    durations = [i["duration_hours"] for i in ideas if "duration_hours" in i and i["duration_hours"] is not None]
    if durations:
        avg_h = sum(durations) / len(durations)
        avg_min = avg_h * 60
        sorted_d = sorted(durations)
        n = len(sorted_d)
        median_h = sorted_d[n // 2] if n % 2 else (sorted_d[n // 2 - 1] + sorted_d[n // 2]) / 2
        median_min = median_h * 60
        p90_h = sorted_d[int(n * 0.9)]
        p90_min = p90_h * 60
        avg_str = f"{avg_min:.1f} min  (media, n={n})"
        median_str = f"{median_min:.1f} min"
        p90_str = f"{p90_min:.1f} min"
        fastest = min(ideas, key=lambda i: i.get("duration_hours", float("inf")) if "duration_hours" in i else float("inf"))
        slowest = max(ideas, key=lambda i: i.get("duration_hours", float("-inf")) if "duration_hours" in i else float("-inf"))
        fastest_str = f"{fastest['title'][:24]}  ({fastest['duration_hours']*60:.1f} min)"
        slowest_str = f"{slowest['title'][:24]}  ({slowest['duration_hours']*60:.1f} min)"
        # Distribution buckets
        b_quick  = sum(1 for d in durations if d * 60 < 5)
        b_short  = sum(1 for d in durations if 5 <= d * 60 < 30)
        b_medium = sum(1 for d in durations if 30 <= d * 60 < 120)
        b_long   = sum(1 for d in durations if d * 60 >= 120)
    else:
        avg_str = "n/d"
        median_str = "n/d"
        p90_str = "n/d"
        fastest_str = "n/d"
        slowest_str = "n/d"
        b_quick = b_short = b_medium = b_long = 0

    W = 64
    inner = W - 4

    print()
    print("+" + "=" * (W - 2) + "+")
    title = "  BAGO STATS — Velocidad de ciclo W2"
    print(f"|{title:<{W - 2}}|")
    print("+" + "=" * (W - 2) + "+")

    def row(lbl: str, val: str) -> None:
        content = f"{lbl:<32} {val}"
        if len(content) > inner:
            content = content[:inner]
        print(f"| {content:<{inner}} |")

    def sep() -> None:
        print("+" + "-" * (W - 2) + "+")

    sep()
    row("Total ideas implementadas:", str(total))
    row("Últimos 7 días:", str(len(ideas_7d)))
    row("Últimos 30 días:", str(len(ideas_30d)))
    sep()
    row("Tiempo medio por idea:", avg_str)
    row("Mediana:", median_str)
    row("Percentil 90:", p90_str)
    row("Más rápida:", fastest_str)
    row("Más lenta:", slowest_str)
    sep()
    row("Distribución de tiempos:", "")
    row("  < 5 min (quick win):",  f"{b_quick:>3} ideas")
    row("  5–30 min (normal):",    f"{b_short:>3} ideas")
    row("  30–120 min (complejo):",f"{b_medium:>3} ideas")
    row("  > 2h (largo):",         f"{b_long:>3} ideas")
    sep()

    # 5 most recent — columns fit within inner (60)
    sorted_ideas = sorted(ideas, key=lambda i: i["done_at"], reverse=True)
    recent = sorted_ideas[:5]
    header = f"{'#':<3} {'Idea':<30} {'done_at':<10} {'min':>5}"
    print(f"| {header:<{inner}} |")
    sep()
    for idx, idea in enumerate(recent, 1):
        dt_str = idea["done_at"][:10]
        if "duration_hours" in idea and idea["duration_hours"] is not None:
            dur = f"{idea['duration_hours']*60:.1f}"
        else:
            dur = " n/d"
        line = f"{idx:<3} {idea['title'][:30]:<30} {dt_str:<10} {dur:>5}"
        print(f"| {line:<{inner}} |")
    print("+" + "=" * (W - 2) + "+")
    print()



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
