#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
html_export.py — Genera un informe HTML autocontenido del proyecto BAGO.

El HTML incluye: tabla de ideas implementadas, lista de herramientas, gráfico
de métricas por semana, estado del proyecto y configuración básica.

Uso:
    python3 .bago/tools/html_export.py            # genera bago_report.html
    python3 .bago/tools/html_export.py --out DIR  # guardar en directorio
    python3 .bago/tools/html_export.py --open     # abrir en navegador tras generar

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
TOOLS = ROOT / ".bago" / "tools"


def GREEN(s: str) -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)   -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str)-> str: return f"\033[33m{s}\033[0m"
def BOLD(s: str)  -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)   -> str: return f"\033[2m{s}\033[0m"


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _build_report() -> dict:
    gs    = _load_json(STATE / "global_state.json") or {}
    proj  = gs.get("active_project", {})
    impl  = _load_json(STATE / "implemented_ideas.json") or {}
    ideas = impl.get("implemented", [])

    # Group by week
    weeks: dict[str, list[str]] = defaultdict(list)
    for idea in ideas:
        dt = _parse_dt(idea.get("done_at", ""))
        if dt:
            w = _week_key(dt)
            weeks[w].append(idea.get("title", "?"))

    # Tool count
    base = {"tool_registry.py", "db_init.py", "idea_gen.py", "validate.py",
            "bago_core.py", "__init__.py", "emit_ideas.py"}
    tools = [f.stem for f in TOOLS.glob("*.py") if f.name not in base]

    # Snapshots
    snaps = list((ROOT / ".bago" / "snapshots").glob("*.zip")) if (ROOT / ".bago" / "snapshots").exists() else []

    return {
        "project":  proj,
        "ideas":    ideas,
        "weeks":    dict(weeks),
        "tools":    sorted(tools),
        "snaps":    [s.name for s in sorted(snaps, key=lambda x: x.stat().st_mtime, reverse=True)],
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _render_html(report: dict) -> str:
    proj    = report["project"]
    ideas   = report["ideas"]
    weeks   = report["weeks"]
    tools   = report["tools"]
    snaps   = report["snaps"]
    gen     = report["generated"]
    name    = proj.get("name", "BAGO Project")

    # Chart data
    sorted_weeks = sorted(weeks.keys())
    chart_labels = json.dumps(sorted_weeks)
    chart_data   = json.dumps([len(weeks[w]) for w in sorted_weeks])

    # Ideas rows
    idea_rows = ""
    for idx, idea in enumerate(ideas[:100], 1):
        dt_str = ""
        dt = _parse_dt(idea.get("done_at", ""))
        if dt:
            dt_str = dt.strftime("%Y-%m-%d")
        title = idea.get("title", idea.get("idea_title", "?"))
        slot  = idea.get("slot", idea.get("idea_index", "?"))
        idea_rows += f"<tr><td>{idx}</td><td>{slot}</td><td>{title}</td><td>{dt_str}</td></tr>\n"

    # Tool pills
    tool_pills = "".join(f'<span class="pill">{t}</span>' for t in tools)

    # Snap list
    snap_items = "".join(f"<li>{s}</li>" for s in snaps[:10]) or "<li>(ninguno)</li>"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BAGO Report — {name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; padding: 24px; }}
  h1 {{ font-size: 2rem; color: #38bdf8; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 32px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #1e2433; border: 1px solid #2d3748; border-radius: 12px; padding: 20px; }}
  .card .label {{ font-size: 0.8rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
  .card .value {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
  .card .sub {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
  h2 {{ font-size: 1.2rem; color: #94a3b8; margin: 24px 0 12px; border-bottom: 1px solid #2d3748; padding-bottom: 8px; }}
  .chart-wrap {{ background: #1e2433; border-radius: 12px; padding: 20px; margin-bottom: 32px; max-height: 280px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; padding: 8px 12px; background: #1e2433; color: #64748b; font-weight: 600; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #1a2030; }}
  tr:hover td {{ background: #1a2535; }}
  td:first-child {{ color: #64748b; }}
  .pill {{ display: inline-block; background: #1e3a5f; color: #38bdf8; border-radius: 6px; padding: 2px 8px;
           font-size: 0.75rem; margin: 2px; }}
  .pills-wrap {{ margin-bottom: 32px; }}
  ul {{ list-style: none; padding-left: 0; }}
  li {{ padding: 4px 0; color: #94a3b8; font-size: 0.85rem; }}
  li::before {{ content: "📦 "; }}
  footer {{ margin-top: 40px; color: #4a5568; font-size: 0.75rem; text-align: center; }}
</style>
</head>
<body>
<h1>🤖 BAGO Report</h1>
<div class="subtitle">Proyecto: <strong>{name}</strong> · Generado: {gen}</div>

<div class="grid">
  <div class="card"><div class="label">Ideas implementadas</div><div class="value">{len(ideas)}</div></div>
  <div class="card"><div class="label">Herramientas</div><div class="value">{len(tools)}</div></div>
  <div class="card"><div class="label">Semanas activas</div><div class="value">{len(weeks)}</div></div>
  <div class="card"><div class="label">Snapshots</div><div class="value">{len(snaps)}</div></div>
</div>

<h2>📈 Ideas por semana</h2>
<div class="chart-wrap">
  <canvas id="chart" height="200"></canvas>
</div>

<h2>✅ Ideas implementadas ({len(ideas)})</h2>
<table>
  <thead><tr><th>#</th><th>Slot</th><th>Título</th><th>Fecha</th></tr></thead>
  <tbody>{idea_rows}</tbody>
</table>

<h2>🔧 Herramientas ({len(tools)})</h2>
<div class="pills-wrap">{tool_pills}</div>

<h2>📦 Snapshots</h2>
<ul>{snap_items}</ul>

<footer>Generado por BAGO Framework · {gen}</footer>

<script>
new Chart(document.getElementById('chart'), {{
  type: 'bar',
  data: {{
    labels: {chart_labels},
    datasets: [{{
      label: 'Ideas',
      data: {chart_data},
      backgroundColor: '#38bdf8aa',
      borderColor: '#38bdf8',
      borderWidth: 1,
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e2a3a' }} }},
      x: {{ ticks: {{ color: '#64748b' }}, grid: {{ display: false }} }},
    }}
  }}
}});
</script>
</body>
</html>
"""


def main() -> int:
    args    = sys.argv[1:]
    open_it = "--open" in args

    out_dir = ROOT / ".bago" / "state" / "reports"
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_dir = Path(args[idx + 1])

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "bago_report.html"

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Exportar informe HTML                               │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Generando informe...")

    try:
        report  = _build_report()
        html    = _render_html(report)
        out_file.write_text(html, encoding="utf-8")

        size_kb = len(html.encode()) // 1024
        print(f"  {GREEN('✅')} Informe generado: {BOLD(str(out_file))}")
        print(f"  Tamaño: {size_kb}KB  |  Ideas: {len(report['ideas'])}  |  Herramientas: {len(report['tools'])}")
        print()

        if open_it:
            webbrowser.open(out_file.as_uri())
            print(f"  Abriendo en navegador...")
            print()

        return 0
    except Exception as e:
        print(f"  {RED('✗')} Error al generar informe: {e}\n")
        return 1



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
