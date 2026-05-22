from typing import Optional
#!/usr/bin/env python3
"""
bago contract — Sistema de contratos de estado verificables.

Un contrato define un conjunto de condiciones medibles que el sistema
debe cumplir antes de una fecha límite. Sirve como compromiso auditable
entre el equipo y el framework.

Uso:
    bago contract list              → todos los contratos
    bago contract check             → evalúa todos los activos
    bago contract check CONTRACT-002 → evalúa uno específico
    bago contract status            → resumen visual con countdown
    bago contract --test            → tests integrados
"""
import argparse, json, subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BAGO_ROOT      = Path(__file__).parent.parent
CONTRACTS_DIR  = BAGO_ROOT / "state" / "contracts"
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
TOOLS_DIR      = Path(__file__).parent
CONFIG_FILE    = BAGO_ROOT / "state" / "config" / "contracts_config.json"

BOLD="\033[1m"; DIM="\033[2m"; RESET="\033[0m"
RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"; CYAN="\033[36m"
MAGENTA="\033[35m"


# ─── Checker metadata (loaded from contracts_config.json) ─────────────────────

def _load_checker_metadata() -> dict[str, dict]:
    """Load checker metadata from contracts_config.json.

    Returns a dict keyed by checker type with their description and param schemas.
    Falls back to an empty dict — missing config never breaks contract evaluation.
    """
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {c["type"]: c for c in data.get("checkers", [])}
    except Exception:
        return {}


CHECKER_METADATA: dict[str, dict] = _load_checker_metadata()


def get_checker_default(checker_type: str, param: str):
    """Return the default value for a param from checker metadata, or None."""
    meta = CHECKER_METADATA.get(checker_type, {})
    return meta.get("params", {}).get(param, {}).get("default")


# ─── Condition checkers ───────────────────────────────────────────────────────

def check_test_count(params: dict) -> tuple:
    """Run bago test and verify passing count >= min."""
    min_pass = params.get("min", get_checker_default("test_count", "min") or 1)
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "integration_tests.py")],
            capture_output=True, text=True, timeout=120
        )
        import re
        m = re.search(r"Resultado:\s*(\d+)/(\d+) passed\s+(\d+) failed", r.stdout)
        if m:
            passed = int(m.group(1)); failed = int(m.group(3))
            ok = passed >= min_pass and failed == 0
            return ok, f"{passed} passed, {failed} failed (requiere ≥{min_pass})"
        return False, f"no se pudo parsear output: {r.stdout[-100:]}"
    except Exception as e:
        return False, str(e)


def check_file_exists(params: dict) -> tuple:
    """Verify one or more files exist."""
    files   = params.get("files", [])
    missing = [f for f in files if not Path(f).exists()]
    ok      = len(missing) == 0
    return ok, ("todos existen" if ok else f"faltantes: {missing}")


def check_health_score(params: dict) -> tuple:
    """Run bago health and verify score >= min."""
    min_score = params.get("min", get_checker_default("health_score", "min") or 90)
    try:
        r = subprocess.run(
            [sys.executable, "bago", "health"],
            capture_output=True, text=True, cwd=str(BAGO_ROOT.parent), timeout=30
        )
        import re
        m = re.search(r"(\d+)/100", r.stdout)
        if m:
            score = int(m.group(1))
            return score >= min_score, f"health={score}/100 (requiere ≥{min_score})"
        return False, "no se pudo parsear score"
    except Exception as e:
        return False, str(e)


def check_validate_go(params: dict) -> tuple:
    """Run bago validate and verify GO."""
    try:
        r = subprocess.run(
            [sys.executable, "bago", "validate"],
            capture_output=True, text=True, cwd=str(BAGO_ROOT.parent), timeout=30
        )
        ok = "GO" in r.stdout and "KO" not in r.stdout
        snippet = r.stdout[:80].strip()
        return ok, snippet
    except Exception as e:
        return False, str(e)


