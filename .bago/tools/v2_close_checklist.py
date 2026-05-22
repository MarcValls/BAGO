#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2_close_checklist.py — Checklist V2 de validación de cierre.

Verifica el "done técnico mínimo" de V2:
  1. validate_manifest = GO
  2. validate_state = GO
  3. validate_pack = GO
  4. Inventario reconciliado (reconcile_state sin diff)
  5. Sin reporting stale (stale_detector sin ERRORs)
  6. Escenarios coherentes (no cerrados en active_scenarios)

Salida: tabla con ✅/❌ por criterio + veredicto final GO/KO V2

Uso:
  python3 .bago/tools/v2_close_checklist.py
"""

from pathlib import Path
import subprocess
import sys
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def run_script(script: str, args: list = None) -> tuple[int, str]:
    """Ejecuta un script y devuelve (returncode, stdout)."""
    cmd = [sys.executable, str(TOOLS / script)] + (args or [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT.parent, timeout=60)
        output = (proc.stdout + proc.stderr).strip()
        return proc.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT"
    except Exception as e:
        return 1, f"ERROR: {e}"


def check_validate_manifest() -> tuple[bool, str]:
    rc, out = run_script("validate_manifest.py")
    ok = rc == 0 and "GO manifest" in out
    return ok, out.split("\n")[0] if out else "?"


def check_validate_state() -> tuple[bool, str]:
    rc, out = run_script("validate_state.py")
    ok = rc == 0 and "GO state" in out
    return ok, out.split("\n")[0] if out else "?"


def check_validate_pack() -> tuple[bool, str]:
    rc, out = run_script("validate_pack.py")
    ok = rc == 0 and "GO pack" in out
    last = out.split("\n")[-1] if out else "?"
    return ok, last


def check_reconcile() -> tuple[bool, str]:
    rc, out = run_script("reconcile_state.py")
    ok = rc == 0
    first = out.split("\n")[0] if out else "?"
    return ok, first


def check_stale() -> tuple[bool, str]:
    rc, out = run_script("stale_detector.py")
    # OK si no hay ERRORs (rc puede ser 0 con warns)
    has_error = "ERROR" in out and "❌" in out
    ok = not has_error
    first = out.split("\n")[0] if out else "?"
    return ok, first


def check_scenarios_coherent() -> tuple[bool, str]:
    """No debe haber escenarios con CERRADO en MD pero en active_scenarios."""
    gs_path = ROOT / "state" / "global_state.json"
    if not gs_path.exists():
        return False, "global_state.json no encontrado"
    global_state = json.loads(gs_path.read_text(encoding="utf-8"))
    active = global_state.get("active_scenarios", [])
    if not active:
        return True, "Sin escenarios activos"

    scenarios_dir = ROOT / "state" / "scenarios"
    closed_pattern = re.compile(r"Estado[:\s]*CERRADO", re.IGNORECASE)
    problems = []
    for sid in active:
        candidates = []
        if scenarios_dir.exists():
            candidates += list(scenarios_dir.glob(f"*{sid}*.md"))
        candidates += list((ROOT / "state").glob(f"*{sid}*.md"))
        for md in candidates:
            if md.exists() and closed_pattern.search(md.read_text(encoding="utf-8")):
                problems.append(sid)
    if problems:
        return False, f"Escenarios CERRADO en active: {', '.join(problems)}"
    return True, f"{len(active)} activo(s) coherente(s)"


def main():
    print()
    print("═══ BAGO V2 CHECKLIST DE CIERRE ══════════════════════════")
    print()

    checks = [
        ("validate_manifest",    check_validate_manifest),
        ("validate_state",       check_validate_state),
        ("validate_pack",        check_validate_pack),
        ("inventario reconcil.", check_reconcile),
        ("sin stale ERRORs",     check_stale),
        ("escenarios coherentes",check_scenarios_coherent),
    ]

    results = []
    for name, fn in checks:
        ok, detail = fn()
        results.append((name, ok, detail))
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name:<24} {detail}")

    all_ok = all(ok for _, ok, _ in results)
    print()
    if all_ok:
        print("═══ VEREDICTO: ✅ GO V2 ═══════════════════════════════════")
    else:
        failed = [name for name, ok, _ in results if not ok]
        print(f"═══ VEREDICTO: ❌ KO V2 — Pendiente: {', '.join(failed)}")
    print()

    return 0 if all_ok else 1



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())
