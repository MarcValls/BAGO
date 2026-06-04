#!/usr/bin/env python3
"""bago_core/claim_model.py -- data model for the Claim Evidence Ledger.

This is the FASE 6.5 split of the original :mod:`bago_core.claim_ledger`
(427 lines) into four modules:

  - :mod:`bago_core.claim_model`   -- `Claim` dataclass, status constants,
    basis constants
  - :mod:`bago_core.claim_storage` -- `ClaimLedger` (append-only JSONL store)
  - :mod:`bago_core.claim_cli`     -- argparse + main
  - :mod:`bago_core.claim_ledger`  -- re-export facade (preserves the old
    public surface for `bago claim ...` and the test runner)

R0-R10:
- R0: <120 lines
- R1: model only, no I/O
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


# -- Tipos de base validos ------------------------------------------------------
BASIS_TYPES = ("command", "artifact", "observation", "provider_response", "test_result")

# -- Estados posibles de un claim ----------------------------------------------
STATUS_OPEN       = "open"       # registrado, pendiente de verificacion
STATUS_VERIFIED   = "verified"   # evidencia verificada explicitamente
STATUS_SIMULATED  = "simulated"  # evidencia simulada (nunca = evidencia real)
STATUS_FAILED     = "failed"     # la evidencia no pudo verificarse
STATUS_SUPERSEDED = "superseded" # reemplazado por un claim posterior


class Claim:
    """Representa una afirmacion trazable del sistema."""

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
