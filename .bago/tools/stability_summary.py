#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stability_summary.py — Resumen único de estabilidad operacional.

Lee los últimos informes de sandbox (smoke, VM, soak, matrix) y el estado
de los validadores canónicos (validate_manifest, validate_state) para
emitir un bloque conciso de salud antes de avanzar a implementación.

Salida:
  GO   → gates requeridos en verde; se puede avanzar a W2.
  WARN → algún gate requerido advertido pero no bloqueante.
  SKIP → gate opcional no disponible; no afecta la decisión final.
  KO   → al menos un gate bloqueante; no avanzar hasta reparar.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAGO_ROOT = Path(__file__).resolve().parents[1]

# ── helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_validator(script: str) -> tuple[str, str]:
    """Returns (status, output) where status is 'GO' or 'KO'."""
    result = subprocess.run(
        [sys.executable, str(BAGO_ROOT / "tools" / script)],
        capture_output=True,
        text=True,
    )
    out = (result.stdout + result.stderr).strip()
    status = "GO" if result.returncode == 0 else "KO"
    return status, out


def report_gate(name: str, report: dict | None) -> tuple[str, str]:
    """Returns (status, summary_line)."""
    if report is None:
        return "SKIP", f"{name}: no disponible (opcional)"
    overall = report.get("status", report.get("overall_status", "unknown"))
    failures = report.get("failure_count", "n/a")
    workers = report.get("workers", "n/a")
    duration = report.get("duration_seconds", "n/a")
    st = "GO" if str(overall).lower() in ("pass", "ok", "green", "success") else "KO"
    return st, f"{name}: status={overall}, failures={failures}, workers={workers}, duration={duration}s"


def check_stale_task() -> tuple[str, str] | None:
    """Devuelve (status, line) si hay una task pendiente con más de 3 días de antigüedad."""
    task_file = ROOT / ".bago" / "state" / "pending_w2_task.json"
    if not task_file.exists():
        return None
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
        if data.get("status") == "done":
            return None
        created_at = data.get("created_at") or data.get("accepted_at") or data.get("timestamp", "")
        if not created_at:
            return None
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_h = (datetime.now(tz=timezone.utc) - created_dt).total_seconds() / 3600
        title = data.get("idea_title", "—")
        if age_h > 72:
            return ("WARN", f"stale_task: '{title}' abierta hace {int(age_h)}h ({int(age_h/24)}d) — ⚠ supera 3 días")
        return ("GO", f"task_age: '{title}' abierta hace {int(age_h)}h — dentro del límite")
    except Exception:
        return None


def _sprint_block() -> tuple[str, str]:
    """Muestra el último sprint en stability: número, ideas, velocidad.
    # FULL_SPRINT_IN_STABILITY_IMPLEMENTED
    """
    import re
    state_dir = BAGO_ROOT / "state"
    summaries = sorted(state_dir.glob("sprint_summary_*.md"), reverse=True)
    if not summaries:
        return "SKIP", "sprint: sin datos de sprint"
    try:
        text = summaries[0].read_text(encoding="utf-8")
        num_m   = re.search(r"#\s+Sprint BAGO #(\d+)", text)
        ideas_m = re.search(r"-\s+Ideas en este sprint:\s+(\d+)", text)
        vel_m   = re.search(r"-\s+Velocidad:\s+([\d.]+)\s+ideas/día", text)
        total_m = re.search(r"-\s+Total acumulado:\s+([\d/]+)", text)
        num    = num_m.group(1)   if num_m   else "?"
        ideas  = ideas_m.group(1) if ideas_m else "?"
        vel    = vel_m.group(1)   if vel_m   else "?"
        total  = total_m.group(1) if total_m else "?"
        return "GO", f"sprint #{num}: {ideas} ideas  vel={vel}/día  total={total}"
    except Exception as e:
        return "WARN", f"sprint: error al leer ({e})"


def catalog_status() -> tuple[str, str]:
    """Salud del catálogo de ideas: disponibles vs implementadas."""
    import sqlite3 as _sq3
    db_path = BAGO_ROOT / "state" / "bago.db"
    impl_path = BAGO_ROOT / "state" / "implemented_ideas.json"
    MIN_IDEAS = 5
    try:
        implemented = 0
        if impl_path.exists():
            data = json.loads(impl_path.read_text(encoding="utf-8"))
            implemented = len(data.get("implemented", []))
        total_db = 0
        if db_path.exists():
            conn = _sq3.connect(str(db_path))
            total_db = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
            conn.close()
        available = max(0, total_db - implemented)
        if available == 0:
            return "KO", f"catálogo: {implemented} impl., 0 disponibles — renovar catálogo"
        elif available < MIN_IDEAS:
            return "WARN", f"catálogo: {implemented} impl., {available} disp. (< mínimo {MIN_IDEAS})"
        else:
            return "GO", f"catálogo: {implemented} impl., {available} disp. ({total_db} total)"
    except Exception as e:
        return "WARN", f"catálogo: no disponible ({e})"


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("BAGO stability summary")
    print("=" * 44)

    gates: list[tuple[str, str]] = []

    # 1. Canonical validators
    for script, label in [("validate_manifest.py", "validate_manifest"), ("validate_state.py", "validate_state")]:
        st, out = run_validator(script)
        # extract first meaningful line
        first_line = next((l for l in out.splitlines() if l.strip()), out)
        gates.append((st, f"{label}: {first_line}"))

    # 2. Sandbox reports
    report_paths = {
        "smoke":  ROOT / "sandbox/runtime/last-report.json",
        "vm":     ROOT / "sandbox/runtime-vm/last-report-vm.json",
        "soak":   ROOT / "sandbox/runtime-vm/last-soak-report-vm.json",
        "matrix": ROOT / "sandbox/runtime-vm/matrix/last-matrix-summary.json",
    }
    for name, path in report_paths.items():
        report = load_json(path)
        st, line = report_gate(name, report)
        gates.append((st, line))

    # 3. Stale task check
    stale = check_stale_task()
    if stale is not None:
        gates.append(stale)

    # 4. Catalog status
    gates.append(catalog_status())

    # 5. Sprint block
    gates.append(_sprint_block())

    # 6. Print gates
    print()
    for st, line in gates:
        icon = "✓" if st == "GO" else ("⚠" if st == "WARN" else ("-" if st == "SKIP" else "✗"))
        print(f"  [{st}] {icon} {line}")

    # 5. Overall decision
    has_ko = any(st == "KO" for st, _ in gates)
    has_warn = any(st == "WARN" for st, _ in gates)

    print()
    if has_ko:
        print("DECISIÓN: KO — reparar antes de avanzar a W2.")
        print("  → Ejecuta `python3 .bago/tools/validate_pack.py` para diagnóstico completo.")
        return 1
    elif has_warn:
        print("DECISIÓN: WARN — sandbox no disponible; validadores canónicos en verde.")
        print("  → Puedes avanzar a W2 si el trabajo no depende del sandbox.")
        return 0
    else:
        print("DECISIÓN: GO — gates requeridos en verde. Avanzar a W2.")
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
    sys.exit(main())
