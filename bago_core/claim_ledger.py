#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
claim_ledger.py â€” BAGO 4.1.5 Claim Evidence Ledger

Registro append-only de afirmaciones con evidencia trazable.

El nÃºcleo anti-mentira de BAGO: ninguna afirmaciÃ³n relevante del sistema puede
existir sin un rastro que indique en quÃ© se basa, quÃ© comando la generÃ³ y
quÃ© artefactos la sostienen.

Regla central:
    sin evidencia â†’ no hay claim
    sin comando   â†’ no hay validaciÃ³n
    sin artefacto â†’ no hay prueba

Uso:
    ledger = ClaimLedger(base_path=".bago/state")
    claim_id = ledger.add(
        claim="La sesiÃ³n fue guardada correctamente",
        basis="command",
        command="/save",
        artifacts=[".bago/state/sessions/abc.json"],
        limits="No valida calidad de respuesta del provider"
    )
    ledger.verify(claim_id, artifacts_exist=True)
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# â”€â”€ Tipos de base vÃ¡lidos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BASIS_TYPES = ("command", "artifact", "observation", "provider_response", "test_result")

# â”€â”€ Estados posibles de un claim â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STATUS_OPEN       = "open"       # registrado, pendiente de verificaciÃ³n
STATUS_VERIFIED   = "verified"   # evidencia verificada explÃ­citamente
STATUS_SIMULATED  = "simulated"  # evidencia simulada (nunca = evidencia real)
STATUS_FAILED     = "failed"     # la evidencia no pudo verificarse
STATUS_SUPERSEDED = "superseded" # reemplazado por un claim posterior


class Claim:
    """Representa una afirmaciÃ³n trazable del sistema."""

    def __init__(
        self,
        claim: str,
        basis: str,
        command: str = "",
        artifacts: list[str] | None = None,
        limits: str = "",
        status: str = STATUS_OPEN,
        claim_id: str | None = None,
        recorded_at: str | None = None,
        resolved_at: str | None = None,
        session_id: str = "",
        provider: str = "",
        model: str = "",
        stdout: str = "",
        notes: str = "",
    ):
        if basis not in BASIS_TYPES:
            raise ValueError(f"basis debe ser uno de: {BASIS_TYPES}")
        self.claim_id    = claim_id or str(uuid.uuid4())[:12]
        self.claim       = claim
        self.basis       = basis
        self.command     = command
        self.artifacts   = artifacts or []
        self.limits      = limits
        self.status      = status
        self.recorded_at = recorded_at or datetime.now(timezone.utc).isoformat()
        self.resolved_at = resolved_at
        self.session_id  = session_id
        self.provider    = provider
        self.model       = model
        self.stdout      = stdout
        self.notes       = notes

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id":    self.claim_id,
            "claim":       self.claim,
            "basis":       self.basis,
            "command":     self.command,
            "artifacts":   self.artifacts,
            "limits":      self.limits,
            "status":      self.status,
            "recorded_at": self.recorded_at,
            "resolved_at": self.resolved_at,
            "session_id":  self.session_id,
            "provider":    self.provider,
            "model":       self.model,
            "stdout":      self.stdout,
            "notes":       self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        return cls(
            claim       = data["claim"],
            basis       = data.get("basis", "observation"),
            command     = data.get("command", ""),
            artifacts   = data.get("artifacts", []),
            limits      = data.get("limits", ""),
            status      = data.get("status", STATUS_OPEN),
            claim_id    = data.get("claim_id"),
            recorded_at = data.get("recorded_at"),
            resolved_at = data.get("resolved_at"),
            session_id  = data.get("session_id", ""),
            provider    = data.get("provider", ""),
            model       = data.get("model", ""),
            stdout      = data.get("stdout", ""),
            notes       = data.get("notes", ""),
        )

    def __repr__(self) -> str:
        return (
            f"Claim({self.claim_id!r}, basis={self.basis!r}, "
            f"status={self.status!r}, claim={self.claim!r})"
        )


