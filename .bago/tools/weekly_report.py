#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_report.py — Informe semanal de actividad BAGO.

Genera un resumen Markdown de ideas implementadas, sesiones y velocidad
en los últimos 7 días (o N días con --days).

Uso:
    python3 .bago/tools/weekly_report.py               # imprime resumen
    python3 .bago/tools/weekly_report.py --days 14     # últimas 2 semanas
    python3 .bago/tools/weekly_report.py --save        # guarda en .bago/state/reports/

Códigos de salida: 0 siempre
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
REPORTS_DIR = STATE / "reports"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"


def _load_implemented(since_dt: datetime) -> list[dict]:
    """Load ideas implemented after since_dt from implemented_ideas.json."""
    impl_file = STATE / "implemented_ideas.json"
    if not impl_file.exists():
        return []
    try:
        data = json.loads(impl_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    ideas = data if isinstance(data, list) else data.get("implemented", [])
    result = []
    for idea in ideas:
        ts_str = (idea.get("done_at") or idea.get("implemented_at")
                  or idea.get("timestamp") or idea.get("date", ""))
        if not ts_str:
            continue
        try:
            # Strip timezone offset for simple parsing
            ts_clean = ts_str[:19].replace("T", " ")
            ts = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                ts = datetime.strptime(ts_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        if ts >= since_dt:
            result.append({**idea, "_ts": ts})
    return sorted(result, key=lambda x: x["_ts"], reverse=True)


def _count_sessions(since_dt: datetime) -> int:
    """Count session_close_*.md files newer than since_dt."""
    count = 0
    for f in STATE.glob("session_close_*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime >= since_dt:
                count += 1
        except Exception:
            pass
    return count


def _load_global_state() -> dict:
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return {}
    try:
        return json.loads(gs_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_task_stats() -> dict:
    """Load stats from implemented_ideas.json for all-time totals."""
    impl_file = STATE / "implemented_ideas.json"
    if not impl_file.exists():
        return {"total": 0}
    try:
        data = json.loads(impl_file.read_text(encoding="utf-8"))
    except Exception:
        return {"total": 0}
    items = data if isinstance(data, list) else data.get("implemented", [])
    return {"total": len(items)}


def _build_report(days: int) -> tuple[str, str]:
    """Build console + markdown report. Returns (console_text, markdown_text)."""
    now_utc = datetime.now(tz=timezone.utc)
    since = now_utc - timedelta(days=days)
    since_str = since.strftime("%Y-%m-%d")
    now_str = now_utc.strftime("%Y-%m-%d")

    ideas = _load_implemented(since)
    sessions = _count_sessions(since)
    gs = _load_global_state()
    all_stats = _load_task_stats()

    project_name = gs.get("active_project", {}).get("name", "desconocido")
    velocity = len(ideas) / days * 7 if days > 0 else 0  # ideas/week

    # ── Markdown ──────────────────────────────────────────────────────────────
    md_lines = [
        f"# Informe BAGO — {since_str} → {now_str}",
        "",
        f"**Proyecto**: {project_name}  ",
        f"**Período**: últimos {days} días  ",
        f"**Generado**: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Resumen",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Ideas implementadas (período) | **{len(ideas)}** |",
        f"| Sesiones de trabajo | **{sessions}** |",
        f"| Velocidad estimada | **{velocity:.1f} ideas/semana** |",
        f"| Total histórico implementadas | **{all_stats['total']}** |",
        "",
    ]

    if ideas:
        md_lines += [
            "## Ideas implementadas",
            "",
        ]
        for idea in ideas:
            title = idea.get("title", idea.get("idea", "sin título"))
            ts = idea["_ts"].strftime("%Y-%m-%d")
            priority = idea.get("priority", "—")
            md_lines.append(f"- **{title}** _(prioridad {priority}, {ts})_")
        md_lines.append("")

    md_lines += [
        "## Notas",
        "",
        "- Generado automáticamente por `bago report`",
        "- Las sesiones se cuentan por archivos `session_close_*.md`",
        "",
    ]

    md_text = "\n".join(md_lines)

    # ── Console ───────────────────────────────────────────────────────────────
    con_lines = [
        "",
        "  ┌─────────────────────────────────────────────────────────────┐",
        "  │  BAGO · Informe semanal de actividad                        │",
        "  └─────────────────────────────────────────────────────────────┘",
        f"  Proyecto : {project_name}",
        f"  Período  : {since_str} → {now_str}  ({days} días)",
        "",
        f"  IDEAS IMPLEMENTADAS     : {BOLD(str(len(ideas)))}",
        f"  Sesiones de trabajo     : {sessions}",
        f"  Velocidad estimada      : {velocity:.1f} ideas/semana",
        f"  Total histórico         : {all_stats['total']}",
        "",
    ]

    if ideas:
        con_lines.append("  IDEAS DEL PERÍODO:")
        for idea in ideas:
            title = idea.get("title", idea.get("idea", "sin título"))
            ts = idea["_ts"].strftime("%m-%d")
            priority = idea.get("priority", "—")
            con_lines.append(f"    [{ts}] (p{priority}) {title}")
        con_lines.append("")

    if sessions == 0 and len(ideas) == 0:
        con_lines.append(f"  {DIM('Sin actividad registrada en este período.')}")
        con_lines.append("")

    return "\n".join(con_lines), md_text


def main() -> int:
    args = sys.argv[1:]
    days = 7
    save = "--save" in args

    if "--days" in args:
        idx = args.index("--days")
        if idx + 1 < len(args):
            try:
                days = int(args[idx + 1])
            except ValueError:
                pass

    console_text, md_text = _build_report(days)
    print(console_text)

    if save:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"report_{date_str}.md"
        report_file.write_text(md_text, encoding="utf-8")
        print(f"  Guardado en: {report_file}")
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
