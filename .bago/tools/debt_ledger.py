#!/usr/bin/env python3
"""
bago debt — Ledger de deuda técnica con impacto comercial.

Cuantifica la deuda técnica en horas de trabajo y coste €:
  - Clasifica hallazgos por cuadrante: Reckless/Prudent × Deliberate/Inadvertent
  - Estima horas para saldar cada hallazgo por tipo
  - Proyecta coste total a tarifa configurable (default €80/hr)
  - Detecta si la deuda crece o decrece entre scans
  - Muestra ROI de cada fix: tiempo/€ recuperado por resolución

Uso:
    bago debt                    → deuda actual del último scan
    bago debt --rate 120         → tarifa horaria personalizada (€)
    bago debt --trend             → comparar vs scan anterior
    bago debt --quadrant reckless → filtrar cuadrante
    bago debt --top 10            → solo top 10 por coste
    bago debt --json              → output JSON
    bago debt --test              → tests integrados
"""
import argparse, json, sys
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

# ─── Debt catalogue ────────────────────────────────────────────────────────────
# (source_prefix, rule_prefix) → (hours_to_fix, quadrant, description)
# Quadrants: RecklessDeliberate | RecklessInadvertent | PrudentDeliberate | PrudentInadvertent
DEBT_CATALOGUE = {
    # Security — always Reckless·Deliberate if unfixed
    ("bandit", "B1"): (2.0,  "RecklessDeliberate",   "Critical security vuln — must fix before deploy"),
    ("bandit", "B2"): (1.5,  "RecklessDeliberate",   "High security vuln — auth/crypto issue"),
    ("bandit", "B3"): (0.75, "RecklessInadvertent",  "Moderate security issue — hardcoded value"),
    ("bandit", "B6"): (1.0,  "RecklessInadvertent",  "Injection risk — input validation missing"),
    # Runtime errors — Reckless·Inadvertent (you didn't mean to leave it broken)
    ("pylint", "E0"): (0.5,  "RecklessInadvertent",  "Runtime error — will crash in production"),
    ("pylint", "E1"): (0.25, "RecklessInadvertent",  "Undefined reference — runtime NameError"),
    ("flake8", "E9"): (0.33, "RecklessInadvertent",  "Syntax/import error — module won't load"),
    ("flake8", "F8"): (0.25, "RecklessInadvertent",  "Undefined/unused name — logic bug risk"),
    ("mypy",   ""  ): (0.33, "PrudentDeliberate",    "Type annotation gap — caught early is cheap"),
    # Maintainability — Prudent·Deliberate (known shortcuts)
    ("pylint", "R0"): (1.0,  "PrudentDeliberate",    "Refactor needed — complexity too high"),
    ("pylint", "R1"): (0.5,  "PrudentDeliberate",    "Refactor hint — simplification available"),
    ("pylint", "C0"): (0.1,  "PrudentInadvertent",   "Convention violation — style inconsistency"),
    ("pylint", "C1"): (0.1,  "PrudentInadvertent",   "Convention violation — naming/format"),
    ("pylint", "W0"): (0.25, "PrudentInadvertent",   "Warning pattern — accidental debt"),
    ("pylint", "W1"): (0.2,  "PrudentInadvertent",   "Warning pattern — deprecated usage"),
    # Style / formatting — Prudent·Inadvertent (low cost, high volume)
    ("flake8", "E1"): (0.05, "PrudentInadvertent",   "Indentation issue — cosmetic debt"),
    ("flake8", "E2"): (0.05, "PrudentInadvertent",   "Whitespace issue — cosmetic debt"),
    ("flake8", "E3"): (0.03, "PrudentInadvertent",   "Blank line issue — trivial to fix"),
    ("flake8", "E5"): (0.05, "PrudentInadvertent",   "Line too long — readability debt"),
    ("flake8", "W2"): (0.03, "PrudentInadvertent",   "Trailing whitespace — autofixable"),
    ("flake8", "W3"): (0.05, "PrudentInadvertent",   "Blank line at EOF — trivial"),
    ("flake8", "W6"): (0.1,  "PrudentDeliberate",    "Deprecated feature — migration needed"),
    # BAGO-specific
    ("bago",   "BAGO-W001"): (0.05, "PrudentInadvertent", "utcnow() deprecation — autofixable in 3 min"),
    ("bago",   "BAGO-I001"): (0.1,  "PrudentInadvertent", "Bare sys.exit — testability debt"),
    # Default
    ("",       ""          ): (0.2,  "PrudentInadvertent", "General code quality issue"),
}

