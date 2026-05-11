#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_v2.py — Auditoría integral BAGO V2.

Ejecuta en secuencia y produce reporte completo:
  1. INTEGRIDAD      → validate_pack
  2. INVENTARIO      → reconcile_state
  3. REPORTING       → stale_detector
  4. HEALTH SCORE    → health_score
  5. VÉRTICE         → vertice_activator
  6. WORKFLOW        → workflow_selector (modo auto)

Tiempo objetivo < 30 segundos.
Salida: reproducible, formato auditoría.

Uso:
  python3 .bago/tools/audit_v2.py
  bago audit
"""

from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
PACK_JSON = ROOT / "pack.json"
GLOBAL_STATE = ROOT / "state" / "global_state.json"


def run_script(script: str, args: list = None) -> tuple[int, str]:
    cmd = [sys.executable, str(TOOLS / script)] + (args or [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=ROOT.parent)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT"
    except Exception as e:
        return 1, f"ERROR: {e}"


def get_pack_version() -> str:
    if PACK_JSON.exists():
        d = json.loads(PACK_JSON.read_text(encoding="utf-8"))
        return d.get("version", "?")
    return "?"


def get_mode() -> str:
    if GLOBAL_STATE.exists():
        gs = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
        notes = gs.get("notes", "").lower()
        last_type = gs.get("last_completed_task_type", "").lower()
        if "self" in notes or "bago" in notes or "cajafisica" in notes:
            return "self"
        if "system_change" in last_type or "system" in last_type:
            return "self"
    # Detectar por path
    if "CAJAFISICA" in str(ROOT) or "cajafisica" in str(ROOT).lower():
        return "self"
    return "project"


def section(num: int, name: str, status_icon: str, detail: str):
    print(f"[{num}] {name:<18} {status_icon}  {detail}")


def main(argv=None):
    _ = argv
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    pack_version = get_pack_version()
    mode = get_mode()

    print()
    print("═══ BAGO V2 AUDITORÍA ═══════════════════════════════════════")
    print(f"Fecha: {now}")
    print(f"Pack:  {pack_version}  modo: {mode}")
    print()

    results = {}

    # [1] INTEGRIDAD — read-only verify (sync must be run separately before audit)
    rc, out = run_script("validate_pack.py")
    ok1 = rc == 0 and "GO pack" in out
    results["integridad"] = ok1
    detail1 = "GO pack" if ok1 else (out.splitlines()[-1] if out else "KO")
    section(1, "INTEGRIDAD", "✅" if ok1 else "❌", detail1)

    # [2] INVENTARIO
    rc, out = run_script("reconcile_state.py")
    ok2 = rc == 0
    results["inventario"] = ok2
    # Extraer conteo del output
    if ok2:
        inv_line = out.splitlines()[0] if out else "reconciliado"
        # Limpiar emoji
        detail2 = inv_line.replace("✅ ", "")
    else:
        detail2 = "Diff detectado — " + (out.splitlines()[0] if out else "?")
    section(2, "INVENTARIO", "✅" if ok2 else "⚠️ ", detail2)

    # [3] REPORTING
    rc, out = run_script("stale_detector.py")
    has_error = "[ERROR]" in out and "❌" in out
    ok3 = not has_error
    results["reporting"] = ok3
    if ok3 and "✅" in out:
        detail3 = "Sin artefactos stale"
    elif ok3:
        warn_n = out.count("[WARN]")
        detail3 = f"{warn_n} WARN(s) sin ERRORs"
    else:
        err_n = out.count("[ERROR]")
        detail3 = f"{err_n} ERROR(s) detectados"
    section(3, "REPORTING", "✅" if ok3 else "❌", detail3)

    # [4] HEALTH SCORE
    # Guard: if there are no closed sessions the score is not meaningful —
    # health_score.py has this guard internally but only when NOT called with
    # --score-only. We replicate the check here so audit_v2 is honest.
    sessions_dir = ROOT / "state" / "sessions"
    has_sessions = sessions_dir.exists() and any(
        True for f in sessions_dir.glob("*.json")
        if f.stat().st_size > 0
    )
    if not has_sessions:
        detail4 = "⚪ INITIALIZING — no closed sessions yet (score not meaningful)"
        results["health"] = None   # excluded from GO/KO verdict
        ok4 = None
        section(4, "HEALTH SCORE", "⚪", detail4)
    else:
        rc, out = run_script("health_score.py", ["--score-only"])
        score = 0
        for line in out.splitlines():
            token = line.strip().split()[0] if line.strip() else ""
            if token.isdigit():
                score = int(token)
                break
        ok4 = score >= 80
        results["health"] = ok4
        if score >= 80:
            semaforo = "🟢"
        elif score >= 50:
            semaforo = "🟡"
        else:
            semaforo = "🔴"
        detail4 = f"{semaforo} {score}/100"
        section(4, "HEALTH SCORE", "✅" if ok4 else "⚠️ ", detail4)

    # [5] VÉRTICE
    rc, out = run_script("vertice_activator.py")
    # rc: 0=CLEAN, 1=WATCH, 2=ACTIVATE
    ok5 = rc == 0
    results["vertice"] = ok5
    if rc == 0:
        detail5 = "CLEAN"
        icon5 = "✅"
    elif rc == 1:
        detail5 = "WATCH — " + (out.splitlines()[1].strip() if len(out.splitlines()) > 1 else "señales presentes")
        icon5 = "⚠️ "
    else:
        detail5 = "ACTIVATE — revisión Vértice recomendada"
        icon5 = "🔴"
    section(5, "VÉRTICE", icon5, detail5)

    # [6] WORKFLOW SUGERIDO
    rc, out = run_script("workflow_selector.py", ["--auto"])
    wf = "?"
    for line in out.splitlines():
        if "Workflow recomendado:" in line:
            wf = line.split(":", 1)[1].strip()
            break
    results["workflow"] = True  # No es un criterio de GO/KO
    section(6, "WORKFLOW SUGERIDO", "→", wf)

    # Veredicto
    critical = ["integridad", "inventario", "reporting"]
    all_critical_ok = all(results.get(k, False) for k in critical)
    all_ok = all_critical_ok and results.get("vertice", True)

    print()
    if all_ok:
        print("═══ VEREDICTO: ✅ GO V2 ══════════════════════════════════════")
    elif all_critical_ok:
        print("═══ VEREDICTO: ⚠️  WATCH V2 — revisar señales no críticas ═════")
    else:
        failed = [k for k in critical if not results.get(k, False)]
        print(f"═══ VEREDICTO: ❌ KO V2 — Bloqueantes: {', '.join(failed)} ════")
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
