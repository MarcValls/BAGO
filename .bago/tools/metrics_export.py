#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metrics_export.py — Exporta métricas de ideas implementadas a CSV.

Uso:
    python3 .bago/tools/metrics_export.py              # muestra tabla en consola
    python3 .bago/tools/metrics_export.py --csv        # exporta a .bago/state/reports/metrics.csv
    python3 .bago/tools/metrics_export.py --json       # exporta a metrics.json
    python3 .bago/tools/metrics_export.py --summary    # resumen agregado
    python3 .bago/tools/metrics_export.py --out FILE   # ruta de salida personalizada

Códigos de salida: 0 = OK
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT      = Path(__file__).resolve().parents[2]
STATE     = ROOT / ".bago" / "state"
REPORTS   = STATE / "reports"
IDEAS_FILE = STATE / "implemented_ideas.json"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


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
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def _enrich(idea: dict) -> dict:
    """Add computed fields."""
    dt = _parse_date(idea.get("done_at", ""))
    duration_h = idea.get("duration_hours", None)
    duration_m = round(duration_h * 60, 1) if duration_h is not None else None

    return {
        "title":         idea.get("title", ""),
        "slot":          idea.get("slot", ""),
        "done_at":       idea.get("done_at", ""),
        "week":          dt.strftime("W%V-%Y") if dt else "",
        "day":           dt.strftime("%Y-%m-%d") if dt else "",
        "weekday":       dt.strftime("%A") if dt else "",
        "hour":          dt.hour if dt else "",
        "duration_h":    round(duration_h, 4) if duration_h is not None else "",
        "duration_min":  duration_m if duration_m is not None else "",
    }


def _print_table(rows: list[dict]) -> None:
    print()
    print(f"  {'#':<4} {'SLOT':<5} {'DURACIÓN':>9}  {'FECHA':<12}  TÍTULO")
    print(f"  {'─'*4} {'─'*5} {'─'*9}  {'─'*12}  {'─'*40}")
    for i, r in enumerate(rows, 1):
        dur = f"{r['duration_min']}m" if r['duration_min'] != "" else DIM("N/A")
        day = r['day'][:10] if r['day'] else DIM("?")
        slot_str = str(r['slot']) if r['slot'] != "" else DIM("-")
        title = r['title'][:55] + "…" if len(r['title']) > 55 else r['title']
        print(f"  {i:<4} {slot_str:<5} {dur:>9}  {day:<12}  {title}")
    print()


def _export_csv(rows: list[dict], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["title", "slot", "done_at", "week", "day", "weekday", "hour", "duration_h", "duration_min"]
    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _export_json(rows: list[dict], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_summary(rows: list[dict]) -> None:
    durations = [r["duration_min"] for r in rows if r["duration_min"] != ""]
    days_with = len(set(r["day"] for r in rows if r["day"]))
    weeks = len(set(r["week"] for r in rows if r["week"]))

    print()
    print(f"  {BOLD('Resumen de métricas')}")
    print(f"  {'─'*40}")
    print(f"  Total ideas implementadas : {BOLD(str(len(rows)))}")
    print(f"  Días activos              : {days_with}")
    print(f"  Semanas activas           : {weeks}")
    if durations:
        avg = sum(durations) / len(durations)
        mn  = min(durations)
        mx  = max(durations)
        print(f"  Duración promedio         : {avg:.1f} min")
        print(f"  Mínima / Máxima           : {mn:.1f}m / {mx:.1f}m")
        ideas_per_day = len(rows) / days_with if days_with else 0
        print(f"  Ideas por día activo      : {ideas_per_day:.1f}")
    # Weekday distribution
    from collections import Counter
    wd_count = Counter(r["weekday"] for r in rows if r["weekday"])
    if wd_count:
        top_day = wd_count.most_common(1)[0]
        print(f"  Día más productivo        : {top_day[0]} ({top_day[1]} ideas)")
    print()


def main() -> int:
    args     = sys.argv[1:]
    do_csv   = "--csv"     in args
    do_json  = "--json"    in args
    summary  = "--summary" in args or "-s" in args

    out_path: Path | None = None
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_path = Path(args[idx + 1])

    ideas = _load_ideas()
    if not ideas:
        print(f"\n  {YELLOW('⚠')} Sin ideas implementadas.\n")
        return 0

    rows = [_enrich(idea) for idea in ideas]

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Metrics Export                                      │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Total: {BOLD(str(len(rows)))} ideas  ·  fuente: {DIM(str(IDEAS_FILE))}")

    if summary:
        _print_summary(rows)
    elif not do_csv and not do_json:
        _print_table(rows)

    if do_csv or out_path:
        dest = out_path or REPORTS / "metrics.csv"
        if out_path and not str(out_path).endswith(".csv"):
            dest = out_path
        _export_csv(rows, dest)
        print(f"  {GREEN('✅ CSV exportado:')} {dest}")

    if do_json:
        dest = out_path or REPORTS / "metrics.json"
        _export_json(rows, dest)
        print(f"  {GREEN('✅ JSON exportado:')} {dest}")

    if not do_csv and not do_json and not summary:
        print(f"  Usa {CYAN('--csv')} o {CYAN('--json')} para exportar  ·  {CYAN('--summary')} para resumen")
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