QUADRANT_DESC = {
    "RecklessDeliberate":   ("🔴 Imprudente·Deliberado",  "Sabías que era malo y lo dejaste. Actuar hoy."),
    "RecklessInadvertent":  ("🟠 Imprudente·Inadvertido", "No lo sabías pero es peligroso. Alta prioridad."),
    "PrudentDeliberate":    ("🟡 Prudente·Deliberado",    "Atajo consciente con plan de pago. Cumplir plazo."),
    "PrudentInadvertent":   ("🔵 Prudente·Inadvertido",   "Deuda acumulada sin querer. Amortizar gradual."),
}


def lookup_debt(f: fe.Finding) -> tuple:
    src  = f.source.lower()
    rule = f.rule or ""
    for (s, r), (hrs, quad, desc) in DEBT_CATALOGUE.items():
        if s and r:
            if s in src and rule.startswith(r):
                return hrs, quad, desc
    for (s, r), (hrs, quad, desc) in DEBT_CATALOGUE.items():
        if s and not r:
            if s in src:
                return hrs, quad, desc
    return 0.2, "PrudentInadvertent", "General code quality issue"


class DebtItem:
    __slots__ = ("finding","hours","quadrant","description","cost_eur")
    def __init__(self, f, hours, quadrant, description, rate):
        self.finding     = f
        self.hours       = hours
        self.quadrant    = quadrant
        self.description = description
        self.cost_eur    = round(hours * rate, 2)


def build_debt_items(findings: list, rate: float) -> list:
    items = []
    for f in findings:
        hrs, quad, desc = lookup_debt(f)
        items.append(DebtItem(f, hrs, quad, desc, rate))
    items.sort(key=lambda x: (-x.cost_eur, x.quadrant))
    return items


def aggregate_debt(items: list) -> dict:
    total_hours = sum(i.hours for i in items)
    total_cost  = sum(i.cost_eur for i in items)
    by_quadrant = {}
    for item in items:
        q = item.quadrant
        if q not in by_quadrant:
            by_quadrant[q] = {"count": 0, "hours": 0.0, "cost": 0.0}
        by_quadrant[q]["count"] += 1
        by_quadrant[q]["hours"]  = round(by_quadrant[q]["hours"] + item.hours, 2)
        by_quadrant[q]["cost"]   = round(by_quadrant[q]["cost"]  + item.cost_eur, 2)
    return {
        "total_hours": round(total_hours, 2),
        "total_cost":  round(total_cost, 2),
        "items":       len(items),
        "by_quadrant": by_quadrant,
    }


