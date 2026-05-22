#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path


def parse_iso(ts: str):
    # Accept both Z and +00:00
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return dt.datetime.fromisoformat(ts)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(s: str):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_template(title: str, width: int, height: int, body: str):
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
<style>
text {{ font-family: Menlo, Consolas, monospace; fill: #0f172a; }}
.axis {{ stroke: #64748b; stroke-width: 1; }}
.grid {{ stroke: #cbd5e1; stroke-width: 1; stroke-dasharray: 3 3; }}
.title {{ font-size: 16px; font-weight: 700; }}
.label {{ font-size: 11px; }}
</style>
<rect x='0' y='0' width='{width}' height='{height}' fill='#f8fafc'/>
<text x='20' y='26' class='title'>{esc(title)}</text>
{body}
</svg>
"""


def line_chart(points, title, y_label, out_path: Path, color="#2563eb"):
    width, height = 980, 420
    left, right, top, bottom = 70, 30, 55, 55
    cw = width - left - right
    ch = height - top - bottom

    xs = [p[0] for p in points] or [0]
    ys = [p[1] for p in points] or [0]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = 0, max(ys) if ys else 1
    if xmax == xmin:
        xmax += 1
    if ymax == ymin:
        ymax += 1

    def px(x):
        return left + ((x - xmin) / (xmax - xmin)) * cw

    def py(y):
        return top + ch - ((y - ymin) / (ymax - ymin)) * ch

    grid = []
    ticks = 5
    for i in range(ticks + 1):
        yv = ymin + (ymax - ymin) * i / ticks
        y = py(yv)
        grid.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left+cw}' y2='{y:.2f}' class='grid' />")
        grid.append(f"<text x='8' y='{y+4:.2f}' class='label'>{yv:.1f}</text>")

    path_d = ""
    for i, (xv, yv) in enumerate(points):
        cmd = "M" if i == 0 else "L"
        path_d += f" {cmd} {px(xv):.2f} {py(yv):.2f}"

    body = [
        *grid,
        f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
        f"<path d='{path_d}' fill='none' stroke='{color}' stroke-width='2.5' />" if path_d else "",
        f"<text x='{width/2:.0f}' y='{height-15}' text-anchor='middle' class='label'>segundos desde inicio</text>",
        f"<text x='14' y='{top-8}' class='label'>{esc(y_label)}</text>",
    ]
    out_path.write_text(svg_template(title, width, height, "\n".join(body)), encoding="utf-8")


def bar_chart(labels, values, title, y_label, out_path: Path, color="#0f766e"):
    width, height = 980, 420
    left, right, top, bottom = 70, 30, 55, 95
    cw = width - left - right
    ch = height - top - bottom
    n = max(1, len(values))
    ymax = max(values) if values else 1
    if ymax == 0:
        ymax = 1

    bar_w = cw / n * 0.7
    gap = cw / n * 0.3

    parts = []
    ticks = 5
    for i in range(ticks + 1):
        yv = ymax * i / ticks
        y = top + ch - (yv / ymax) * ch
        parts.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left+cw}' y2='{y:.2f}' class='grid' />")
        parts.append(f"<text x='8' y='{y+4:.2f}' class='label'>{yv:.1f}</text>")

    for i, (lab, val) in enumerate(zip(labels, values)):
        x = left + i * (bar_w + gap) + gap / 2
        h = (val / ymax) * ch
        y = top + ch - h
        parts.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_w:.2f}' height='{h:.2f}' fill='{color}' rx='3'/>" )
        parts.append(f"<text x='{x + bar_w/2:.2f}' y='{top+ch+15:.2f}' text-anchor='middle' class='label'>{esc(lab)}</text>")
        parts.append(f"<text x='{x + bar_w/2:.2f}' y='{y-6:.2f}' text-anchor='middle' class='label'>{val:.1f}</text>")

    parts.extend(
        [
            f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
            f"<text x='{width/2:.0f}' y='{height-15}' text-anchor='middle' class='label'>agentes</text>",
            f"<text x='14' y='{top-8}' class='label'>{esc(y_label)}</text>",
        ]
    )

    out_path.write_text(svg_template(title, width, height, "\n".join(parts)), encoding="utf-8")


def normalize_error_label(label: str):
    if not label or label == "none":
        return "none"
    if len(label) <= 28:
        return label
    return label[:25] + "..."


def main():
    ap = argparse.ArgumentParser(description="Renderiza gráficas SVG de un run de stress")
    ap.add_argument("--run-dir", required=True, help="Directorio del run (stress_YYYY...) ")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    results = read_csv(run_dir / "results.csv")
    timeline = read_csv(run_dir / "agent_timeline.csv")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    # Throughput por segundo
    t0 = min(parse_iso(r["timestamp_utc"]) for r in results)
    bucket = defaultdict(int)
    for r in results:
        sec = int((parse_iso(r["timestamp_utc"]) - t0).total_seconds())
        bucket[sec] += 1
    throughput_points = sorted(bucket.items())
    throughput_10s = [
        (int(x["second_from_start"]), float(x["rps_avg"]))
        for x in summary.get("throughput_windows_10s", [])
    ]

    # P95 latencia por agente
    by_agent_lat = defaultdict(list)
    for r in results:
        by_agent_lat[r["agent"]].append(float(r["latency_ms"]))

    def p95(vals):
        vals = sorted(vals)
        if not vals:
            return 0.0
        idx = int(round((len(vals) - 1) * 0.95))
        return vals[idx]

    agent_labels = sorted(by_agent_lat.keys())
    p95_values = [p95(by_agent_lat[a]) for a in agent_labels]

    # Errores por agente
    by_agent_err = defaultdict(int)
    for r in results:
        if str(r["ok"]).lower() not in ("true", "1"):
            by_agent_err[r["agent"]] += 1
    err_values = [by_agent_err[a] for a in agent_labels]

    # Reintentos por agente
    by_agent_retry = defaultdict(int)
    for r in results:
        by_agent_retry[r["agent"]] += int(r.get("retries_used") or 0)
    retry_values = [by_agent_retry[a] for a in agent_labels]

    # Errores por tipo desde summary endurecido
    error_breakdown = summary.get("error_breakdown") or {}
    error_labels = [normalize_error_label(k) for k, v in error_breakdown.items() if k != "none" and v > 0]
    error_type_values = [v for k, v in error_breakdown.items() if k != "none" and v > 0]

    # CPU promedio por agente desde timeline
    cpu_acc = defaultdict(list)
    for r in timeline:
        cpu_acc[r["agent"]].append(float(r.get("pid_cpu_pct") or 0.0))
    cpu_values = [sum(cpu_acc[a]) / max(1, len(cpu_acc[a])) for a in agent_labels]

    charts_dir = run_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    line_chart(
        throughput_points,
        title="Throughput por segundo",
        y_label="req/s",
        out_path=charts_dir / "throughput.svg",
        color="#1d4ed8",
    )
    line_chart(
        throughput_10s,
        title="Throughput promedio por ventana de 10s",
        y_label="req/s avg",
        out_path=charts_dir / "throughput_10s.svg",
        color="#0369a1",
    )
    bar_chart(
        labels=agent_labels,
        values=p95_values,
        title="P95 de latencia por agente",
        y_label="ms",
        out_path=charts_dir / "latency_p95_by_agent.svg",
        color="#0f766e",
    )
    bar_chart(
        labels=agent_labels,
        values=err_values,
        title="Errores por agente",
        y_label="errores",
        out_path=charts_dir / "errors_by_agent.svg",
        color="#b91c1c",
    )
    bar_chart(
        labels=agent_labels,
        values=retry_values,
        title="Reintentos acumulados por agente",
        y_label="retries",
        out_path=charts_dir / "retries_by_agent.svg",
        color="#c2410c",
    )
    bar_chart(
        labels=error_labels or ["none"],
        values=error_type_values or [0],
        title="Errores por tipo",
        y_label="errores",
        out_path=charts_dir / "errors_by_type.svg",
        color="#be123c",
    )
    bar_chart(
        labels=agent_labels,
        values=cpu_values,
        title="CPU promedio por agente (proceso)",
        y_label="%cpu",
        out_path=charts_dir / "cpu_avg_by_agent.svg",
        color="#7c3aed",
    )

    report = {
        "run_dir": str(run_dir),
        "summary": summary,
        "charts": [
            str(charts_dir / "throughput.svg"),
            str(charts_dir / "throughput_10s.svg"),
            str(charts_dir / "latency_p95_by_agent.svg"),
            str(charts_dir / "errors_by_agent.svg"),
            str(charts_dir / "retries_by_agent.svg"),
            str(charts_dir / "errors_by_type.svg"),
            str(charts_dir / "cpu_avg_by_agent.svg"),
        ],
    }
    (run_dir / "charts" / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