def check_tools_count(params: dict) -> tuple:
    """Verify number of .py tools >= min."""
    min_count = params.get("min", get_checker_default("tools_count", "min") or 80)
    count     = len(list(TOOLS_DIR.glob("*.py")))
    return count >= min_count, f"{count} tools (requiere ≥{min_count})"


def check_routing_count(params: dict) -> tuple:
    """Verify bago COMMANDS covers unique, resolvable tool entries (quality, not quantity).

    Prefers importing from tool_registry.py (single source of truth).
    Falls back to AST-parsing the bago script if tool_registry is unavailable.
    """
    min_count = params.get("min", get_checker_default("routing_count", "min") or 10)

    # ── Primary: load from tool_registry (single source of truth) ────────────
    import importlib.util as _ilu
    reg_file = TOOLS_DIR / "tool_registry.py"
    if reg_file.exists():
        spec = _ilu.spec_from_file_location("_contracts_registry", str(reg_file))
        if spec:
            mod = _ilu.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                cmd_names = mod.get_cmd_names() if hasattr(mod, "get_cmd_names") else list(getattr(mod, "REGISTRY", {}).keys())
                seen = set(cmd_names)
                dupes = [c for c in cmd_names if cmd_names.count(c) > 1]
                if dupes:
                    return False, f"comandos duplicados en tool_registry: {dupes}"
                ok = len(seen) >= min_count
                return ok, f"{len(seen)} comandos únicos en tool_registry (requiere ≥{min_count})"
            except Exception:
                pass  # fall through to AST fallback

    # ── Fallback: AST-parse bago script ──────────────────────────────────────
    import ast as _ast
    bago_script = BAGO_ROOT.parent / "bago"
    if not bago_script.exists():
        return False, "script bago no encontrado y tool_registry.py no disponible"
    try:
        tree = _ast.parse(bago_script.read_text())
    except SyntaxError as e:
        return False, f"bago script no parseable: {e}"

    commands: list[str] = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign):
            for target in node.targets:
                if isinstance(target, _ast.Name) and target.id in ("COMMANDS", "COMMANDS_MAIN", "COMMANDS_ADVANCED"):
                    if isinstance(node.value, _ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, _ast.Constant) and isinstance(k.value, str):
                                commands.append(k.value)

    if not commands:
        text = bago_script.read_text()
        count = text.count('elif cmd ==')
        if count < min_count:
            return False, f"solo {count} rutas elif (requiere ≥{min_count})"
        return True, f"{count} rutas elif (legacy; migrar a tool_registry)"

    seen: set[str] = set()
    duplicates: list[str] = []
    for cmd in commands:
        if cmd in seen:
            duplicates.append(cmd)
        seen.add(cmd)

    if duplicates:
        return False, f"comandos duplicados en COMMANDS: {duplicates}"

    ok = len(seen) >= min_count
    return ok, f"{len(seen)} comandos únicos registrados en bago (requiere ≥{min_count})"


def check_file_not_contains(params: dict) -> tuple:
    """Verify no file in a glob contains a forbidden pattern."""
    glob_pat = params.get("glob", ".bago/tools/*.py")
    pattern  = params.get("pattern", "utcnow()")
    files    = list(BAGO_ROOT.parent.glob(glob_pat))
    hits     = []
    for f in files:
        try:
            if pattern in f.read_text():
                hits.append(f.name)
        except Exception:
            pass
    ok = len(hits) == 0
    return ok, (f"✅ sin '{pattern}'" if ok else f"aún contiene '{pattern}': {hits}")


def check_snapshot_exists(params: dict) -> tuple:
    """Verify at least one snapshot was taken after a given date."""
    since = params.get("since", "")
    snaps_dir = BAGO_ROOT / "state" / "snapshots"
    snaps = list(snaps_dir.glob("SNAP-*.json")) + list(snaps_dir.glob("SNAP-*.zip"))
    if not snaps:
        return False, "sin snapshots"
    latest = max(snaps, key=lambda p: p.stat().st_mtime)
    if since:
        try:
            cutoff = datetime.fromisoformat(since.rstrip("Z")).replace(tzinfo=timezone.utc)
            mtime  = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
            return mtime >= cutoff, f"último: {latest.name} ({mtime.strftime('%H:%M')})"
        except Exception as e:
            return False, str(e)
    return True, f"último: {latest.name}"


