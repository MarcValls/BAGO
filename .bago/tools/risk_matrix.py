#!/usr/bin/env python3
"""
bago risk — Matriz de riesgo oculto.

Convierte hallazgos de código en riesgo de negocio cuantificado:
  - Categorías: Security | Reliability | Maintainability | VelocityDrag
  - Dimensiones: Probabilidad × Impacto → Exposición
  - Consecuencias en lenguaje comercial (tiempo perdido, coste de incidente)

Uso:
    bago risk                    → matriz de riesgo del último scan
    bago risk --scan SCAN-ID     → scan específico
    bago risk --category security → solo una categoría
    bago risk --json             → output JSON estructurado
    bago risk --test             → tests integrados
"""
import argparse, json, sys, math
from pathlib import Path
from datetime import datetime, timezone

TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))
import findings_engine as fe

BAGO_ROOT   = Path(__file__).parent.parent
REPORTS_DIR = BAGO_ROOT / "state" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

BOLD="\033[1m"; DIM="\033[2m"; RESET="\033[0m"
RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"; CYAN="\033[36m"; MAGENTA="\033[35m"

# ─── Risk taxonomy ─────────────────────────────────────────────────────────────
# Maps (source, rule_prefix) → (category, base_probability, base_impact, business_consequence)
RISK_TAXONOMY = {
    # Security
    ("bandit", "B1"): ("Security",       0.8, 9, "Breach risk / data exposure / compliance fine"),
    ("bandit", "B2"): ("Security",       0.6, 7, "Credential leak / privilege escalation"),
    ("bandit", "B3"): ("Security",       0.5, 6, "Injection vulnerability / code execution"),
    ("bandit", ""  ): ("Security",       0.5, 6, "Security vulnerability"),
    # Reliability
    ("pylint", "E" ): ("Reliability",    0.9, 8, "Runtime crash / production incident"),
    ("flake8", "E9"): ("Reliability",    0.9, 8, "Syntax error / import failure"),
    ("flake8", "F8"): ("Reliability",    0.7, 6, "Undefined name / broken reference"),
    ("mypy",   ""  ): ("Reliability",    0.7, 7, "Type mismatch → silent data corruption"),
    # Maintainability / debt
    ("pylint", "C" ): ("Maintainability",0.3, 3, "Code clarity loss → slower feature delivery"),
    ("pylint", "R" ): ("Maintainability",0.4, 4, "Refactor needed → review time increase"),
    ("pylint", "W" ): ("Maintainability",0.5, 4, "Bad pattern → regression risk"),
    ("flake8", "E3"): ("Maintainability",0.2, 2, "Style debt → cognitive load"),
    ("flake8", "W" ): ("Maintainability",0.3, 3, "Warning pattern → future bug surface"),
    # Velocity drag
    ("bago",   "BAGO-W001"): ("VelocityDrag", 0.6, 5, "Deprecated API → migration cost at Python upgrade"),
    ("bago",   "BAGO-I001"): ("VelocityDrag", 0.4, 3, "Bare exit → testing difficulty / CI fragility"),
    ("bago",   ""         ): ("VelocityDrag", 0.4, 3, "BAGO governance gap → audit effort"),
    # Default
    ("",       ""          ): ("Maintainability",0.3, 3, "Code quality issue"),
}

CATEGORY_COLORS = {
    "Security":       RED,
    "Reliability":    MAGENTA,
    "Maintainability":YELLOW,
    "VelocityDrag":   CYAN,
}

CATEGORY_ICONS = {
    "Security":        "🔴",
    "Reliability":     "🟠",
    "Maintainability": "🟡",
    "VelocityDrag":    "🔵",
}


def classify_finding(f: fe.Finding) -> tuple:
    """Returns (category, probability, impact, consequence)."""
    src   = f.source.lower()
    rule  = f.rule or ""
    # Try most specific match first
    for (s, r), (cat, prob, imp, cons) in RISK_TAXONOMY.items():
        if s and r:
            if s in src and rule.startswith(r):
                return cat, prob, imp, cons
    for (s, r), (cat, prob, imp, cons) in RISK_TAXONOMY.items():
        if s and not r:
            if s in src:
                return cat, prob, imp, cons
    # severity boost
    sev_boost = {"error": 1.5, "warning": 1.0, "info": 0.7, "hint": 0.5}
    boost     = sev_boost.get(f.severity, 1.0)
    return "Maintainability", 0.3 * boost, 3, "Code quality issue"


def exposure_score(probability: float, impact: float) -> float:
    return round(probability * impact, 2)


def risk_level(score: float) -> str:
    if score >= 6:  return "CRÍTICO"
    if score >= 4:  return "ALTO"
    if score >= 2:  return "MEDIO"
    return "BAJO"


def risk_color(level: str) -> str:
    return {
        "CRÍTICO": RED,
        "ALTO":    MAGENTA,
        "MEDIO":   YELLOW,
        "BAJO":    DIM,
    }.get(level, RESET)


class RiskItem:
    __slots__ = ("finding", "category", "probability", "impact", "consequence",
                 "exposure", "level")
    def __init__(self, f, cat, prob, imp, cons):
        self.finding      = f
        self.category     = cat
        self.probability  = round(prob, 2)
        self.impact       = imp
        self.consequence  = cons
        self.exposure     = exposure_score(prob, imp)
        self.level        = risk_level(self.exposure)


def build_risk_items(findings: list) -> list:
    items = []
    for f in findings:
        cat, prob, imp, cons = classify_finding(f)
        items.append(RiskItem(f, cat, prob, imp, cons))
    items.sort(key=lambda x: (-x.exposure, x.category))
    return items


def aggregate(items: list) -> dict:
    cats = {}
    total_exposure = 0.0
    for item in items:
        c = item.category
        if c not in cats:
            cats[c] = {"count": 0, "total_exposure": 0.0, "max_exposure": 0.0,
                       "critical": 0, "high": 0}
        cats[c]["count"] += 1
        cats[c]["total_exposure"] = round(cats[c]["total_exposure"] + item.exposure, 2)
        cats[c]["max_exposure"]   = max(cats[c]["max_exposure"], item.exposure)
        if item.level == "CRÍTICO": cats[c]["critical"] += 1
        elif item.level == "ALTO":  cats[c]["high"] += 1
        total_exposure += item.exposure

    return {"by_category": cats, "total_exposure": round(total_exposure, 2),
            "items": len(items)}


def render(items: list, agg: dict, scan_id: str):
    print(f"\n  {BOLD}BAGO Risk Matrix{RESET}  — {DIM}{scan_id}{RESET}\n")

    # Category summary
    print(f"  {'Categoría':<20} {'Hallazgos':>10} {'Exposición':>12} {'Críticos':>9}")
    print(f"  {'─'*20}  {'─'*9}  {'─'*11}  {'─'*8}")
    total_exp = agg["total_exposure"]
    for cat, data in sorted(agg["by_category"].items(),
                            key=lambda kv: -kv[1]["total_exposure"]):
        col  = CATEGORY_COLORS.get(cat, RESET)
        icon = CATEGORY_ICONS.get(cat, "⚪")
        bar  = "█" * min(12, int(data["total_exposure"] / max(total_exp, 1) * 12))
        crit = f"{RED}{data['critical']:>2}{RESET}" if data["critical"] else "  0"
        print(f"  {col}{icon} {cat:<18}{RESET}  {data['count']:>9}  "
              f"{YELLOW}{data['total_exposure']:>9.1f}{RESET}  {crit}")

    print(f"\n  {DIM}Exposición total: {BOLD}{total_exp:.1f}{RESET}  "
          f"({'CRÍTICA' if total_exp >= 100 else 'ALTA' if total_exp >= 50 else 'MEDIA' if total_exp >= 20 else 'BAJA'})\n")

    # Top-10 risks
    top = [i for i in items if i.level in ("CRÍTICO", "ALTO")][:10]
    if top:
        print(f"  {BOLD}Top Riesgos (Crítico/Alto){RESET}\n")
        print(f"  {'Nivel':<9} {'Exp':>5}  {'Archivo':<35} {'Regla':<15} {'Consecuencia'}")
        print(f"  {'─'*9}  {'─'*4}  {'─'*34}  {'─'*14}  {'─'*30}")
        for item in top:
            f    = item.finding
            col  = risk_color(item.level)
            path = f.file.split("/")[-1] if "/" in f.file else f.file
            cons = item.consequence[:35]
            print(f"  {col}{item.level:<9}{RESET}  {item.exposure:>4.1f}  "
                  f"{path:<35}  {(f.rule or '-'):<15}  {DIM}{cons}{RESET}")
        print()

    # Risk matrix (2×2 ASCII)
    print(f"  {BOLD}Matriz Probabilidad × Impacto{RESET}\n")
    quadrants = {"HL": [], "HH": [], "LL": [], "LH": []}
    for item in items:
        ph = "H" if item.probability >= 0.5 else "L"
        ih = "H" if item.impact >= 5 else "L"
        quadrants[ph+ih].append(item)

    hh = len(quadrants["HH"]); hl = len(quadrants["HL"])
    lh = len(quadrants["LH"]); ll = len(quadrants["LL"])
    print(f"  Alta  │ {YELLOW}{hl:>3} Monitor{RESET}  │ {RED}{hh:>3} Actuar YA{RESET}  │")
    print(f"  Prob. │{' '*12}│{' '*12}│")
    print(f"  Baja  │ {GREEN}{ll:>3} Aceptar{RESET}   │ {CYAN}{lh:>3} Planificar{RESET}│")
    print(f"  ──────┼──────────────┼──────────────┤")
    print(f"        │  Bajo impacto │  Alto impacto│\n")


def save_report(items: list, agg: dict, scan_id: str) -> Path:
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out  = REPORTS_DIR / f"RISK-{ts}.json"
    data = {
        "report_id": f"RISK-{ts}",
        "scan_id":   scan_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary":   agg,
        "items": [
            {"file": i.finding.file, "line": i.finding.line,
             "rule": i.finding.rule, "source": i.finding.source,
             "severity": i.finding.severity, "category": i.category,
             "probability": i.probability, "impact": i.impact,
             "exposure": i.exposure, "level": i.level,
             "consequence": i.consequence}
            for i in items
        ],
    }
    out.write_text(json.dumps(data, indent=2) + "\n")
    return out


def cmd_risk(scan_id, category_filter, as_json, as_csv=False, top=None):
    db = fe.FindingsDB.load(scan_id) if scan_id else fe.FindingsDB.latest()
    if db is None:
        print(f"{RED}✗ Sin scan disponible. Ejecuta 'bago scan' primero.{RESET}")
        raise SystemExit(1)

    findings = db.findings
    if category_filter:
        items = build_risk_items(findings)
        items = [i for i in items if i.category.lower() == category_filter.lower()]
    else:
        items = build_risk_items(findings)

    if top is not None:
        items = items[:top]

    agg = aggregate(items)

    if as_json:
        print(json.dumps(agg, indent=2))
        return

    if as_csv:
        import csv as _csv, io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["file", "category", "probability", "impact", "exposure", "level"])
        for item in items:
            w.writerow([
                getattr(item.finding, "file", ""),
                item.category,
                item.probability,
                item.impact,
                item.exposure,
                item.level,
            ])
        print(buf.getvalue(), end="")
        return

    render(items, agg, db.scan_id)
    out = save_report(items, agg, db.scan_id)
    print(f"  {DIM}Reporte guardado: {out.name}{RESET}\n")


def run_tests():
    print("Ejecutando tests de risk_matrix.py...")
    errors = 0
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): nonlocal errors; errors += 1; print(f"  FAIL: {n} — {m}")

    # T1: classify bandit finding → Security
    f = fe.Finding(id="x",severity="error",file="a.py",line=1,col=0,
                   rule="B105",source="bandit",message="m",fix_suggestion="",autofixable=False)
    cat, prob, imp, cons = classify_finding(f)
    if cat == "Security" and prob > 0.5:
        ok("risk:classify_bandit_security")
    else:
        fail("risk:classify_bandit_security", f"cat={cat} prob={prob}")

    # T2: classify pylint E → Reliability
    f2 = fe.Finding(id="y",severity="error",file="b.py",line=2,col=0,
                    rule="E0001",source="pylint",message="m",fix_suggestion="",autofixable=False)
    cat2, _, imp2, _ = classify_finding(f2)
    if cat2 == "Reliability" and imp2 >= 7:
        ok("risk:classify_pylint_reliability")
    else:
        fail("risk:classify_pylint_reliability", f"cat={cat2} imp={imp2}")

    # T3: exposure_score
    if exposure_score(0.8, 9) == 7.2:
        ok("risk:exposure_score")
    else:
        fail("risk:exposure_score", str(exposure_score(0.8, 9)))

    # T4: risk_level thresholds
    if (risk_level(7.2) == "CRÍTICO" and risk_level(4.5) == "ALTO"
            and risk_level(2.5) == "MEDIO" and risk_level(1.0) == "BAJO"):
        ok("risk:level_thresholds")
    else:
        fail("risk:level_thresholds", "mismatch")

    # T5: build_risk_items sorts by exposure desc
    findings = [f, f2]
    items    = build_risk_items(findings)
    if len(items) == 2 and items[0].exposure >= items[1].exposure:
        ok("risk:sorted_by_exposure")
    else:
        fail("risk:sorted_by_exposure", f"exp={[i.exposure for i in items]}")

    # T6: aggregate counts categories
    agg = aggregate(items)
    if "by_category" in agg and agg["items"] == 2 and agg["total_exposure"] > 0:
        ok("risk:aggregate_structure")
    else:
        fail("risk:aggregate_structure", str(agg))

    total = 6; passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors: raise SystemExit(1)


