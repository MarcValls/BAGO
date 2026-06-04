#!/usr/bin/env python3
"""bago_core/claim_cli.py -- argparse + main for the claim ledger.

FASE 6.5 split of the original :mod:`bago_core.claim_ledger`. This module
is a thin facade: parse args, dispatch to :mod:`bago_core.claim_storage`,
and print results. No business logic or I/O happens here.

R0-R10:
- R0: <120 lines
- R1: CLI only
"""
from __future__ import annotations

import argparse
import sys

from bago_core.claim_model import (
    BASIS_TYPES,
    STATUS_OPEN,
    STATUS_SIMULATED,
    STATUS_VERIFIED,
)
from bago_core.claim_storage import ClaimLedger


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bago claim", description="Claim Evidence Ledger de BAGO")
    parser.add_argument("--base-path", default=".", help="Directorio base del proyecto")
    sub = parser.add_subparsers(dest="action")

    add_p = sub.add_parser("add", help="Anade un claim trazable")
    add_p.add_argument("--claim",     required=True, help="Texto de la afirmacion")
    add_p.add_argument("--basis",     required=True, choices=BASIS_TYPES, help="Tipo de evidencia")
    add_p.add_argument("--command",   default="", help="Comando que genero la evidencia")
    add_p.add_argument("--artifacts", default="", help="Rutas de artefactos separadas por coma")
    add_p.add_argument("--limits",    default="", help="Limites de lo que prueba esta evidencia")
    add_p.add_argument("--status",    default=STATUS_OPEN, choices=[STATUS_OPEN, STATUS_SIMULATED, STATUS_VERIFIED])
    add_p.add_argument("--stdout",    default="", help="Salida capturada del comando")
    add_p.add_argument("--notes",     default="")

    list_p = sub.add_parser("list", help="Lista los claims del ledger")
    list_p.add_argument("--status", default="", help="Filtrar por estado")

    verify_p = sub.add_parser("verify", help="Verifica que los artefactos de un claim existen")
    verify_p.add_argument("claim_id", help="ID del claim a verificar")

    report_p = sub.add_parser("report", help="Resumen del ledger")

    args = parser.parse_args(argv)
    ledger = ClaimLedger(base_path=args.base_path)

    if args.action == "add":
        arts = [a.strip() for a in args.artifacts.split(",") if a.strip()] if args.artifacts else []
        cid = ledger.add(
            claim     = args.claim,
            basis     = args.basis,
            command   = args.command,
            artifacts = arts,
            limits    = args.limits,
            status    = args.status,
            stdout    = args.stdout,
            notes     = args.notes,
        )
        print(f"\u2713 Claim registrado: {cid}")
        return 0

    if args.action == "list":
        claims = ledger.load_all()
        # Show latest state per claim_id
        latest: dict = {}
        for c in claims:
            latest[c.claim_id] = c
        filtered = [c for c in latest.values() if not args.status or c.status == args.status]
        if not filtered:
            print("(sin claims)")
            return 0
        for c in sorted(filtered, key=lambda x: x.recorded_at):
            print(f"  [{c.status:10}] {c.claim_id} -- {c.claim[:70]}")
            if c.command:
                print(f"             cmd: {c.command}")
            if c.limits:
                print(f"          limite: {c.limits}")
        return 0

    if args.action == "verify":
        ok = ledger.verify(args.claim_id)
        if ok:
            print(f"\u2713 Claim {args.claim_id} verificado (artefactos presentes)")
        else:
            print(f"\u2717 Claim {args.claim_id} FAILED (artefactos ausentes o claim no encontrado)")
        return 0 if ok else 1

    if args.action == "report":
        r = ledger.report()
        print(f"Claims totales : {r['total_claims']}")
        print(f"  verified     : {r['verified']}")
        print(f"  open         : {r['open']}")
        print(f"  simulated    : {r['simulated']}")
        print(f"  failed       : {r['failed']}")
        if r["open_ids"]:
            print(f"  open ids     : {', '.join(r['open_ids'])}")
        if r["failed_ids"]:
            print(f"  failed ids   : {', '.join(r['failed_ids'])}")
        return 0

    parser.print_help()
    return 0


def _run_tests() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        ledger = ClaimLedger(base_path=td)
        assert ledger.report()["total_claims"] == 0

        cid = ledger.add(
            claim="Test claim",
            basis="command",
            command="/test",
            artifacts=[],
            limits="Solo prueba unitaria",
        )
        assert ledger.get(cid) is not None
        assert ledger.report()["open"] == 1

        # Verificar: sin artefactos -> verified (nada que comprobar)
        ok = ledger.verify(cid)
        assert ok, "verify sin artefactos debe ser True"
        assert ledger.get(cid).status == STATUS_VERIFIED

        # Simulated claim
        cid2 = ledger.add(
            claim="Claim simulado",
            basis="test_result",
            status=STATUS_SIMULATED,
        )
        assert ledger.simulated_claims()  # debe haber al menos uno

        # Failed claim
        cid3 = ledger.add(
            claim="Claim con artefacto inexistente",
            basis="artifact",
            artifacts=["/nonexistent/path/file.json"],
        )
        ok3 = ledger.verify(cid3)
        assert not ok3, "verify con artefacto inexistente debe ser False"
        assert ledger.get(cid3).status == "failed"

        r = ledger.report()
        assert r["total_claims"] == 3
        assert r["verified"] == 1
        assert r["simulated"] == 1
        assert r["failed"] == 1

    print("claim_ledger.py: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv and "--test" in argv:
        return _run_tests()
    return _cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