def check_sprint_open(params: dict) -> tuple:
    """Verify at least one sprint with status open exists."""
    sprints_dir = BAGO_ROOT / "state" / "sprints"
    if not sprints_dir.exists():
        return False, "sin directorio sprints"
    for f in sprints_dir.glob("SPRINT-*.json"):
        try:
            d = json.loads(f.read_text())
            if d.get("status") in ("open", "active", "OPEN", "ACTIVE"):
                return True, f"{d.get('sprint_id', f.stem)} activo"
        except Exception:
            pass
    return False, "ningún sprint abierto"


def check_chg_count(params: dict) -> tuple:
    """Verify number of CHG files >= min."""
    min_count = params.get("min", get_checker_default("chg_count", "min") or 77)
    changes_dir = BAGO_ROOT / "state" / "changes"
    count = len(list(changes_dir.glob("*.json")))
    return count >= min_count, f"{count} CHG registrados (requiere ≥{min_count})"


CHECKERS = {
    "test_count":         check_test_count,
    "file_exists":        check_file_exists,
    "health_score":       check_health_score,
    "validate_go":        check_validate_go,
    "tools_count":        check_tools_count,
    "routing_count":      check_routing_count,
    "file_not_contains":  check_file_not_contains,
    "snapshot_exists":    check_snapshot_exists,
    "sprint_open":        check_sprint_open,
    "chg_count":          check_chg_count,
}


# ─── Core logic ───────────────────────────────────────────────────────────────

def load_contract(path: Path) -> dict:
    return json.loads(path.read_text())


def load_all_contracts() -> list:
    return sorted(
        [load_contract(p) for p in CONTRACTS_DIR.glob("CONTRACT-*.json")],
        key=lambda c: c["contract_id"]
    )


def evaluate_contract(contract: dict) -> dict:
    results = []
    for cond in contract.get("conditions", []):
        checker = CHECKERS.get(cond["type"])
        if checker is None:
            known = list(CHECKER_METADATA.keys()) or list(CHECKERS.keys())
            hint  = f" Tipos disponibles: {known}" if known else ""
            results.append({**cond, "passed": False,
                             "detail": f"checker '{cond['type']}' no encontrado.{hint}"})
            continue
        try:
            passed, detail = checker(cond.get("params", {}))
        except Exception as e:
            passed, detail = False, str(e)
        results.append({**cond, "passed": passed, "detail": detail})

    total    = len(results)
    passed   = sum(1 for r in results if r["passed"])
    critical = [r for r in results if r.get("critical") and not r["passed"]]

    deadline_str = contract.get("deadline")
    now          = datetime.now(timezone.utc)
    time_left    = None
    overdue      = False
    if deadline_str:
        try:
            deadline  = datetime.fromisoformat(deadline_str.rstrip("Z")).replace(tzinfo=timezone.utc)
            delta     = deadline - now
            time_left = delta
            overdue   = delta.total_seconds() < 0
        except Exception:
            pass

    fulfilled = passed == total
    status    = (
        "BASELINE"  if contract.get("type") == "baseline" else
        "FULFILLED" if fulfilled else
        "VIOLATED"  if (overdue and not fulfilled) else
        "BREACHING" if not fulfilled else
        "ACTIVE"
    )

    return {
        "contract_id": contract["contract_id"],
        "title":       contract["title"],
        "status":      status,
        "passed":      passed,
        "total":       total,
        "critical_failures": critical,
        "time_left":   time_left,
        "overdue":     overdue,
        "results":     results,
    }


def countdown_str(delta: timedelta) -> str:
    if delta is None: return "—"
    total_secs = int(abs(delta.total_seconds()))
    h = total_secs // 3600; m = (total_secs % 3600) // 60
    sign = "-" if delta.total_seconds() < 0 else ""
    return f"{sign}{h}h {m:02d}m"


# ─── Rendering ────────────────────────────────────────────────────────────────

