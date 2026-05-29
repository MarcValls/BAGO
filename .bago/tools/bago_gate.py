#!/usr/bin/env python3
"""
bago_gate.py — Puerta única de BAGO.

CLI unificado para ejecutar cualquier combinación de gates.
Concepto potenciómetro: cada gate se puede encender/apagar individualmente.

Uso:
  python .bago/tools/bago_gate.py                    # ejecuta TODOS los gates
  python .bago/tools/bago_gate.py --gate sincerity   # solo sincerity
  python .bago/tools/bago_gate.py --gate sincerity --gate version --gate truth
  python .bago/tools/bago_gate.py --json             # salida JSON
  python .bago/tools/bago_gate.py --strict           # WARN también cuenta como KO
  python .bago/tools/bago_gate.py --list             # lista gates disponibles
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import os
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from bago.gates.orchestrator import GateOrchestrator, GateReport
from bago.gates import Status
from bago.gates.plugins import SincerityGate, VersionGate, TruthGate, PrePushGate, InterfaceConsistencyGate


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("bago_gate")
    p.add_argument("--gate", action="append", default=[], help="Gate a ejecutar (repetible). Sin --gate ejecuta todos.")
    p.add_argument("--json", action="store_true", help="Emitir reporte en JSON.")
    p.add_argument("--strict", action="store_true", help="Tratar WARN como KO (exit != 0).")
    p.add_argument("--list", action="store_true", help="Listar gates disponibles y salir.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path.cwd().resolve()
    # Intentar encontrar repo root
    for p in [root, *root.parents]:
        if (p / ".bago").exists():
            root = p
            break

    orch = GateOrchestrator(root)
    orch.register(SincerityGate())
    orch.register(VersionGate())
    orch.register(TruthGate())
    orch.register(PrePushGate())
    orch.register(InterfaceConsistencyGate())

    if args.list:
        print("Gates disponibles:")
        for name in orch.list_gates():
            gate = orch._gates[name]
            print(f"  · {name} — {gate.description}")
        return 0

    gate_names = args.gate if args.gate else None
    report = orch.run(gate_names)

    if args.json:
        print(report.to_json())
    else:
        print(report.to_markdown())

    overall = report.overall_status
    if overall == Status.KO:
        return 1
    if args.strict and overall == Status.WARN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
