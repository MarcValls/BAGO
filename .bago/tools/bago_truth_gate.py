#!/usr/bin/env python3
"""
bago_truth_gate.py — Wrapper CLI para BAGO Truth Gate.

Expone los comandos del Truth Gate como script independiente en .bago/tools/.

Uso:
  python .bago/tools/bago_truth_gate.py run --purpose "validación" -- "python -m pytest .bago/tools/tests -q"
  python .bago/tools/bago_truth_gate.py claim --kind test_pass --text "Tests pasan" --conclusion "OK" --evidence ev_xxx
  python .bago/tools/bago_truth_gate.py close
  python .bago/tools/bago_truth_gate.py report
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

# Asegurar que el paquete bago es importable
TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from bago.truth_cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
