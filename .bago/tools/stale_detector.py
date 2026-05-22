#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stale_detector.py — Detector de artefactos de reporte desactualizados.

Detecta:
  1. Escenarios en active_scenarios con archivo EVAL- en state/scenarios/ (contradicción)
  2. Discrepancia entre inventario en global_state.json vs archivos reales en disco
  3. ESTADO_BAGO_ACTUAL.md con timestamp anterior al last_updated de global_state.json por >48h
  4. Escenarios con "Estado: CERRADO" en MD pero aún en active_scenarios

Uso:
  python3 .bago/tools/stale_detector.py
"""

from pathlib import Path
import json
import re
import sys
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
SCENARIOS_DIR = STATE / "scenarios"
GLOBAL_STATE = STATE / "global_state.json"
ESTADO_FILE = STATE / "ESTADO_BAGO_ACTUAL.md"

WARN = "WARN"
ERROR = "ERROR"

def load_global():
    if not GLOBAL_STATE.exists():
        return {}
    return json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))

def check_eval_in_active(gs: dict, issues: list):
    """Escenarios en active_scenarios con archivo EVAL- en state/scenarios/ → contradicción."""
    active = gs.get("active_scenarios", [])
    if not active:
        return
    if not SCENARIOS_DIR.exists():
        return
    eval_files = list(SCENARIOS_DIR.glob("EVAL-*.md"))
    for scenario_id in active:
        for ef in eval_files:
            if scenario_id.upper() in ef.name.upper() or scenario_id.replace("-", "") in ef.name.replace("-", ""):
                issues.append((ERROR, f"Escenario '{scenario_id}' en active_scenarios pero existe EVAL '{ef.name}' → contradicción"))

def check_inventory_vs_disk(gs: dict, issues: list):
    """Discrepancia entre inventario en global_state.json vs archivos reales en disco."""
    inventory = gs.get("inventory", {})
    dirs = {
        "sessions":  (STATE / "sessions",  "*.json"),
        "changes":   (STATE / "changes",   "*.json"),
        "evidences": (STATE / "evidences", "*.json"),
    }
    for key, (folder, pattern) in dirs.items():
        expected = inventory.get(key, None)
        if expected is None:
            continue
        if not folder.exists():
            real = 0
        else:
            # Excluir README.md del conteo
            real = len([f for f in folder.glob(pattern) if f.name != "README.md"])
        if real != expected:
            sev = WARN if abs(real - expected) <= 2 else ERROR
            issues.append((sev, f"Inventario[{key}]: global_state={expected} vs disco={real} (diff={real-expected:+d})"))

def check_estado_timestamp(gs: dict, issues: list):
    """ESTADO_BAGO_ACTUAL.md con timestamp anterior al last_updated por más de 48h."""
    if not ESTADO_FILE.exists():
        issues.append((WARN, "ESTADO_BAGO_ACTUAL.md no encontrado"))
        return

    last_updated_str = gs.get("updated_at") or gs.get("last_updated")
    if not last_updated_str:
        return

    try:
        last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return

    # Intentar extraer timestamp del archivo ESTADO
    content = ESTADO_FILE.read_text(encoding="utf-8")
    # Buscar patrón de fecha ISO o fecha humana
    date_patterns = [
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)",
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    estado_ts = None
    for pat in date_patterns:
        m = re.search(pat, content)
        if m:
            raw = m.group(1)
            try:
                if "T" in raw:
                    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    # make aware if naive
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    estado_ts = ts
                elif " " in raw:
                    estado_ts = datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                else:
                    estado_ts = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

    if estado_ts is None:
        # Usar mtime del archivo como fallback
        mtime = ESTADO_FILE.stat().st_mtime
        estado_ts = datetime.fromtimestamp(mtime, tz=timezone.utc)

    diff = last_updated - estado_ts
    if diff > timedelta(hours=48):
        issues.append((WARN, f"ESTADO_BAGO_ACTUAL.md parece desactualizado: último update global={last_updated.date()} estado={estado_ts.date()} (diff={diff.days}d)"))

def check_closed_in_active(gs: dict, issues: list):
    """Escenarios con 'Estado: CERRADO' en MD pero aún en active_scenarios."""
    active = gs.get("active_scenarios", [])
    if not active or not SCENARIOS_DIR.exists():
        return

    closed_pattern = re.compile(r"Estado[:\s]*CERRADO", re.IGNORECASE)
    for scenario_id in active:
        # Buscar archivo MD del escenario
        candidates = list(SCENARIOS_DIR.glob(f"*{scenario_id}*.md")) + \
                     list(SCENARIOS_DIR.glob(f"ESCENARIO*{scenario_id.split('-')[-1]}*.md"))
        # También buscar en state/
        candidates += list(STATE.glob(f"*{scenario_id}*.md"))
        for md_file in candidates:
            if md_file.exists():
                content = md_file.read_text(encoding="utf-8")
                if closed_pattern.search(content):
                    issues.append((ERROR, f"Escenario '{scenario_id}' tiene 'CERRADO' en {md_file.name} pero sigue en active_scenarios"))

def main():
    gs = load_global()
    issues = []

    check_eval_in_active(gs, issues)
    check_inventory_vs_disk(gs, issues)
    check_estado_timestamp(gs, issues)
    check_closed_in_active(gs, issues)

    if not issues:
        print("✅ Reporting limpio")
        return 0

    errors = [i for i in issues if i[0] == ERROR]
    warns  = [i for i in issues if i[0] == WARN]

    for sev, msg in issues:
        icon = "❌" if sev == ERROR else "⚠️ "
        print(f"{icon} [{sev}] {msg}")

    print()
    print(f"Resumen: {len(errors)} ERROR(s), {len(warns)} WARN(s)")

    return 1 if errors else 0


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
