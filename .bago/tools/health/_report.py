#!/usr/bin/env python3
"""health_report.py — Herramienta #100 (milestone): Reporte integral de salud del proyecto.

Combina: config-check + bago-lint + rule-catalog en un único documento
Markdown/HTML con resumen ejecutivo, score de salud, findings por severidad,
deuda técnica y recomendaciones priorizadas.

Uso:
    bago health-report [TARGET] [--format md|html] [--out FILE] [--open] [--test]

Opciones:
    TARGET      Ruta del proyecto a analizar (default: ./)
    --format    Formato de salida: md (default) | html
    --out FILE  Guardar en archivo en lugar de stdout
    --open      Abrir en browser si --format html
    --test      Self-tests internos
"""
from __future__ import annotations

import json
import subprocess
import sys
import datetime
from pathlib import Path
from typing import Optional

BAGO_ROOT = Path(__file__).resolve().parents[2]

# Import chart_engine (optional — graceful fallback if missing)
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chart_engine import render_gauge, render_bar, render_doughnut
    _CHARTS_OK = True
except Exception:
    _CHARTS_OK = False
TOOLS     = BAGO_ROOT / "tools"

_RED  = "\033[0;31m"
_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_BLU  = "\033[0;34m"
_RST  = "\033[0m"
_BOLD = "\033[1m"


# ─── Sub-runners ───────────────────────────────────────────────────────────

def _run_config_check(bago_root: Path) -> dict:
    """Ejecuta config_check.py --json."""
    pack = bago_root / ".bago" / "pack.json"
    if not pack.exists():
        return {"issues": [], "error": "pack.json no encontrado"}
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "config_check.py"), "--json"],
            capture_output=True, text=True, timeout=15,
            cwd=str(bago_root)
        )
        return json.loads(r.stdout) if r.stdout.strip() else {"issues": []}
    except Exception as e:
        return {"issues": [], "error": str(e)}


def _run_bago_lint(target: str) -> dict:
    """Ejecuta bago_lint_cli.py --json."""
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "bago_lint_cli.py"), target, "--json"],
            capture_output=True, text=True, timeout=60
        )
        if r.stdout.strip():
            return json.loads(r.stdout)
        return {"findings": [], "summary": {}}
    except Exception as e:
        return {"findings": [], "error": str(e)}


