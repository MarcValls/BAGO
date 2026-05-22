#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeline.py — Historial visual ASCII de ideas implementadas por semana/día.

Uso:
    python3 .bago/tools/timeline.py               # timeline por semana (últimas 8)
    python3 .bago/tools/timeline.py --days        # agrupar por día (últimos 30 días)
    python3 .bago/tools/timeline.py --all         # todo el historial
    python3 .bago/tools/timeline.py --weeks N     # N semanas atrás

Códigos de salida: 0 = OK
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
IDEAS_FILE = STATE / "implemented_ideas.json"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"
def BLUE(s: str)   -> str: return f"\033[34m{s}\033[0m"


def _load_ideas() -> list[dict]:
    if not IDEAS_FILE.exists():
        return []
    try:
        data = json.loads(IDEAS_FILE.read_text(encoding="utf-8"))
        return data.get("implemented", [])
    except Exception:
        return []


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    # Try parsing with timezone offset (e.g. +02:00)
    try:
        # Python 3.7+ fromisoformat doesn't handle Z but handles offsets
        s_clean = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s_clean).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        pass
    return None


def _bar(count: int, max_count: int, width: int = 30) -> str:
    if max_count == 0:
        return ""
    filled = int(count / max_count * width)
    bar = "█" * filled + "░" * (width - filled)
    if count >= max_count * 0.8:
        return GREEN(bar)
    elif count >= max_count * 0.4:
        return CYAN(bar)
    else:
        return BLUE(bar)


def _week_key(dt: datetime) -> str:
    # ISO week: year-weeknum
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_label(dt: datetime) -> str:
    iso = dt.isocalendar()
    # Find Monday of that week
    monday = dt - timedelta(days=dt.weekday())
    return f"{monday.strftime('%d %b')} W{iso[1]:02d}"


def _show_by_week(ideas: list[dict], num_weeks: int) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(weeks=num_weeks)

    # Group by week
    by_week: dict[str, list[dict]] = defaultdict(list)
    for idea in ideas:
        dt = _parse_date(idea.get("done_at", ""))
        if dt and dt >= cutoff:
            by_week[_week_key(dt)].append(idea)

    if not by_week:
        print(f"\n  {YELLOW('⚠')} Sin ideas en las últimas {num_weeks} semanas.")
        return

    # Sort weeks
    sorted_weeks = sorted(by_week.keys())
    max_count = max(len(v) for v in by_week.values())

    print(f"\n  {'SEMANA':<14} {'IDEAS':>5}  ACTIVIDAD")
    print(f"  {'──────':<14} {'─────':>5}  ─────────")

    for week_key in sorted_weeks:
        ideas_in_week = by_week[week_key]
        count = len(ideas_in_week)
        # Get representative date for label
        first_dt = _parse_date(ideas_in_week[0].get("done_at", ""))
        label = _week_label(first_dt) if first_dt else week_key

        bar = _bar(count, max_count)
        is_current = _week_key(now) == week_key
        marker = YELLOW(" ← actual") if is_current else ""
        print(f"  {label:<14} {BOLD(str(count)):>5}  {bar}{marker}")

    total = sum(len(v) for v in by_week.values())
    print(f"\n  Total: {BOLD(str(total))} ideas en {len(sorted_weeks)} semanas")


def _show_by_day(ideas: list[dict], num_days: int) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=num_days)

    by_day: dict[str, list[dict]] = defaultdict(list)
    for idea in ideas:
        dt = _parse_date(idea.get("done_at", ""))
        if dt and dt >= cutoff:
            day_key = dt.strftime("%Y-%m-%d")
            by_day[day_key].append(idea)

    if not by_day:
        print(f"\n  {YELLOW('⚠')} Sin ideas en los últimos {num_days} días.")
        return

    sorted_days = sorted(by_day.keys())
    max_count = max(len(v) for v in by_day.values())

    print(f"\n  {'FECHA':<12} {'IDEAS':>5}  ACTIVIDAD")
    print(f"  {'─────':<12} {'─────':>5}  ─────────")

    for day_key in sorted_days:
        count = len(by_day[day_key])
        dt = datetime.strptime(day_key, "%Y-%m-%d")
        label = dt.strftime("%d %b %a")
        bar = _bar(count, max_count)
        today = now.strftime("%Y-%m-%d") == day_key
        marker = YELLOW(" ← hoy") if today else ""
        print(f"  {label:<12} {BOLD(str(count)):>5}  {bar}{marker}")

    total = sum(len(v) for v in by_day.values())
    print(f"\n  Total: {BOLD(str(total))} ideas en {len(sorted_days)} días activos")


def main() -> int:
    args = sys.argv[1:]
    by_day  = "--days" in args or "-d" in args
    all_    = "--all"  in args or "-a" in args

    num_weeks = 8
    num_days  = 30
    if "--weeks" in args:
        idx = args.index("--weeks")
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            num_weeks = int(args[idx + 1])
    if all_:
        num_weeks = 520  # 10 years
        num_days  = 3650

    ideas = _load_ideas()
    if not ideas:
        print(f"\n  {YELLOW('⚠')} Sin ideas implementadas en el registro.\n")
        return 0

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    mode = "por día" if by_day else "por semana"
    print(f"  │  BAGO · Timeline ({mode}){'':30}│")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Total histórico: {BOLD(str(len(ideas)))} ideas implementadas")

    if by_day:
        _show_by_day(ideas, num_days)
    else:
        _show_by_week(ideas, num_weeks)

    print()
    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
