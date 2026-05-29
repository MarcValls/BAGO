#!/usr/bin/env python3
"""goal_validator.py — Centinela de Sinceridad BAGO

Valida que un objetivo declarado realmente se ha cumplido.
NO acepta falsos OK. Si no puede verificar, dice UNKNOWN.

Uso:
    python3 bago validate-goal <goal_id>
    python3 bago validate-goal --last
    python3 bago validate-goal --json

Reglas:
1. Todo objetivo debe tener criterios de aceptación medibles
2. Si un criterio falla, el objetivo entero es KO
3. Si no hay evidencia, el estado es UNKNOWN (no OK)
4. El validador nunca inventa evidencia
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_BAGO_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = _BAGO_ROOT / ".bago" / "state"
_GOALS_FILE = _STATE_DIR / "goals_log.jsonl"
_REPORTS_DIR = _STATE_DIR / "reports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_goals() -> list[dict]:
    goals = []
    if _GOALS_FILE.exists():
        for line in _GOALS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    goals.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return goals


def _save_goal(goal: dict) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_GOALS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(goal, ensure_ascii=False) + "\n")


def _run_checks(checks: list[dict]) -> tuple[str, list[dict]]:
    """Ejecuta cada check y devuelve estado global + detalles."""
    results = []
    overall = "GO"
    for check in checks:
        name = check.get("name", "unnamed")
        check_type = check.get("type", "unknown")
        expected = check.get("expected")
        actual = None
        status = "UNKNOWN"
        detail = ""

        if check_type == "file_exists":
            path = Path(check.get("path", ""))
            actual = str(path.resolve()) if path.exists() else None
            status = "GO" if path.exists() else "KO"
            if status == "KO":
                detail = f"Falta archivo: {path}"

        elif check_type == "string_in_file":
            path = Path(check.get("path", ""))
            needle = check.get("string", "")
            if not path.exists():
                status = "KO"
                detail = f"Falta archivo: {path}"
            else:
                content = path.read_text(encoding="utf-8")
                found = needle in content
                actual = f"found={found}"
                status = "GO" if found else "KO"
                if status == "KO":
                    detail = f"No se encontró '{needle}' en {path}"

        elif check_type == "test_pass":
            import subprocess
            cmd = check.get("command", [])
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=check.get("timeout", 30),
                    encoding="utf-8", errors="replace",
                )
                actual = f"rc={result.returncode}"
                status = "GO" if result.returncode == 0 else "KO"
                if status == "KO":
                    detail = result.stdout[:200] + result.stderr[:200]
            except Exception as exc:
                status = "KO"
                detail = str(exc)

        elif check_type == "command_output":
            import subprocess
            cmd = check.get("command", [])
            expected_substring = check.get("expected_output", "")
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=check.get("timeout", 30),
                    encoding="utf-8", errors="replace",
                )
                combined = result.stdout + result.stderr
                actual = combined[:200]
                status = "GO" if expected_substring in combined else "KO"
                if status == "KO":
                    detail = f"No se encontró '{expected_substring}' en la salida"
            except Exception as exc:
                status = "KO"
                detail = str(exc)

        elif check_type == "no_file_contains":
            path = Path(check.get("path", ""))
            forbidden = check.get("forbidden", "")
            if not path.exists():
                status = "UNKNOWN"
                detail = f"No se puede verificar: {path} no existe"
            else:
                content = path.read_text(encoding="utf-8")
                found = forbidden in content
                actual = f"found={found}"
                status = "GO" if not found else "KO"
                if status == "KO":
                    detail = f"'{forbidden}' sigue presente en {path}"

        else:
            status = "UNKNOWN"
            detail = f"Tipo de check desconocido: {check_type}"

        results.append({
            "name": name,
            "type": check_type,
            "status": status,
            "expected": expected,
            "actual": actual,
            "detail": detail,
        })

        if status == "KO":
            overall = "KO"
        elif status == "UNKNOWN" and overall == "GO":
            overall = "UNKNOWN"

    return overall, results


def validate_goal(goal_id: str | None, json_mode: bool = False) -> dict:
    """Valida un objetivo específico o el último."""
    goals = _load_goals()
    if not goals:
        return {"status": "UNKNOWN", "reason": "No hay objetivos registrados"}

    if goal_id is None:
        goal = goals[-1]
    else:
        goal = next((g for g in goals if g.get("id") == goal_id), None)
        if goal is None:
            return {"status": "UNKNOWN", "reason": f"Objetivo '{goal_id}' no encontrado"}

    checks = goal.get("checks", [])
    if not checks:
        return {
            "status": "UNKNOWN",
            "goal_id": goal.get("id"),
            "reason": "El objetivo no tiene checks de verificación",
        }

    overall, results = _run_checks(checks)

    report = {
        "status": overall,
        "goal_id": goal.get("id"),
        "goal_description": goal.get("description", ""),
        "timestamp": _now(),
        "checks_total": len(results),
        "checks_go": sum(1 for r in results if r["status"] == "GO"),
        "checks_ko": sum(1 for r in results if r["status"] == "KO"),
        "checks_unknown": sum(1 for r in results if r["status"] == "UNKNOWN"),
        "details": results,
    }

    # Persistir reporte
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _REPORTS_DIR / f"goal_validation_{goal.get('id', 'unknown')}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)

    return report


def _print_report(report: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"  BAGO Goal Validator")
    print(f"{'=' * 60}")
    print(f"  Objetivo: {report['goal_id']}")
    print(f"  Descripción: {report['goal_description'][:60]}")
    print(f"  Estado: {report['status']}")
    print(f"  Checks: {report['checks_go']} GO / {report['checks_ko']} KO / {report['checks_unknown']} UNKNOWN")
    print(f"{'=' * 60}")
    for detail in report["details"]:
        icon = "  [OK]" if detail["status"] == "GO" else "  [KO]" if detail["status"] == "KO" else "  [?]"
        print(f"{icon} {detail['name']} ({detail['type']})")
        if detail.get("detail"):
            print(f"       {detail['detail'][:80]}")
    print(f"{'=' * 60}")
    print(f"  Reporte guardado: .bago/state/reports/goal_validation_{report['goal_id']}.json")


def add_goal(description: str, checks: list[dict]) -> dict:
    """Registra un nuevo objetivo con checks de verificación."""
    goal = {
        "id": f"G_{_now().replace(':', '-').replace('.', '_')}",
        "description": description,
        "created_at": _now(),
        "checks": checks,
    }
    _save_goal(goal)
    return goal


def main() -> None:
    p = argparse.ArgumentParser(description="BAGO Goal Validator — Centinela de Sinceridad")
    p.add_argument("goal_id", nargs="?", help="ID del objetivo a validar")
    p.add_argument("--last", action="store_true", help="Validar el último objetivo")
    p.add_argument("--json", action="store_true", help="Salida JSON")
    p.add_argument("--add", nargs=2, metavar=("DESC", "CHECKS_JSON"), help="Añadir objetivo (checks como JSON)")
    args = p.parse_args()

    if args.add:
        desc, checks_json = args.add
        checks = json.loads(checks_json)
        goal = add_goal(desc, checks)
        print(f"Objetivo registrado: {goal['id']}")
        return

    goal_id = None if args.last else args.goal_id
    report = validate_goal(goal_id, json_mode=args.json)
    sys.exit(0 if report["status"] == "GO" else 1 if report["status"] == "KO" else 2)




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
    main()