def _get_git_info(target: str) -> dict:
    """Información básica del repositorio git."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=target
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "log", "-1", "--format=%h %s", "--", "."],
            capture_output=True, text=True, cwd=target
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=target
        ).stdout.strip()
        return {"branch": branch, "commit": commit, "dirty": bool(dirty)}
    except Exception:
        return {}


# ─── Score calculation ──────────────────────────────────────────────────────

def _compute_score(findings: list[dict], cfg_issues: list[dict]) -> dict:
    """Calcula score 0-100 y status textual."""
    errors   = sum(1 for f in findings if f.get("severity") == "error")
    warnings = sum(1 for f in findings if f.get("severity") in ("warning", "warn"))
    infos    = sum(1 for f in findings if f.get("severity") in ("info", "convention"))

    cfg_errors   = sum(1 for i in cfg_issues if i.get("severity") == "error")
    cfg_warnings = sum(1 for i in cfg_issues if i.get("severity") == "warning")

    deductions = (errors * 5) + (warnings * 2) + (infos * 0.5) + (cfg_errors * 3) + (cfg_warnings * 1)
    score = max(0, min(100, round(100 - deductions)))

    if score >= 90:
        status = "EXCELENTE"
        emoji  = "🟢"
    elif score >= 70:
        status = "BUENO"
        emoji  = "🟡"
    elif score >= 50:
        status = "MEJORABLE"
        emoji  = "🟠"
    else:
        status = "CRÍTICO"
        emoji  = "🔴"

    return {
        "score": score, "status": status, "emoji": emoji,
        "errors": errors, "warnings": warnings, "infos": infos,
        "cfg_errors": cfg_errors, "cfg_warnings": cfg_warnings,
    }


# ─── Report generators ─────────────────────────────────────────────────────

def _top_rules(findings: list[dict], n: int = 5) -> list[tuple[str, int]]:
    """Top N reglas más frecuentes."""
    from collections import Counter
    c = Counter(f.get("rule", "?") for f in findings)
    return c.most_common(n)


def _top_files(findings: list[dict], n: int = 5) -> list[tuple[str, int]]:
    """Top N archivos con más hallazgos."""
    from collections import Counter
    c = Counter(f.get("file", "?") for f in findings)
    return c.most_common(n)


def generate_markdown(target: str, lint_data: dict, cfg_data: dict,
                      git_info: dict, title: Optional[str] = None) -> str:
    findings   = lint_data.get("findings", [])
    cfg_issues = cfg_data.get("issues", [])
    score      = _compute_score(findings, cfg_issues)
    now        = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    title      = title or f"Health Report — {Path(target).resolve().name}"

    lines = [
        f"# {title}",
        "",
        f"> Generado por **BAGO health-report** · {now}",
        "",
        "---",
        "",
        f"## {score['emoji']} Score de Salud: {score['score']}/100 — {score['status']}",
        "",
        "| Métrica | Valor |",
        "|---------|-------|",
        f"| Score   | **{score['score']}/100** |",
        f"| Errores de código  | {score['errors']} |",
        f"| Advertencias de código | {score['warnings']} |",
        f"| Info / Convenciones    | {score['infos']} |",
        f"| Errores de config      | {score['cfg_errors']} |",
        f"| Advertencias de config | {score['cfg_warnings']} |",
    ]

    if git_info:
        lines += [
            f"| Rama   | `{git_info.get('branch', '?')}` |",
            f"| Último commit | {git_info.get('commit', '?')} |",
            f"| Cambios sin commit | {'Sí ⚠️' if git_info.get('dirty') else 'No ✅'} |",
        ]

    lines += [
        "",
        "---",
        "",
        "## 📦 Configuración (pack.json)",
        "",
    ]
    if cfg_data.get("error"):
        lines.append(f"⚠️ `{cfg_data['error']}`")
    elif not cfg_issues:
        lines.append("✅ Sin problemas de configuración detectados.")
    else:
        for i in cfg_issues:
            sev_icon = "🔴" if i.get("severity") == "error" else "🟡"
            lines.append(f"- {sev_icon} `{i.get('code','?')}` — {i.get('message','')}")

    # Top reglas
    top_r = _top_rules(findings)
    lines += [
        "",
        "---",
        "",
        "## 🔍 Análisis de Código",
        "",
        f"**Total de hallazgos:** {len(findings)} "
        f"({score['errors']} errores, {score['warnings']} advertencias, {score['infos']} info)",
        "",
    ]

    if top_r:
        lines += [
            "### Top Reglas",
            "",
            "| Regla | Ocurrencias |",
            "|-------|------------|",
        ]
        for rule, cnt in top_r:
            lines.append(f"| `{rule}` | {cnt} |")

    top_f = _top_files(findings)
    if top_f:
        lines += [
            "",
            "### Archivos con más hallazgos",
            "",
            "| Archivo | Hallazgos |",
            "|---------|-----------|",
        ]
        for fname, cnt in top_f:
            lines.append(f"| `{fname}` | {cnt} |")

    # Recomendaciones priorizadas
    recs: list[str] = []
    if score["errors"] > 0:
        recs.append(f"🔴 Resolver los **{score['errors']} errores** de código (prioridad alta)")
    if score["cfg_errors"] > 0:
        recs.append(f"🔴 Corregir **{score['cfg_errors']} error(es)** en pack.json (`bago config-check --fix`)")
    if score["warnings"] > 5:
        recs.append(f"🟡 Reducir las **{score['warnings']} advertencias** de código")
    if git_info.get("dirty"):
        recs.append("🟡 Hacer commit de los cambios pendientes (`git status`)")
    if score["score"] < 70:
        recs.append("💡 Considera ejecutar `bago autofix` para correcciones automáticas")
    if not recs:
        recs.append("✅ El proyecto está en buen estado — sin acciones críticas")

    lines += [
        "",
        "---",
        "",
        "## 💡 Recomendaciones",
        "",
    ]
    for r in recs:
        lines.append(f"- {r}")

    lines += ["", "---", "*Generado con BAGO Framework — `bago health-report`*", ""]
    return "\n".join(lines)


def generate_html(target: str, lint_data: dict, cfg_data: dict,
                  git_info: dict, title: Optional[str] = None) -> str:
    findings   = lint_data.get("findings", [])
    cfg_issues = cfg_data.get("issues", [])
    score      = _compute_score(findings, cfg_issues)
    now        = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    page_title = title or f"Health Report — {Path(target).resolve().name}"

    # ── Interactive charts (if chart_engine available) ──────────────────
    if _CHARTS_OK:
        gauge_html = render_gauge(score["score"], "Health Score")

        top_rules = _top_rules(findings, 10)
        bar_html  = render_bar(
            [r for r, _ in top_rules],
            [c for _, c in top_rules],
            title="Top Reglas (hallazgos)",
            color="#e74c3c",
            horizontal=True,
            max_width=700,
        ) if top_rules else "<p>Sin hallazgos de código.</p>"

        donut_html = render_doughnut(
            ["Errores", "Advertencias", "Info"],
            [score["errors"], score["warnings"], score["infos"]],
            title="Distribución de severidad",
            colors=["#e74c3c", "#f1c40f", "#3498db"],
        )
        charts_section = f"""
