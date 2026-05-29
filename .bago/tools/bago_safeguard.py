#!/usr/bin/env python3
"""bago_safeguard.py — Panel de safeguards BAGO.

Gestiona los 4 genes de protección del sistema:
  identity          → identidad operativa de BAGO
  safety_contract   → contrato de operación segura
  kill_switch_policy → garantía de parada del reactor
  project_boundary  → límites del scope del proyecto

Estados por gen:
  ON        → protegido (default)
  SOFT_OFF  → mutable en sombra/candidato, no en vivo
  OFF       → mutable en vivo (peligroso)
  BROKEN    → modo inseguro registrado

Uso:
  bago safeguard              → muestra estado de todos los safeguards
  bago safeguard status       → igual
  bago safeguard explain <gene> → explica las consecuencias de OFF
  bago safeguard set <gene> <state> → cambia estado (pide confirmación)
  bago safeguard history      → historial de cambios
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import datetime
import json
import sys
from pathlib import Path

BAGO_ROOT       = Path(__file__).resolve().parents[2]
SAFEGUARDS_FILE = BAGO_ROOT / ".bago" / "state" / "reactor" / "safeguards.json"

VALID_STATES = ["ON", "SOFT_OFF", "OFF", "BROKEN"]
DANGER_STATES = ["OFF", "BROKEN"]

STATE_ICON = {
    "ON":       "✓",
    "SOFT_OFF": "~",
    "OFF":      "✗",
    "BROKEN":   "☠",
}

STATE_COLOR_HINT = {
    "ON":       "verde",
    "SOFT_OFF": "amarillo",
    "OFF":      "rojo",
    "BROKEN":   "crítico",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(SAFEGUARDS_FILE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        print(f"  ✗ safeguards.json no encontrado: {SAFEGUARDS_FILE}")
        sys.exit(1)

def _save(data: dict):
    SAFEGUARDS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _append_history(data: dict, gene: str, old_state: str, new_state: str, reason: str = ""):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "gene": gene,
        "from": old_state,
        "to": new_state,
        "reason": reason,
    }
    data.setdefault("history", []).append(entry)
    data["_meta"]["last_modified"] = entry["timestamp"]
    data["_meta"]["modified_by"] = "bago safeguard set"

def _confirm(prompt: str) -> bool:
    print(f"\n  ⚠  {prompt}")
    try:
        ans = input("  Confirmar (escribe 'si' para continuar): ").strip().lower()
        return ans in ("si", "sí", "yes", "y")
    except (EOFError, KeyboardInterrupt):
        return False

# ── commands ──────────────────────────────────────────────────────────────────

def cmd_status():
    data = _load()
    genes = data.get("genes", {})
    reactor = data.get("reactor", {})
    r_state = reactor.get("state", "OFF")

    print("\n  ◈ SAFEGUARDS BAGO\n")
    print(f"  {'Gen':<22} {'Estado':<12} {'Descripción'}")
    print("  " + "─" * 75)
    for name, gene in genes.items():
        state = gene.get("state", "ON")
        icon = STATE_ICON.get(state, "?")
        desc = gene.get("description", "")[:50]
        warn = "  ← ATENCIÓN" if state in DANGER_STATES else ""
        print(f"  {name:<22} {icon} {state:<10} {desc}{warn}")

    r_icon = STATE_ICON.get(r_state, "?") if r_state in STATE_ICON else "·"
    print(f"\n  Reactor Kernel: {r_icon} {r_state}")
    print()

def cmd_explain(gene_name: str):
    data = _load()
    gene = data.get("genes", {}).get(gene_name)
    if not gene:
        print(f"  ✗ Gen '{gene_name}' no encontrado.")
        print(f"  Genes disponibles: {', '.join(data.get('genes', {}).keys())}")
        sys.exit(1)

    state = gene.get("state", "ON")
    print(f"\n  ◈ SAFEGUARD: {gene_name}")
    print(f"  Estado actual: {STATE_ICON.get(state,'?')} {state} ({STATE_COLOR_HINT.get(state,'?')})\n")
    print(f"  {gene.get('description', '')}\n")
    print(f"  Consecuencias si se pone OFF:")
    for c in gene.get("consequences_if_off", []):
        print(f"    • {c}")
    print()
    if gene.get("changed_at"):
        print(f"  Último cambio: {gene['changed_at']}")
    print()

def cmd_set(gene_name: str, new_state: str, reason: str = ""):
    new_state = new_state.upper()
    data = _load()
    genes = data.get("genes", {})

    if gene_name not in genes:
        print(f"  ✗ Gen '{gene_name}' no encontrado.")
        sys.exit(1)
    if new_state not in VALID_STATES:
        print(f"  ✗ Estado '{new_state}' inválido. Usa: {', '.join(VALID_STATES)}")
        sys.exit(1)

    gene = genes[gene_name]
    old_state = gene.get("state", "ON")

    if old_state == new_state:
        print(f"  '{gene_name}' ya está en {new_state}.")
        return

    # Mostrar consecuencias antes de confirmar
    if new_state in DANGER_STATES:
        cmd_explain(gene_name)
        confirmed = _confirm(
            f"¿Cambiar '{gene_name}' de {old_state} → {new_state}?"
            + (" Esto puede comprometer la seguridad del sistema." if new_state == "OFF" else "")
        )
        if not confirmed:
            print("  Cancelado.")
            return

    gene["state"] = new_state
    gene["changed_at"] = datetime.datetime.now().isoformat()
    gene["changed_by"] = "bago safeguard set"

    _append_history(data, gene_name, old_state, new_state, reason)
    _save(data)

    icon = STATE_ICON.get(new_state, "?")
    print(f"  {icon} '{gene_name}' cambiado: {old_state} → {new_state}")
    if new_state in DANGER_STATES:
        print(f"  ⚠  Sistema en modo no seguro. Registrado en historial.")
    print()

def cmd_history():
    data = _load()
    history = data.get("history", [])
    if not history:
        print("  Sin cambios registrados.")
        return
    print(f"\n  ◈ HISTORIAL DE SAFEGUARDS ({len(history)} entradas)\n")
    for entry in reversed(history[-20:]):
        ts = entry.get("timestamp", "?")[:19]
        gene = entry.get("gene", "?")
        old = entry.get("from", "?")
        new = entry.get("to", "?")
        reason = entry.get("reason", "")
        print(f"  {ts}  {gene:<22} {old} → {new}  {reason}")
    print()

# ── main ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    args = (argv or sys.argv[1:])
    sub = args[0] if args else "status"

    if sub in ("status", ""):
        cmd_status()
    elif sub == "explain":
        if len(args) < 2:
            print("  Uso: bago safeguard explain <gene>")
            sys.exit(1)
        cmd_explain(args[1])
    elif sub == "set":
        if len(args) < 3:
            print("  Uso: bago safeguard set <gene> <state> [reason]")
            sys.exit(1)
        reason = " ".join(args[3:]) if len(args) > 3 else ""
        cmd_set(args[1], args[2], reason)
    elif sub == "history":
        cmd_history()
    elif sub in ("-h", "--help", "help"):
        print(__doc__)
    else:
        print(f"  Subcomando desconocido: {sub}")
        print("  Uso: bago safeguard [status|explain <gene>|set <gene> <state>|history]")
        sys.exit(1)

if __name__ == "__main__":
    main()