class ClaimLedger:
    """
    Registro append-only de claims trazables.

    Los claims NUNCA se eliminan. Solo cambian de estado.
    El archivo claims.jsonl es la fuente de verdad.
    """

    def __init__(self, base_path: str | Path = ".") -> None:
        self.base_path = Path(base_path)
        self.evidence_dir = self.base_path / ".bago" / "state" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.claims_file = self.evidence_dir / "claims.jsonl"

    # â”€â”€ Lectura â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def load_all(self) -> list[Claim]:
        """Carga todos los claims del ledger."""
        if not self.claims_file.exists():
            return []
        claims: list[Claim] = []
        for line in self.claims_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    claims.append(Claim.from_dict(json.loads(line)))
                except Exception:
                    pass
        return claims

    def get(self, claim_id: str) -> Claim | None:
        """Devuelve el Ãºltimo estado de un claim por id."""
        found = None
        for c in self.load_all():
            if c.claim_id == claim_id:
                found = c
        return found

    def open_claims(self) -> list[Claim]:
        return [c for c in self.load_all() if c.status == STATUS_OPEN]

    def failed_claims(self) -> list[Claim]:
        return [c for c in self.load_all() if c.status == STATUS_FAILED]

    def simulated_claims(self) -> list[Claim]:
        return [c for c in self.load_all() if c.status == STATUS_SIMULATED]

    # â”€â”€ Escritura â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _append(self, claim: Claim) -> None:
        """AÃ±ade una lÃ­nea al ledger (append-only)."""
        with self.claims_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(claim.to_dict(), ensure_ascii=False) + "\n")

    def add(
        self,
        claim: str,
        basis: str,
        command: str = "",
        artifacts: list[str] | None = None,
        limits: str = "",
        status: str = STATUS_OPEN,
        session_id: str = "",
        provider: str = "",
        model: str = "",
        stdout: str = "",
        notes: str = "",
    ) -> str:
        """AÃ±ade un claim y devuelve su claim_id."""
        c = Claim(
            claim      = claim,
            basis      = basis,
            command    = command,
            artifacts  = artifacts or [],
            limits     = limits,
            status     = status,
            session_id = session_id,
            provider   = provider,
            model      = model,
            stdout     = stdout,
            notes      = notes,
        )
        self._append(c)
        return c.claim_id

    def update_status(self, claim_id: str, new_status: str, notes: str = "") -> bool:
        """
        Registra un nuevo estado para un claim existente.
        El ledger es append-only: el estado nuevo va como nueva entrada con mismo claim_id.
        """
        original = self.get(claim_id)
        if original is None:
            return False
        updated = Claim(
            claim       = original.claim,
            basis       = original.basis,
            command     = original.command,
            artifacts   = original.artifacts,
            limits      = original.limits,
            status      = new_status,
            claim_id    = claim_id,
            recorded_at = original.recorded_at,
            resolved_at = datetime.now(timezone.utc).isoformat(),
            session_id  = original.session_id,
            provider    = original.provider,
            model       = original.model,
            stdout      = original.stdout,
            notes       = notes or original.notes,
        )
        self._append(updated)
        return True

    def verify(self, claim_id: str, artifacts_exist: bool = True) -> bool:
        """
        Verifica un claim: comprueba que sus artefactos existen en disco
        y marca el claim como verified (o failed).
        """
        claim = self.get(claim_id)
        if claim is None:
            return False

        all_exist = all(Path(a).exists() for a in claim.artifacts) if claim.artifacts else True
        ok = artifacts_exist and all_exist
        new_status = STATUS_VERIFIED if ok else STATUS_FAILED
        self.update_status(claim_id, new_status, notes="auto-verified by ClaimLedger.verify()")
        return ok

    # â”€â”€ Reporte â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def report(self) -> dict[str, Any]:
        """Resumen del ledger para validate y evidencias."""
        all_claims = self.load_all()
        # Para cada claim_id, el Ãºltimo estado es el que manda
        latest: dict[str, Claim] = {}
        for c in all_claims:
            latest[c.claim_id] = c

        by_status: dict[str, list[str]] = {}
        for c in latest.values():
            by_status.setdefault(c.status, []).append(c.claim_id)

        return {
            "total_claims":    len(latest),
            "open":            len(by_status.get(STATUS_OPEN, [])),
            "verified":        len(by_status.get(STATUS_VERIFIED, [])),
            "simulated":       len(by_status.get(STATUS_SIMULATED, [])),
            "failed":          len(by_status.get(STATUS_FAILED, [])),
            "superseded":      len(by_status.get(STATUS_SUPERSEDED, [])),
            "open_ids":        by_status.get(STATUS_OPEN, []),
            "failed_ids":      by_status.get(STATUS_FAILED, []),
        }


# â”€â”€ CLI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _cli(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="bago claim", description="Claim Evidence Ledger de BAGO")
    parser.add_argument("--base-path", default=".", help="Directorio base del proyecto")
    sub = parser.add_subparsers(dest="action")

    add_p = sub.add_parser("add", help="AÃ±ade un claim trazable")
    add_p.add_argument("--claim",     required=True, help="Texto de la afirmaciÃ³n")
    add_p.add_argument("--basis",     required=True, choices=BASIS_TYPES, help="Tipo de evidencia")
    add_p.add_argument("--command",   default="", help="Comando que generÃ³ la evidencia")
    add_p.add_argument("--artifacts", default="", help="Rutas de artefactos separadas por coma")
    add_p.add_argument("--limits",    default="", help="LÃ­mites de lo que prueba esta evidencia")
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
        print(f"âœ“ Claim registrado: {cid}")
        return 0

    if args.action == "list":
        claims = ledger.load_all()
        # Show latest state per claim_id
        latest: dict[str, Claim] = {}
        for c in claims:
            latest[c.claim_id] = c
        filtered = [c for c in latest.values() if not args.status or c.status == args.status]
        if not filtered:
            print("(sin claims)")
            return 0
        for c in sorted(filtered, key=lambda x: x.recorded_at):
            print(f"  [{c.status:10}] {c.claim_id} â€” {c.claim[:70]}")
            if c.command:
                print(f"             cmd: {c.command}")
            if c.limits:
                print(f"          lÃ­mite: {c.limits}")
        return 0

    if args.action == "verify":
        ok = ledger.verify(args.claim_id)
        if ok:
            print(f"âœ“ Claim {args.claim_id} verificado (artefactos presentes)")
        else:
            print(f"âœ— Claim {args.claim_id} FAILED (artefactos ausentes o claim no encontrado)")
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

        # Verificar: sin artefactos â†’ verified (nada que comprobar)
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
        assert ledger.get(cid3).status == STATUS_FAILED

        r = ledger.report()
        assert r["total_claims"] == 3
        assert r["verified"] == 1
        assert r["simulated"] == 1
        assert r["failed"] == 1

    print("claim_ledger.py: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(_cli())