<h2>📊 Dashboard de Salud</h2>
<div style="display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;margin:16px 0;">
  <div style="flex:0 0 280px;">{gauge_html}</div>
  <div style="flex:0 0 340px;">{donut_html}</div>
</div>
<h2>🔍 Top Reglas</h2>
{bar_html}"""
    else:
        score_color = "#27ae60" if score["score"] >= 90 else (
                      "#f1c40f" if score["score"] >= 70 else (
                      "#e67e22" if score["score"] >= 50 else "#e74c3c"))
        charts_section = (
            f'<div style="display:inline-block;padding:16px 32px;border-radius:8px;'
            f'background:{score_color};color:white;font-size:2em;font-weight:bold;margin:16px 0;">'
            f'{score["score"]}/100 — {score["status"]}</div>'
        )

    # ── Findings table ──────────────────────────────────────────────────
    rows = []
    for f in findings[:50]:
        sev = f.get("severity", "info")
        clr = "#c0392b" if sev == "error" else ("#d4ac0d" if "warn" in sev else "#2980b9")
        rows.append(
            f'<tr><td><code>{f.get("file","")}</code></td>'
            f'<td>{f.get("line","")}</td>'
            f'<td><b style="color:{clr}">{sev}</b></td>'
            f'<td><code>{f.get("rule","")}</code></td>'
            f'<td>{f.get("message","")[:80]}</td></tr>'
        )
    table = ""
    if rows:
        table = (
            "<h2>📋 Hallazgos (primeros 50)</h2>"
            "<table><thead><tr><th>Archivo</th><th>Línea</th>"
            "<th>Severidad</th><th>Regla</th><th>Mensaje</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )

    # ── Git info ────────────────────────────────────────────────────────
    git_html = ""
    if git_info:
        dirty_badge = '⚠️ Sí' if git_info.get("dirty") else '✅ No'
        git_html = (
            f'<h2>🔀 Git</h2>'
            f'<table><tbody>'
            f'<tr><th>Rama</th><td><code>{git_info.get("branch","?")}</code></td></tr>'
            f'<tr><th>Último commit</th><td>{git_info.get("commit","?")}</td></tr>'
            f'<tr><th>Cambios sin commit</th><td>{dirty_badge}</td></tr>'
            f'</tbody></table>'
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<style>
:root{{--text-muted:#666;}}
@media(prefers-color-scheme:dark){{body{{background:#1a1a2e;color:#e0e0e0;}}:root{{--text-muted:#aaa;}}}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      max-width:1100px;margin:40px auto;padding:0 20px;background:#f8f9fa;}}
h1{{color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:12px;}}
h2{{color:#34495e;margin-top:32px;}}
table{{border-collapse:collapse;width:100%;margin:16px 0;}}
th{{background:#2c3e50;color:white;padding:8px 12px;text-align:left;}}
td{{padding:6px 12px;border-bottom:1px solid #ddd;}}
tr:nth-child(even){{background:#f2f2f2;}}
code{{background:#ecf0f1;padding:2px 6px;border-radius:3px;font-size:0.9em;}}
</style>
</head>
<body>
<h1>🏥 {page_title}</h1>
<p style="color:var(--text-muted);">Generado por BAGO Framework · {now}</p>
{charts_section}
{git_html}
{table}
<hr>
<small style="color:var(--text-muted);">BAGO Framework — <code>bago health-report</code></small>
</body>
</html>"""