def render_debt(items: list, agg: dict, scan_id: str, rate: float, top: int):
    print(f"\n  {BOLD}BAGO Debt Ledger{RESET}  — {DIM}{scan_id}{RESET}  "
          f"{DIM}(tarifa: €{rate:.0f}/hr){RESET}\n")

    total_h = agg["total_hours"]
    total_c = agg["total_cost"]
    weeks   = total_h / 40.0
    print(f"  {BOLD}Deuda total:{RESET}  {YELLOW}{total_h:.1f} horas{RESET}  "
          f"({YELLOW}€{total_c:.0f}{RESET})  ≈ {weeks:.1f} semanas·persona\n")

    # By quadrant
    print(f"  {'Cuadrante':<32} {'Items':>6} {'Horas':>8} {'€':>8}")
    print(f"  {'─'*32}  {'─'*5}  {'─'*7}  {'─'*7}")
    for quad in ("RecklessDeliberate","RecklessInadvertent",
                 "PrudentDeliberate","PrudentInadvertent"):
        if quad not in agg["by_quadrant"]: continue
        d    = agg["by_quadrant"][quad]
        icon, _ = QUADRANT_DESC[quad]
        pct  = d["hours"] / max(total_h, 0.01) * 100
        bar  = "█" * min(8, int(pct / 100 * 8))
        print(f"  {icon:<32}  {d['count']:>5}  {d['hours']:>7.1f}  {d['cost']:>7.0f}")

    # Top items
    limit = min(top, len(items))
    print(f"\n  {BOLD}Top {limit} por coste{RESET}\n")
    print(f"  {'€':>7}  {'Hrs':>5}  {'Cuad':<4}  {'Archivo':<30}  {'Descripción'}")
    print(f"  {'─'*6}  {'─'*4}  {'─'*4}  {'─'*29}  {'─'*35}")

    q_short = {
        "RecklessDeliberate":  "🔴RD",
        "RecklessInadvertent": "🟠RI",
        "PrudentDeliberate":   "🟡PD",
        "PrudentInadvertent":  "🔵PI",
    }
    for item in items[:limit]:
        path = "/".join(item.finding.file.split("/")[-2:])
        desc = item.description[:35]
        print(f"  {item.cost_eur:>6.1f}  {item.hours:>4.2f}  "
              f"{q_short.get(item.quadrant,'??'):<4}  {path:<30}  {DIM}{desc}{RESET}")

    # ROI hint
    autofixable = [i for i in items if i.finding.autofixable]
    if autofixable:
        af_hrs  = sum(i.hours for i in autofixable)
        af_cost = sum(i.cost_eur for i in autofixable)
        print(f"\n  {GREEN}⚡ Quick win:{RESET} {len(autofixable)} autofixables = "
              f"{af_hrs:.1f}h / €{af_cost:.0f} recuperables con 'bago fix --apply'\n")


def load_previous_scan() -> tuple:
    """Load second-latest scan for trend comparison. Returns (FindingsDB|None, hours|None)."""
    findings_dir = BAGO_ROOT / "state" / "findings"
    if not findings_dir.exists():
        return None, None
    scans = sorted(findings_dir.glob("SCAN-*.json"))
    if len(scans) < 2:
        return None, None
    try:
        db = fe.FindingsDB.from_file(scans[-2])
        items = build_debt_items(db.findings, 80.0)
        agg   = aggregate_debt(items)
        return db, agg["total_hours"]
    except Exception:
        return None, None


def render_trend(current_hours: float, prev_hours: float, prev_id: str):
    delta = current_hours - prev_hours
    arrow = "▲" if delta > 0 else "▼" if delta < 0 else "─"
    col   = RED if delta > 0 else GREEN if delta < 0 else DIM
    print(f"  {BOLD}Tendencia vs{RESET} {DIM}{prev_id}{RESET}:  "
          f"{col}{arrow} {abs(delta):.1f}h{RESET}  "
          f"({'DEUDA CRECIENDO ⚠️' if delta > 0 else 'DEUDA BAJANDO ✅' if delta < 0 else 'SIN CAMBIO'})\n")


def save_debt_report(agg: dict, scan_id: str) -> Path:
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = REPORTS_DIR / f"DEBT-{ts}.json"
    out.write_text(json.dumps({"report_id": f"DEBT-{ts}", "scan_id": scan_id,
                               "generated_at": datetime.now(timezone.utc).isoformat(),
                               **agg}, indent=2) + "\n")
    return out