STATUS_ICONS = {
    "BASELINE":  f"{DIM}⬜ BASELINE{RESET}",
    "FULFILLED": f"{GREEN}✅ CUMPLIDO{RESET}",
    "ACTIVE":    f"{CYAN}🔵 ACTIVO{RESET}",
    "BREACHING": f"{YELLOW}🟡 INCUMPLIENDO{RESET}",
    "VIOLATED":  f"{RED}❌ VIOLADO{RESET}",
}


def render_contract(ev: dict, verbose: bool = False):
    icon  = STATUS_ICONS.get(ev["status"], ev["status"])
    pct   = ev["passed"] / max(ev["total"], 1) * 100
    bar   = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))

    tl    = ev["time_left"]
    tl_s  = countdown_str(tl) if tl else "—"
    tl_col = RED if ev["overdue"] else (YELLOW if tl and tl.total_seconds() < 3600 else GREEN)

    print(f"\n  {BOLD}{ev['contract_id']}{RESET}  {icon}")
    print(f"  {ev['title']}")
    print(f"  Progreso: [{bar}] {ev['passed']}/{ev['total']}  "
          f"Countdown: {tl_col}{tl_s}{RESET}")

    if verbose or ev["status"] in ("ACTIVE", "BREACHING", "VIOLATED"):
        for r in ev["results"]:
            sym = f"{GREEN}✓{RESET}" if r["passed"] else f"{RED}✗{RESET}"
            crit = f" {RED}[CRÍTICO]{RESET}" if r.get("critical") and not r["passed"] else ""
            print(f"    {sym} {r['description']}{crit}")
            if not r["passed"]:
                print(f"       {DIM}→ {r['detail']}{RESET}")


def cmd_list():
    contracts = load_all_contracts()
    if not contracts:
        print(f"\n  {DIM}Sin contratos. Directorio: {CONTRACTS_DIR}{RESET}\n")
        return
    print(f"\n  {BOLD}Contratos BAGO{RESET}  ({len(contracts)} total)\n")
    for c in contracts:
        ev   = evaluate_contract(c)
        icon = STATUS_ICONS.get(ev["status"], ev["status"])
        tl   = countdown_str(ev["time_left"]) if ev["time_left"] else "—"
        print(f"  {ev['contract_id']:<20} {icon:<28} {ev['passed']}/{ev['total']} cond.  ⏱ {tl}")
    print()


def cmd_check(contract_id: Optional[str], verbose: bool):
    contracts = load_all_contracts()
    if not contracts:
        print(f"\n  {RED}Sin contratos.{RESET}\n"); return

    to_check = ([c for c in contracts if c["contract_id"] == contract_id]
                if contract_id else
                [c for c in contracts if c.get("type") != "baseline"])

    if not to_check:
        print(f"\n  {RED}Contrato '{contract_id}' no encontrado.{RESET}\n"); return

    print(f"\n  {BOLD}BAGO Contract Check{RESET}\n")
    all_ok = True
    for contract in to_check:
        ev = evaluate_contract(contract)
        render_contract(ev, verbose=verbose)
        if ev["status"] in ("VIOLATED", "BREACHING"):
            all_ok = False

    print(f"\n  {'═'*50}")
    if all_ok:
        print(f"  {GREEN}{BOLD}✅ TODOS LOS CONTRATOS EN CURSO{RESET}\n")
    else:
        print(f"  {RED}{BOLD}❌ CONTRATOS VIOLADOS O INCUMPLIENDO — REQUIEREN ATENCIÓN{RESET}\n")
        raise SystemExit(1)


def cmd_status():
    contracts = load_all_contracts()
    if not contracts:
        print(f"\n  {DIM}Sin contratos.{RESET}\n"); return

    print(f"\n  {BOLD}Estado de Contratos{RESET}\n")
    for c in contracts:
        ev = evaluate_contract(c)
        render_contract(ev, verbose=False)
    print()


# ─── Tests ────────────────────────────────────────────────────────────────────

