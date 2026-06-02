#!/usr/bin/env python3
"""bago_core/claim_ledger.py -- facade for the Claim Evidence Ledger (FASE 6.5).

The original 427-line monolith has been split into three modules:

  - :mod:`bago_core.claim_model`   -- Claim dataclass + status/basis constants
  - :mod:`bago_core.claim_storage` -- ClaimLedger (append-only JSONL store)
  - :mod:`bago_core.claim_cli`     -- argparse + main + test runner

This file is a re-export facade so `bago claim ...` (driven by the launcher)
and `python -m bago_core.claim_ledger --test` keep working unchanged.

R0-R10: facade only, no logic.
"""
from __future__ import annotations

from bago_core.claim_cli import _cli, _run_tests, main
from bago_core.claim_model import (
    BASIS_TYPES,
    STATUS_FAILED,
    STATUS_OPEN,
    STATUS_SIMULATED,
    STATUS_SUPERSEDED,
    STATUS_VERIFIED,
    Claim,
)
from bago_core.claim_storage import ClaimLedger

__all__ = [
    "BASIS_TYPES",
    "Claim",
    "ClaimLedger",
    "STATUS_FAILED",
    "STATUS_OPEN",
    "STATUS_SIMULATED",
    "STATUS_SUPERSEDED",
    "STATUS_VERIFIED",
    "_cli",
    "_run_tests",
    "main",
]


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(_cli())
