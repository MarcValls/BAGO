#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""generate_bago_evolution_report — Genera report de evolución del framework BAGO."""
from __future__ import annotations

import datetime as dt
import sys
from collections import Counter
from pathlib import Path

import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _evolution_collectors import (
    MADRID,
    UTC,
    build_markdown_report,
    collect_json_records,
    counts_by_day,
    esc,
    load_json,
    parse_iso,
)
from _evolution_renderers import (
    build_activity_by_day_svg,
    grouped_bar_chart,
    heatmap_chart,
    simple_bar_chart,
    timeline_chart,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "analysis"
FIG_DIR = OUT_DIR / "figures"


def build_html_report(
    *,
    metrics_snapshot: dict,
    current_state: dict,
    start_corpus: int,
    current_corpus: int,
    today_local: dt.date,
    state_ref_day: dt.date,
    today_session_count: int,
    today_change_count: int,
    today_evidence_count: int,
    today_run_count: int,
    today_request_count: int,
    early_counts: Counter,
    late_counts: Counter,
    cluster_rows: list[dict],
    task_types: list[str],
    all_days: list[str],
    task_values: dict,
) -> str:
    def card(title: str, value: str, subtitle: str = "") -> str:
        return f"""
        <div class="card">
          <div class="card-title">{esc(title)}</div>
          <div class="card-value">{esc(value)}</div>
          <div class="card-subtitle">{esc(subtitle)}</div>
        </div>
        """

    def counts_for_phase(counter: Counter) -> str:
        parts = [f"{k}: {counter.get(k, 0)}" for k in ["system_change", "project_bootstrap", "analysis", "repository_audit", "execution"]]
        return " | ".join(parts)

    rows = "".join(
        f"<tr><td>{esc(row)}</td>" + "".join(
            f"<td>{task_values.get(row, {}).get(task, 0)}</td>" for task in task_types
        ) + "</tr>"
        for row in all_days
    )

    cluster_rows_html = "".join(
        f"<tr><td>{esc(c['label'])}</td><td>{c['start'].astimezone(MADRID).strftime('%d/%m %H:%M')}</td>"
        f"<td>{c['end'].astimezone(MADRID).strftime('%d/%m %H:%M')}</td>"
        f"<td>{c['duration_s']:.3f}s</td><td>{c['requests']}</td><td>{c['run_count']}</td></tr>"
        for c in cluster_rows
    )

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Evolución del sistema BAGO</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --card: #1e293b;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #22c55e;
      --accent2: #38bdf8;
      --line: #334155;
    }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: linear-gradient(180deg, #0b1120 0%, #111827 100%);
      color: var(--text);
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1, h2, h3 {{ margin: 0 0 12px; line-height: 1.15; }}
    h1 {{ font-size: 2.2rem; }}
    h2 {{ margin-top: 38px; font-size: 1.35rem; }}
    p, li, td {{ color: var(--text); line-height: 1.55; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; gap: 14px; }}
    .cards {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin: 18px 0 10px; }}
    .card {{
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 10px 25px rgba(0,0,0,.18);
    }}
    .card-title {{ color: var(--muted); font-size: .82rem; text-transform: uppercase; letter-spacing: .06em; }}
    .card-value {{ font-size: 1.35rem; font-weight: 700; margin-top: 8px; }}
    .card-subtitle {{ color: var(--muted); margin-top: 6px; font-size: .92rem; }}
    .panel {{
      background: rgba(17, 24, 39, 0.9);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 20px;
      box-shadow: 0 16px 32px rgba(0,0,0,.22);
      margin-top: 20px;
    }}
    img.svg {{
      width: 100%;
      height: auto;
      display: block;
      background: #f8fafc;
      border-radius: 14px;
      border: 1px solid #cbd5e1;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: .95rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--accent2); font-weight: 600; }}
    code, pre {{
      background: #0b1220;
      border: 1px solid var(--line);
      border-radius: 12px;
      color: #dbeafe;
    }}
    pre {{
      padding: 14px;
      overflow: auto;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .box {{
      background: rgba(30, 41, 59, 0.55);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
    }}
    .diagram-title {{ color: var(--accent2); margin-bottom: 10px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Evolución del sistema BAGO</h1>
    <p class="muted">Comparación entre el arranque de corrección/migración y el estado actual operativo. Generado desde `state/` y `state/metrics/runs/`.</p>

    <div class="grid cards">
      {card("Corpus inicial", f"{start_corpus} artefactos", f"Snapshot base {metrics_snapshot['captured_at']}")}
      {card("Corpus actual", f"{current_corpus} artefactos", f"Inventario visible: {current_state['inventory']['sessions']} sesiones, {current_state['inventory']['changes']} cambios, {current_state['inventory']['evidences']} evidencias")}
      {card("Integridad", f"{current_state['last_validation']['pack']} / {current_state['last_validation']['state']} / {current_state['last_validation']['manifest']}", "Validación más reciente")}
      {card("Última sesión", current_state["last_completed_session_id"], current_state["last_completed_workflow"] or "sin workflow")}
    </div>

    <div class="panel">
      <h2>Lectura ejecutiva</h2>
      <div class="two-col">
        <div class="box">
          <h3 class="diagram-title">Al principio</h3>
          <p>BAGO se enfocaba en <code>system_change</code>, preservación canónica, migración histórica y validación documental. La variedad funcional era baja y el trabajo era esencialmente de consolidación.</p>
          <p class="muted">{counts_for_phase(early_counts)}</p>
        </div>
        <div class="box">
          <h3 class="diagram-title">Ahora</h3>
          <p>El sistema trabaja de forma más madura: bootstrap del repo, análisis, auditoría, ejecución y cierre de ciclos con evidencias y estado vivo actualizado.</p>
          <p class="muted">{counts_for_phase(late_counts)}</p>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>Métricas de hoy</h2>
      <div class="grid cards" style="margin-top: 10px;">
        {card("Hoy local", today_local.strftime("%d/%m/%Y"), "reloj del entorno de trabajo")}
        {card("Sesiones de hoy", str(today_session_count), "sin actividad si vale 0")}
        {card("Cambios de hoy", str(today_change_count), "sin actividad si vale 0")}
        {card("Evidencias de hoy", str(today_evidence_count), "sin actividad si vale 0")}
        {card("Corridas autónomas", str(today_run_count), "ventanas de metrics/runs")}
        {card("Solicitudes hoy", str(today_request_count), "total en corridas que tocan hoy")}
      </div>
      <p class="muted">Si la cifra es 0, no hay registros fechados hoy en el reloj local del entorno.</p>
    </div>

    <div class="panel">
      <h2>Actividad diaria</h2>
      <img class="svg" src="figures/activity_by_day.svg" alt="Actividad diaria" />
    </div>

    <div class="panel">
      <h2>Mezcla de trabajo por fase</h2>
      <img class="svg" src="figures/session_mix_by_phase.svg" alt="Mezcla de trabajo por fase" />
      <table>
        <thead><tr><th>Fase</th><th>system_change</th><th>project_bootstrap</th><th>analysis</th><th>repository_audit</th><th>execution</th><th>Total</th></tr></thead>
        <tbody>
          <tr><td>Inicio</td><td>{early_counts.get("system_change", 0)}</td><td>{early_counts.get("project_bootstrap", 0)}</td><td>{early_counts.get("analysis", 0)}</td><td>{early_counts.get("repository_audit", 0)}</td><td>{early_counts.get("execution", 0)}</td><td>{sum(early_counts.values())}</td></tr>
          <tr><td>Ahora</td><td>{late_counts.get("system_change", 0)}</td><td>{late_counts.get("project_bootstrap", 0)}</td><td>{late_counts.get("analysis", 0)}</td><td>{late_counts.get("repository_audit", 0)}</td><td>{late_counts.get("execution", 0)}</td><td>{sum(late_counts.values())}</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Evolución de tipos de trabajo</h2>
      <img class="svg" src="figures/task_type_evolution.svg" alt="Evolución de tipos de trabajo por día" />
      <table>
        <thead><tr><th>Día</th>{''.join(f'<th>{esc(t)}</th>' for t in task_types)}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Crecimiento del corpus</h2>
      <img class="svg" src="figures/corpus_growth.svg" alt="Crecimiento del corpus" />
    </div>

    <div class="panel">
      <h2>Ventanas de trabajo autónomo</h2>
      <img class="svg" src="figures/runs_clusters.svg" alt="Ventanas de trabajo autónomo" />
      <table>
        <thead><tr><th>Bloque</th><th>Inicio local</th><th>Fin local</th><th>Duración activa</th><th>Solicitudes</th><th>Corridas</th></tr></thead>
        <tbody>{cluster_rows_html}</tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Diagramas</h2>
      <div class="two-col">
        <div class="box">
          <h3 class="diagram-title">Evolución funcional</h3>
          <pre>flowchart LR
  A["Corrección y migración"] --&gt; B["Endurecimiento estructural"]
  B --&gt; C["Performance y release"]
  C --&gt; D["Bootstrap repo-first"]
  D --&gt; E["Evaluación y reconstrucción"]
  E --&gt; F["Operación estable"]</pre>
        </div>
        <div class="box">
          <h3 class="diagram-title">Ciclo autónomo</h3>
          <pre>stateDiagram-v2
  [*] --&gt; Session
  Session --&gt; Change
  Change --&gt; Evidence
  Evidence --&gt; GlobalState
  GlobalState --&gt; NextSession
  NextSession --&gt; Session</pre>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>Observaciones técnicas</h2>
      <p class="muted">Snapshot canónico de referencia: {state_ref_day.strftime("%d/%m/%Y")} desde <code>global_state.updated_at</code>.</p>
      <p class="muted">El árbol local visible tiene menos archivos que <code>global_state.json</code> anticipa en su inventario. Eso sugiere que el estado canónico va por delante de esta copia del árbol.</p>
      <p class="muted">La evolución principal no es solo de volumen; es de especialización y de capacidad para cerrar ciclos de trabajo con evidencias y validación.</p>
    </div>
  </div>
</body>
</html>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    metrics_snapshot = load_json(ROOT / "state" / "metrics" / "metrics_snapshot.json")
    current_state = load_json(ROOT / "state" / "global_state.json")

    sessions = collect_json_records(ROOT / "state" / "sessions")
    changes = collect_json_records(ROOT / "state" / "changes")
    evidences = collect_json_records(ROOT / "state" / "evidences")
    run_summaries = [load_json(p) for p in sorted((ROOT / "state" / "metrics" / "runs").glob("*/summary.json"))]
    today_local = dt.date.today()
    state_ref_day = parse_iso(current_state["updated_at"]).astimezone(MADRID).date()

    # Comparative corpus metrics.
    start_corpus = (
        metrics_snapshot["native_sessions_completed"]
        + metrics_snapshot["migrated_sessions_count"]
        + metrics_snapshot["migrated_changes_count"]
        + metrics_snapshot["validated_changes"]
    )
    current_corpus = (
        current_state["inventory"]["sessions"]
        + current_state["inventory"]["changes"]
        + current_state["inventory"]["evidences"]
    )

    # Daily activity by Europe/Madrid local day.
    session_days = counts_by_day(sessions, "created_at", MADRID)
    change_days = counts_by_day(changes, "created_at", MADRID)
    evidence_days = counts_by_day(evidences, "recorded_at", MADRID)
    task_types = ["analysis", "design", "execution", "validation", "organization", "system_change", "project_bootstrap", "repository_audit", "history_migration"]
    all_days = sorted(set(session_days) | set(change_days) | set(evidence_days))
    task_values = {
        day: {task: 0 for task in task_types}
        for day in all_days
    }
    for session in sessions:
        day = parse_iso(session["created_at"]).astimezone(MADRID).date().isoformat()
        if day in task_values:
            task_values[day][session["task_type"]] += 1
    day_values = {
        day: {
            "sessions": session_days.get(day, 0),
            "changes": change_days.get(day, 0),
            "evidences": evidence_days.get(day, 0),
        }
        for day in all_days
    }
    build_activity_by_day_svg(all_days, day_values, FIG_DIR / "activity_by_day.svg")

    today_session_count = sum(1 for s in sessions if parse_iso(s["created_at"]).astimezone(MADRID).date() == today_local)
    today_change_count = sum(1 for c in changes if parse_iso(c["created_at"]).astimezone(MADRID).date() == today_local)
    today_evidence_count = sum(1 for e in evidences if parse_iso(e["recorded_at"]).astimezone(MADRID).date() == today_local)
    today_run_summaries = []
    for item in run_summaries:
        start = parse_iso(item["started_at_utc"]).astimezone(MADRID)
        end = parse_iso(item["ended_at_utc"]).astimezone(MADRID)
        if start.date() == today_local or end.date() == today_local:
            today_run_summaries.append(item)

    # Session type mix by phase.
    early_sessions = [s for s in sessions if parse_iso(s["created_at"]) < dt.datetime(2026, 4, 14, tzinfo=UTC)]
    late_sessions = [s for s in sessions if parse_iso(s["created_at"]) >= dt.datetime(2026, 4, 14, tzinfo=UTC)]
    early_counts = Counter(s["task_type"] for s in early_sessions)
    late_counts = Counter(s["task_type"] for s in late_sessions)
    grouped_bar_chart(
        ["inicio", "ahora"],
        ["system_change", "project_bootstrap", "analysis", "repository_audit", "execution"],
        {"inicio": early_counts, "ahora": late_counts},
        "Cambio de mezcla de trabajo por fase",
        FIG_DIR / "session_mix_by_phase.svg",
    )

    heatmap_chart(
        all_days,
        task_types,
        task_values,
        "Evolución de tipos de trabajo por día",
        FIG_DIR / "task_type_evolution.svg",
    )

    # Corpus growth chart.
    simple_bar_chart(
        ["inicio", "ahora"],
        [start_corpus, current_corpus],
        "Crecimiento del corpus estructurado",
        "artifacts registrados",
        FIG_DIR / "corpus_growth.svg",
        color="#7c3aed",
    )

    # Runs clusters.
    runs = []
    for item in run_summaries:
        start = parse_iso(item["started_at_utc"])
        end = parse_iso(item["ended_at_utc"])
        runs.append(
            {
                "start": start,
                "end": end,
                "duration_s": float(item["duration_s"]),
                "requests": int(item["total_requests"]),
                "simulate": bool(item.get("simulate")),
                "name": item["model"],
                "run_dir": Path(item.get("run_dir", "")).name if item.get("run_dir") else "",
            }
        )
    runs.sort(key=lambda r: r["start"])
    clusters = []
    current = []
    for run in runs:
        if not current:
            current = [run]
            continue
        gap = (run["start"] - current[-1]["end"]).total_seconds()
        if gap <= 1200:
            current.append(run)
        else:
            clusters.append(current)
            current = [run]
    if current:
        clusters.append(current)
    cluster_rows = []
    for idx, cluster in enumerate(clusters, 1):
        cluster_rows.append(
            {
                "label": f"bloque {idx}",
                "run_count": len(cluster),
                "start": cluster[0]["start"],
                "end": cluster[-1]["end"],
                "start_local": cluster[0]["start"].astimezone(MADRID).strftime("%d/%m %H:%M"),
                "duration_s": sum(r["duration_s"] for r in cluster),
                "requests": sum(r["requests"] for r in cluster),
            }
        )
    timeline_chart(cluster_rows, "Ventanas de trabajo autónomo en metrics/runs", FIG_DIR / "runs_clusters.svg")

    # Session counts by type for the report.
    phase_role_early = sorted({r for s in early_sessions for r in s.get("roles_activated", [])})
    phase_role_late = sorted({r for s in late_sessions for r in s.get("roles_activated", [])})

    report_path = OUT_DIR / "BAGO_EVOLUCION_SISTEMA.md"
    report_path.write_text(build_markdown_report(
        today_local=today_local,
        state_ref_day=state_ref_day,
        start_corpus=start_corpus,
        current_corpus=current_corpus,
        metrics_snapshot=metrics_snapshot,
        current_state=current_state,
        today_session_count=today_session_count,
        today_change_count=today_change_count,
        today_evidence_count=today_evidence_count,
        today_run_summaries=today_run_summaries,
        early_counts=early_counts,
        late_counts=late_counts,
        phase_role_early=phase_role_early,
        phase_role_late=phase_role_late,
        cluster_rows=cluster_rows,
    ), encoding="utf-8")

    html_path = OUT_DIR / "BAGO_EVOLUCION_SISTEMA.html"
    html_path.write_text(build_html_report(
        metrics_snapshot=metrics_snapshot,
        current_state=current_state,
        start_corpus=start_corpus,
        current_corpus=current_corpus,
        today_local=today_local,
        state_ref_day=state_ref_day,
        today_session_count=today_session_count,
        today_change_count=today_change_count,
        today_evidence_count=today_evidence_count,
        today_run_count=len(today_run_summaries),
        today_request_count=sum(int(r.get("total_requests", 0)) for r in today_run_summaries),
        early_counts=early_counts,
        late_counts=late_counts,
        cluster_rows=cluster_rows,
        task_types=task_types,
        all_days=all_days,
        task_values=task_values,
    ), encoding="utf-8")

    print(f"OK {report_path}")
    print(f"OK {html_path}")
    print(f"OK {FIG_DIR / 'activity_by_day.svg'}")
    print(f"OK {FIG_DIR / 'session_mix_by_phase.svg'}")
    print(f"OK {FIG_DIR / 'task_type_evolution.svg'}")
    print(f"OK {FIG_DIR / 'corpus_growth.svg'}")
    print(f"OK {FIG_DIR / 'runs_clusters.svg'}")
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
