from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _evolution_collectors import MADRID, esc, parse_iso


def svg_template(title: str, width: int, height: int, body: str) -> str:
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
<style>
text {{ font-family: Menlo, Consolas, monospace; fill: #0f172a; }}
.axis {{ stroke: #64748b; stroke-width: 1; }}
.grid {{ stroke: #cbd5e1; stroke-width: 1; stroke-dasharray: 3 3; }}
.title {{ font-size: 17px; font-weight: 700; }}
.label {{ font-size: 11px; }}
.small {{ font-size: 10px; }}
</style>
<rect x='0' y='0' width='{width}' height='{height}' fill='#f8fafc'/>
<text x='20' y='26' class='title'>{esc(title)}</text>
{body}
</svg>
"""


def write_svg(path: Path, svg: str) -> None:
    path.write_text(svg, encoding="utf-8")


def simple_bar_chart(labels, values, title, y_label, out_path: Path, color="#2563eb") -> None:
    width, height = 980, 420
    left, right, top, bottom = 70, 30, 52, 80
    cw = width - left - right
    ch = height - top - bottom
    n = max(1, len(values))
    ymax = max(values) if values else 1
    ymax = ymax if ymax > 0 else 1
    bar_w = cw / n * 0.68
    step = cw / n
    body = []
    for i in range(6):
        yv = ymax * i / 5
        y = top + ch - (yv / ymax) * ch
        body.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left+cw}' y2='{y:.2f}' class='grid' />")
        body.append(f"<text x='8' y='{y+4:.2f}' class='label'>{yv:.1f}</text>")
    for i, (label, value) in enumerate(zip(labels, values)):
        x = left + i * step + (step - bar_w) / 2
        h = (value / ymax) * ch if ymax else 0
        y = top + ch - h
        body.append(
            f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_w:.2f}' height='{h:.2f}' fill='{color}' rx='3'/>"
        )
        body.append(
            f"<text x='{x + bar_w/2:.2f}' y='{top+ch+16:.2f}' text-anchor='middle' class='label'>{esc(label)}</text>"
        )
        body.append(
            f"<text x='{x + bar_w/2:.2f}' y='{y-6:.2f}' text-anchor='middle' class='label'>{value:.1f}</text>"
        )
    body.extend(
        [
            f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
            f"<text x='{width/2:.0f}' y='{height-12}' text-anchor='middle' class='label'>{esc(y_label)}</text>",
            f"<text x='14' y='{top-8}' class='label'>valor</text>",
        ]
    )
    write_svg(out_path, svg_template(title, width, height, "\n".join(body)))


def grouped_bar_chart(groups, categories, values, title, out_path: Path) -> None:
    width, height = 980, 440
    left, right, top, bottom = 80, 30, 55, 95
    cw = width - left - right
    ch = height - top - bottom
    max_total = max(sum(values[g].get(cat, 0) for cat in categories) for g in groups) if groups else 1
    max_total = max_total if max_total > 0 else 1
    group_w = cw / max(1, len(groups))
    bar_w = group_w * 0.55
    palette = ["#1d4ed8", "#0f766e", "#c2410c", "#7c3aed", "#b91c1c", "#0369a1"]
    body = []
    for i in range(6):
        yv = max_total * i / 5
        y = top + ch - (yv / max_total) * ch
        body.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left+cw}' y2='{y:.2f}' class='grid' />")
        body.append(f"<text x='8' y='{y+4:.2f}' class='label'>{yv:.1f}</text>")

    for gi, group in enumerate(groups):
        x_center = left + gi * group_w + group_w / 2
        x = x_center - bar_w / 2
        y_cursor = top + ch
        total = sum(values[group].get(cat, 0) for cat in categories)
        for ci, cat in enumerate(categories):
            val = values[group].get(cat, 0)
            h = (val / max_total) * ch if max_total else 0
            y = y_cursor - h
            if val > 0:
                body.append(
                    f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_w:.2f}' height='{h:.2f}' fill='{palette[ci % len(palette)]}' rx='2'/>"
                )
            y_cursor = y
        body.append(
            f"<text x='{x_center:.2f}' y='{top+ch+16:.2f}' text-anchor='middle' class='label'>{esc(group)}</text>"
        )
        body.append(
            f"<text x='{x_center:.2f}' y='{top+ch+32:.2f}' text-anchor='middle' class='small'>{total}</text>"
        )

    legend_x = left
    legend_y = height - 30
    for ci, cat in enumerate(categories):
        x = legend_x + ci * 150
        body.append(f"<rect x='{x}' y='{legend_y-10}' width='12' height='12' fill='{palette[ci % len(palette)]}' rx='2'/>")
        body.append(f"<text x='{x+18}' y='{legend_y}' class='label'>{esc(cat)}</text>")

    body.extend(
        [
            f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
            f"<text x='{width/2:.0f}' y='{height-12}' text-anchor='middle' class='label'>fase</text>",
        ]
    )
    write_svg(out_path, svg_template(title, width, height, "\n".join(body)))


def timeline_chart(clusters, title, out_path: Path) -> None:
    width, height = 1180, 420
    left, right, top, bottom = 145, 30, 55, 80
    cw = width - left - right
    ch = height - top - bottom
    t0 = min(c["start"] for c in clusters)
    t1 = max(c["end"] for c in clusters)
    span = (t1 - t0).total_seconds() or 1
    row_h = ch / max(1, len(clusters))
    body = []

    for i in range(6):
        frac = i / 5
        x = left + frac * cw
        body.append(f"<line x1='{x:.2f}' y1='{top}' x2='{x:.2f}' y2='{top+ch}' class='grid' />")
        tick_t = t0 + dt.timedelta(seconds=span * frac)
        body.append(
            f"<text x='{x:.2f}' y='{top+ch+18}' text-anchor='middle' class='small'>{tick_t.strftime('%d/%m %H:%M')}</text>"
        )

    for idx, c in enumerate(clusters):
        y = top + idx * row_h + row_h * 0.25
        h = row_h * 0.5
        x1 = left + ((c["start"] - t0).total_seconds() / span) * cw
        x2 = left + ((c["end"] - t0).total_seconds() / span) * cw
        body.append(f"<rect x='{x1:.2f}' y='{y:.2f}' width='{max(3, x2-x1):.2f}' height='{h:.2f}' fill='#0f766e' rx='4'/>")
        label = (
            f"{c['label']} | {c['run_count']} corridas | "
            f"{round(c['duration_s'],1)} s | {c['requests']} req"
        )
        body.append(f"<text x='{left-10}' y='{y + h*0.72:.2f}' text-anchor='end' class='label'>{esc(label)}</text>")
        body.append(
            f"<text x='{x1+4:.2f}' y='{y - 4:.2f}' class='small'>{c['start_local']}</text>"
        )

    body.extend(
        [
            f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
            f"<text x='{width/2:.0f}' y='{height-12}' text-anchor='middle' class='label'>tiempo</text>",
        ]
    )
    write_svg(out_path, svg_template(title, width, height, "\n".join(body)))


def heatmap_chart(rows, cols, values, title, out_path: Path) -> None:
    width, height = 1180, 520
    left, right, top, bottom = 160, 40, 70, 90
    cw = width - left - right
    ch = height - top - bottom
    row_h = ch / max(1, len(rows))
    col_w = cw / max(1, len(cols))
    max_value = max((values.get(r, {}).get(c, 0) for r in rows for c in cols), default=1)
    max_value = max_value if max_value > 0 else 1
    body = []

    def fill_for(v: int) -> str:
        # Simple blue-green ramp without external dependencies.
        if v <= 0:
            return "#e2e8f0"
        ratio = v / max_value
        if ratio < 0.25:
            return "#c7f9cc"
        if ratio < 0.5:
            return "#86efac"
        if ratio < 0.75:
            return "#34d399"
        return "#0f766e"

    for i in range(6):
        frac = i / 5
        x = left + frac * cw
        body.append(f"<line x1='{x:.2f}' y1='{top}' x2='{x:.2f}' y2='{top+ch}' class='grid' />")
    for i, row in enumerate(rows):
        y = top + i * row_h
        body.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left+cw}' y2='{y:.2f}' class='grid' />")
        body.append(f"<text x='{left-12}' y='{y + row_h*0.68:.2f}' text-anchor='end' class='label'>{esc(row)}</text>")
        for j, col in enumerate(cols):
            v = values.get(row, {}).get(col, 0)
            x = left + j * col_w
            fill = fill_for(v)
            body.append(
                f"<rect x='{x:.2f}' y='{y:.2f}' width='{col_w:.2f}' height='{row_h:.2f}' fill='{fill}' stroke='#ffffff' stroke-width='1'/>"
            )
            if v > 0:
                body.append(
                    f"<text x='{x + col_w/2:.2f}' y='{y + row_h/2 + 4:.2f}' text-anchor='middle' class='label'>{v}</text>"
                )
    for j, col in enumerate(cols):
        x = left + j * col_w + col_w / 2
        body.append(f"<text x='{x:.2f}' y='{top-10}' text-anchor='middle' class='small'>{esc(col)}</text>")

    body.extend(
        [
            f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
            f"<text x='{width/2:.0f}' y='{height-12}' text-anchor='middle' class='label'>fecha local (Europe/Madrid)</text>",
        ]
    )
    write_svg(out_path, svg_template(title, width, height, "\n".join(body)))


def phase_task_mix_chart(early_counts, late_counts, title, out_path: Path) -> None:
    phases = ["inicio", "ahora"]
    categories = ["system_change", "project_bootstrap", "analysis", "repository_audit", "execution"]
    values = {
        "inicio": early_counts,
        "ahora": late_counts,
    }
    grouped_bar_chart(phases, categories, values, title, out_path)


def build_activity_by_day_svg(all_days, day_values, out_path: Path) -> None:
    width, height = 1180, 440
    left, right, top, bottom = 80, 30, 55, 100
    cw = width - left - right
    ch = height - top - bottom
    max_total = max(sum(v.values()) for v in day_values.values()) if day_values else 1
    max_total = max_total if max_total > 0 else 1
    day_step = cw / max(1, len(all_days))
    bar_w = day_step * 0.56
    palette = {"sessions": "#1d4ed8", "changes": "#0f766e", "evidences": "#c2410c"}
    body = []
    for i in range(6):
        yv = max_total * i / 5
        y = top + ch - (yv / max_total) * ch
        body.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left+cw}' y2='{y:.2f}' class='grid' />")
        body.append(f"<text x='8' y='{y+4:.2f}' class='label'>{yv:.1f}</text>")
    for i, day in enumerate(all_days):
        x = left + i * day_step + (day_step - bar_w) / 2
        y_cursor = top + ch
        total = 0
        for cat in ("sessions", "changes", "evidences"):
            val = day_values[day][cat]
            total += val
            h = (val / max_total) * ch if max_total else 0
            y = y_cursor - h
            if val > 0:
                body.append(
                    f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_w:.2f}' height='{h:.2f}' fill='{palette[cat]}' rx='2'/>"
                )
            y_cursor = y
        body.append(f"<text x='{x + bar_w/2:.2f}' y='{top+ch+16:.2f}' text-anchor='middle' class='label'>{day}</text>")
        body.append(f"<text x='{x + bar_w/2:.2f}' y='{top+ch+31:.2f}' text-anchor='middle' class='small'>{total}</text>")
    body.extend(
        [
            f"<rect x='{left}' y='{height-32}' width='12' height='12' fill='{palette['sessions']}' rx='2'/>",
            f"<text x='{left+18}' y='{height-22}' class='label'>sessions</text>",
            f"<rect x='{left+120}' y='{height-32}' width='12' height='12' fill='{palette['changes']}' rx='2'/>",
            f"<text x='{left+138}' y='{height-22}' class='label'>changes</text>",
            f"<rect x='{left+240}' y='{height-32}' width='12' height='12' fill='{palette['evidences']}' rx='2'/>",
            f"<text x='{left+258}' y='{height-22}' class='label'>evidences</text>",
            f"<line x1='{left}' y1='{top+ch}' x2='{left+cw}' y2='{top+ch}' class='axis' />",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top+ch}' class='axis' />",
            f"<text x='{width/2:.0f}' y='{height-12}' text-anchor='middle' class='label'>fecha local (Europe/Madrid)</text>",
        ]
    )
    write_svg(out_path, svg_template("Actividad diaria del sistema", width, height, "\n".join(body)))


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())

