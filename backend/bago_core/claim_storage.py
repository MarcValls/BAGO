#!/usr/bin/env python3
"""bago_core/claim_storage.py -- append-only JSONL store for Claim records.

This is the FASE 6.5 split of the original :mod:`bago_core.claim_ledger`
(427 lines) into four modules. The store knows nothing about CLI or
rendering; it only knows how to read, append, and reduce Claim rows.

R0-R10:
- R0: <200 lines
- R1: storage only, zero argparse
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bago_core.claim_model import (
    BASIS_TYPES,
    Claim,
    STATUS_FAILED,
    STATUS_OPEN,
    STATUS_SIMULATED,
    STATUS_SUPERSEDED,
    STATUS_VERIFIED,
)
class ClaimLedger:
    """
    Registro append-only de claims trazables.

    Los claims NUNCA se eliminan. Solo cambian de estado.
    El archivo claims.jsonl es la fuente de verdad.
    """

    def __init__(self, base_path: str | Path = ".") -> None:
        self.base_path = Path(base_path)
        self.evidence_dir = self.base_path / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.claims_file = self.evidence_dir / "claims.jsonl"

    # -- Lectura ---------------------------------------------------------------

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
        """Devuelve el ultimo estado de un claim por id."""
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

    # -- Escritura -------------------------------------------------------------

    def _append(self, claim: Claim) -> None:
        """Anade una linea al ledger (append-only)."""
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
        """Anade un claim y devuelve su claim_id."""
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

    # -- Reporte ---------------------------------------------------------------

    def report(self) -> dict[str, Any]:
        """Resumen del ledger para validate y evidencias."""
        all_claims = self.load_all()
        # Para cada claim_id, el ultimo estado es el que manda
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
