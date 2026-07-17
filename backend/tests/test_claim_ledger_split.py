"""FASE 6.5 tests for the claim_ledger split.

Verifies the four modules (model/storage/cli + facade) are importable, the
test runner still works, and a round-trip add->verify produces a verified
claim.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class ClaimLedgerSplitTests(unittest.TestCase):

    def test_model_module(self) -> None:
        from bago_core.claim_model import (
            BASIS_TYPES, Claim, STATUS_FAILED, STATUS_OPEN,
            STATUS_SIMULATED, STATUS_SUPERSEDED, STATUS_VERIFIED,
        )
        self.assertIn("command", BASIS_TYPES)
        self.assertEqual(STATUS_OPEN, "open")
        c = Claim(claim="hello", basis="command")
        self.assertEqual(c.claim, "hello")
        self.assertEqual(c.basis, "command")
        self.assertEqual(c.status, STATUS_OPEN)
        d = c.to_dict()
        c2 = Claim.from_dict(d)
        self.assertEqual(c2.claim_id, c.claim_id)

    def test_storage_module(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        with tempfile.TemporaryDirectory() as td:
            ledger = ClaimLedger(base_path=td)
            self.assertEqual(ledger.report()["total_claims"], 0)
            cid = ledger.add(claim="x", basis="observation", limits="test")
            self.assertIsNotNone(ledger.get(cid))
            ok = ledger.verify(cid)
            self.assertTrue(ok)
            self.assertEqual(ledger.get(cid).status, "verified")

    def test_cli_module(self) -> None:
        from bago_core import claim_cli
        self.assertTrue(callable(claim_cli.main))
        self.assertTrue(callable(claim_cli._run_tests))

    def test_facade_reexports(self) -> None:
        from bago_core import claim_ledger
        # Public surface preserved
        self.assertTrue(callable(claim_ledger.ClaimLedger))
        self.assertTrue(callable(claim_ledger.Claim))
        self.assertTrue(callable(claim_ledger._cli))
        self.assertTrue(callable(claim_ledger._run_tests))
        self.assertTrue(callable(claim_ledger.main))

    def test_module_invocation_test(self) -> None:
        r = subprocess.run(
            [sys.executable, "-m", "bago_core.claim_ledger", "--test"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn("ALL PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