# ─── CLI ───────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    target    = "./"
    fmt       = "md"
    out_file  = None
    do_open   = False
    title     = None

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a == "--title" and i + 1 < len(argv):
            title = argv[i + 1]; i += 2
        elif a == "--open":
            do_open = True; i += 1
        elif not a.startswith("--"):
            target = a; i += 1
        else:
            i += 1

    print(f"{_BLU}Recopilando información del proyecto...{_RST}", file=sys.stderr)

    bago_root = Path(target).resolve()
    lint_data = _run_bago_lint(target)
    cfg_data  = _run_config_check(bago_root)
    git_info  = _get_git_info(target)

    if fmt == "html":
        report = generate_html(target, lint_data, cfg_data, git_info, title)
    else:
        report = generate_markdown(target, lint_data, cfg_data, git_info, title)

    if out_file:
        Path(out_file).write_text(report, encoding="utf-8")
        print(f"{_GRN}✅ Reporte guardado en {out_file}{_RST}", file=sys.stderr)
        if do_open and fmt == "html":
            subprocess.run(["open", out_file])
    else:
        print(report)

    return 0


# ─── Self-tests ────────────────────────────────────────────────────────────

def _self_test() -> None:
    print("Tests de health_report.py...")
    fails: list[str] = []

    def ok(n: str)            : print(f"  OK: {n}")
    def fail(n: str, m: str)  : fails.append(n); print(f"  FAIL: {n}: {m}")

    SAMPLE_FINDINGS = [
        {"file": "a.py", "line": 1, "rule": "BAGO-E001", "severity": "error",   "message": "bare except"},
        {"file": "a.py", "line": 5, "rule": "BAGO-W001", "severity": "warning", "message": "utcnow"},
        {"file": "b.py", "line": 3, "rule": "BAGO-W001", "severity": "warning", "message": "utcnow 2"},
        {"file": "b.py", "line": 9, "rule": "BAGO-I002", "severity": "info",    "message": "TODO"},
    ]
    SAMPLE_CFG = {"issues": [
        {"code": "CFG-E001", "severity": "error",   "message": "missing field: name"},
        {"code": "CFG-W001", "severity": "warning", "message": "deprecated key"},
    ]}

    # T1 — score calculation
    score = _compute_score(SAMPLE_FINDINGS, SAMPLE_CFG["issues"])
    if 0 <= score["score"] <= 100 and score["errors"] == 1:
        ok("health_report:score_calculation")
    else:
        fail("health_report:score_calculation", f"score={score}")

    # T2 — markdown tiene secciones clave
    md = generate_markdown("./", {"findings": SAMPLE_FINDINGS}, SAMPLE_CFG, {})
    if "Score de Salud" in md and "Recomendaciones" in md and "Configuración" in md:
        ok("health_report:markdown_sections")
    else:
        fail("health_report:markdown_sections", "secciones faltantes")

    # T3 — html generado contiene structure básica
    html = generate_html("./", {"findings": SAMPLE_FINDINGS}, SAMPLE_CFG, {})
    if "<!DOCTYPE html>" in html and "Health Report" in html and "Health Score" in html:
        ok("health_report:html_structure")
    else:
        fail("health_report:html_structure", "html incompleto")

    # T4 — sin findings → score alto, sin recomendaciones críticas
    score_ok = _compute_score([], [])
    if score_ok["score"] == 100 and score_ok["status"] == "EXCELENTE":
        ok("health_report:perfect_score")
    else:
        fail("health_report:perfect_score", f"score={score_ok}")

    # T5 — top_rules funciona con vacío
    top = _top_rules([])
    if top == []:
        ok("health_report:top_rules_empty")
    else:
        fail("health_report:top_rules_empty", f"top={top}")

    # T6 — markdown con git_info incluye branch
    md2 = generate_markdown("./", {"findings": []}, {"issues": []},
                             {"branch": "feature/x", "commit": "abc123", "dirty": False})
    if "feature/x" in md2:
        ok("health_report:markdown_git_info")
    else:
        fail("health_report:markdown_git_info", "branch no aparece en md")

    total = 6
    passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