def main():
    p = argparse.ArgumentParser(prog="bago risk")
    p.add_argument("--scan",     default=None,  help="ID de scan específico")
    p.add_argument("--category", default=None,  help="Filtrar por categoría")
    p.add_argument("--json",     action="store_true")
    p.add_argument("--csv",      action="store_true",
                   help="Exporta riesgos a CSV (file,category,probability,impact,exposure,level)")
    p.add_argument("--top",      type=int, default=None,
                   help="Limita output a los N riesgos de mayor exposición")
    p.add_argument("--since",    default=None, metavar="DATE",
                   help="Agregar hallazgos de todos los scans desde DATE (YYYY-MM-DD)")
    p.add_argument("--test",     action="store_true")
    args = p.parse_args()

    if args.test:
        run_tests(); return

    since = getattr(args, "since", None)
    if since:
        import datetime as _dt
        try:
            cutoff = _dt.date.fromisoformat(since)
        except ValueError:
            print(f"ERROR: --since fecha inválida '{since}'", file=sys.stderr)
            raise SystemExit(1)
        all_scans = sorted(fe.FINDINGS_DIR.glob("SCAN-*.json"))
        merged_findings = []
        latest_db = None
        for sf in all_scans:
            stem = sf.stem
            try:
                date_part = stem.split("-", 1)[1].split("_")[0]
                scan_date = _dt.date(int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8]))
            except Exception:
                continue
            if scan_date >= cutoff:
                try:
                    d = fe.FindingsDB.load(stem)
                    merged_findings.extend(d.findings)
                    latest_db = d
                except Exception:
                    pass
        if latest_db is None:
            print(f"{RED}✗ Sin scans desde {since}.{RESET}")
            raise SystemExit(1)
        latest_db.findings = merged_findings
        scan_id = args.scan  # still respect --scan override? No — since overrides
        category_filter = args.category
        items = build_risk_items(merged_findings)
        if category_filter:
            items = [i for i in items if i.category.lower() == category_filter.lower()]
        if args.top is not None:
            items = items[:args.top]
        agg = aggregate(items)
        if args.json:
            print(json.dumps(agg, indent=2)); return
        if getattr(args, "csv", False):
            import csv as _csv, io as _io
            buf = _io.StringIO(); w = _csv.writer(buf)
            w.writerow(["file","category","probability","impact","exposure","level"])
            for item in items:
                w.writerow([getattr(item.finding,"file",""), item.category, item.probability,
                            item.impact, item.exposure, item.level])
            print(buf.getvalue(), end=""); return
        render(items, agg, f"since:{since}")
    else:
        cmd_risk(args.scan, args.category, args.json, getattr(args, "csv", False), getattr(args, "top", None))


if __name__ == "__main__":
    main()