def run_tests():
    print("Ejecutando tests de debt_ledger.py...")
    errors = 0
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): nonlocal errors; errors += 1; print(f"  FAIL: {n} — {m}")

    # T1: bandit B1 → RecklessDeliberate, 2h
    f = fe.Finding(id="a",severity="error",file="a.py",line=1,col=0,
                   rule="B101",source="bandit",message="m",fix_suggestion="",autofixable=False)
    hrs, quad, _ = lookup_debt(f)
    if quad == "RecklessDeliberate" and hrs == 2.0:
        ok("debt:bandit_reckless")
    else:
        fail("debt:bandit_reckless", f"quad={quad} hrs={hrs}")

    # T2: flake8 W291 → PrudentInadvertent, low hours
    f2 = fe.Finding(id="b",severity="warning",file="b.py",line=2,col=0,
                    rule="W291",source="flake8",message="m",fix_suggestion="",autofixable=True)
    hrs2, quad2, _ = lookup_debt(f2)
    if quad2 == "PrudentInadvertent" and hrs2 <= 0.1:
        ok("debt:flake8_prudent")
    else:
        fail("debt:flake8_prudent", f"quad={quad2} hrs={hrs2}")

    # T3: build_debt_items sorts by cost desc
    items = build_debt_items([f, f2], 80.0)
    if items[0].cost_eur >= items[1].cost_eur:
        ok("debt:sorted_by_cost")
    else:
        fail("debt:sorted_by_cost", f"{[i.cost_eur for i in items]}")

    # T4: aggregate totals
    agg = aggregate_debt(items)
    if agg["total_hours"] > 0 and agg["items"] == 2:
        ok("debt:aggregate_totals")
    else:
        fail("debt:aggregate_totals", str(agg))

    # T5: autofixable item has cost
    if items[1].finding.autofixable and items[1].cost_eur > 0:
        ok("debt:autofixable_has_cost")
    else:
        fail("debt:autofixable_has_cost", f"cost={items[1].cost_eur}")

    # T6: rate affects cost proportionally
    items_hi = build_debt_items([f], 160.0)
    items_lo = build_debt_items([f], 80.0)
    if abs(items_hi[0].cost_eur - items_lo[0].cost_eur * 2) < 0.01:
        ok("debt:rate_proportional")
    else:
        fail("debt:rate_proportional", f"{items_hi[0].cost_eur} vs {items_lo[0].cost_eur}")

    total = 6; passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors: raise SystemExit(1)


def main():
    p = argparse.ArgumentParser(prog="bago debt")
    p.add_argument("--scan",      default=None)
    p.add_argument("--rate",      type=float, default=80.0, help="€/hr (default 80)")
    p.add_argument("--trend",     action="store_true")
    p.add_argument("--quadrant",  default=None)
    p.add_argument("--top",       type=int, default=15)
    p.add_argument("--json",      action="store_true")
    p.add_argument("--csv",       action="store_true",
                   help="Exporta deuda a CSV (file,severity,hours,cost_eur,quadrant)")
    p.add_argument("--since",     default=None, metavar="DATE",
                   help="Agregar hallazgos de todos los scans desde DATE (YYYY-MM-DD)")
    p.add_argument("--test",      action="store_true")
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
            if args.json:
                print(json.dumps({"total_hours": 0, "total_cost": 0, "items": 0, "by_quadrant": {}}, indent=2))
                return
            print(f"Sin scans desde {since}.")
            raise SystemExit(1)
        findings = merged_findings
        db = latest_db
    else:
        db = fe.FindingsDB.load(args.scan) if args.scan else fe.FindingsDB.latest()
        if db is None:
            if args.json:
                print(json.dumps({"total_hours": 0, "total_cost": 0, "items": 0, "by_quadrant": {}}, indent=2))
                return
            print(f"{RED}✗ Sin scan. Ejecuta 'bago scan' primero.{RESET}")
            raise SystemExit(1)
        findings = db.findings
    if args.quadrant:
        all_items = build_debt_items(findings, args.rate)
        items     = [i for i in all_items if args.quadrant.lower() in i.quadrant.lower()]
    else:
        items = build_debt_items(findings, args.rate)

    agg = aggregate_debt(items)

    if args.json:
        print(json.dumps(agg, indent=2))
        return

    if getattr(args, "csv", False):
        import csv as _csv, io as _io
        top_items = items[:args.top] if args.top else items
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["file", "severity", "hours", "cost_eur", "quadrant"])
        for item in top_items:
            f = item.finding
            w.writerow([
                getattr(f, "file", ""),
                getattr(f, "severity", ""),
                item.hours,
                item.cost_eur,
                item.quadrant,
            ])
        print(buf.getvalue(), end="")
        return

    render_debt(items, agg, db.scan_id, args.rate, args.top)

    if args.trend:
        _, prev_hours = load_previous_scan()
        if prev_hours is not None:
            render_trend(agg["total_hours"], prev_hours, "scan anterior")
        else:
            print(f"  {DIM}Sin scan previo para comparar{RESET}\n")

    out = save_debt_report(agg, db.scan_id)
    print(f"  {DIM}Reporte guardado: {out.name}{RESET}\n")


if __name__ == "__main__":
    main()