def run_tests():
    print("Ejecutando tests de contracts.py...")
    errors = 0
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): nonlocal errors; errors += 1; print(f"  FAIL: {n} — {m}")

    # T1: check_tools_count passes current state
    passed, detail = check_tools_count({"min": 30})
    if passed:
        ok("contract:tools_count_pass")
    else:
        fail("contract:tools_count_pass", detail)

    # T2: check_tools_count fails impossible threshold
    passed2, _ = check_tools_count({"min": 99999})
    if not passed2:
        ok("contract:tools_count_fail")
    else:
        fail("contract:tools_count_fail", "debería fallar con min=99999")

    # T3: check_file_exists with real file
    p, d = check_file_exists({"files": [str(TOOLS_DIR / "health_score.py")]})
    if p:
        ok("contract:file_exists_real")
    else:
        fail("contract:file_exists_real", d)

    # T4: check_file_exists with fake file
    p2, d2 = check_file_exists({"files": ["/nonexistent/file.py"]})
    if not p2:
        ok("contract:file_exists_fake")
    else:
        fail("contract:file_exists_fake", "debería fallar")

    # T5: evaluate_contract structure — BREACHING when conditions fail but not overdue
    fake = {
        "contract_id": "TEST-001", "title": "test", "type": "test",
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "conditions": [
            {"id": "T1","description":"tools","type":"tools_count","params":{"min":1},"critical":True}
        ]
    }
    ev = evaluate_contract(fake)
    if ev["passed"] == 1 and ev["total"] == 1 and ev["status"] in ("ACTIVE","FULFILLED"):
        ok("contract:evaluate_structure")
    else:
        fail("contract:evaluate_structure", str(ev))

    # T5b: BREACHING when condition fails and not overdue
    fake_breach = {
        "contract_id": "TEST-002", "title": "breach test", "type": "test",
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "conditions": [
            {"id": "B1","description":"impossible","type":"tools_count","params":{"min":99999},"critical":True}
        ]
    }
    ev_breach = evaluate_contract(fake_breach)
    if ev_breach["status"] == "BREACHING":
        ok("contract:breaching_state")
    else:
        fail("contract:breaching_state", f"expected BREACHING got {ev_breach['status']}")

    # T6: countdown_str formatting
    cs = countdown_str(timedelta(hours=1, minutes=30))
    if "1h" in cs and "30" in cs:
        ok("contract:countdown_str")
    else:
        fail("contract:countdown_str", cs)

    total = 7; passed_n = total - errors
    print(f"\n  {passed_n}/{total} tests pasaron")
    if errors: raise SystemExit(1)


def cmd_checkers():
    """List available checker types loaded from contracts_config.json."""
    if not CHECKER_METADATA:
        print("  (contracts_config.json no cargado — usando solo CHECKERS de Python)")
        for t in sorted(CHECKERS.keys()):
            print(f"    {CYAN}{t}{RESET}")
        return
    print(f"\n  {BOLD}Checker types disponibles ({len(CHECKER_METADATA)}){RESET}")
    print(f"  {DIM}Fuente: {CONFIG_FILE}{RESET}\n")
    for t, meta in sorted(CHECKER_METADATA.items()):
        params = meta.get("params", {})
        param_str = ", ".join(
            f"{k}={v.get('default','?')}" for k, v in params.items()
        ) if params else "—"
        in_py = "✅" if t in CHECKERS else "⚠️ "
        print(f"  {in_py} {CYAN}{t}{RESET}")
        print(f"     {meta.get('description', '')}")
        if params:
            print(f"     {DIM}params: {param_str}{RESET}")
    print()


def main():
    p = argparse.ArgumentParser(prog="bago contract")
    p.add_argument("subcmd", nargs="?", default="status",
                   choices=["list","check","status","checkers"])
    p.add_argument("contract_id", nargs="?", default=None)
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    if args.test:
        run_tests(); return

    if args.subcmd == "list":
        cmd_list()
    elif args.subcmd == "check":
        cmd_check(args.contract_id, args.verbose)
    elif args.subcmd == "checkers":
        cmd_checkers()
    else:
        cmd_status()


if __name__ == "__main__":
    main()