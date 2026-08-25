"""FASE 6.5 tests for the claim_ledger split.

Verifies the four modules (model/storage/cli + facade) are importable, the
test runner still works, and a round-trip add->verify produces a verified
claim.
"""
from __future__ import annotations

import subprocess
import hashlib
import sys
import tempfile
import types
import json
import shlex
import unittest
from datetime import datetime, timezone
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
            self.assertFalse(ok)
            self.assertEqual(ledger.get(cid).status, "failed")

    def test_unbound_material_artifact_without_gate_receipt_cannot_verify(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        from bago_core.operational_integrity import CandidateIdentity, EvidenceRecord
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "evidence.txt"
            artifact.write_text("evidence", encoding="utf-8")
            ledger = ClaimLedger(base_path=td)
            cid = ledger.add(claim="x", basis="test_result", command="pytest", artifacts=[str(artifact)])
            candidate = CandidateIdentity("a" * 40, "main", "https://example.invalid/BAGO.git", "origin/main")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            evidence = EvidenceRecord(
                "x", "pytest", (str(artifact),), command=("pytest",), exit_code=0,
                timestamp=datetime.now(timezone.utc).isoformat(), candidate=candidate,
                artifact_sha256=(digest,), receipt_id="test-gate",
            )
            self.assertFalse(ledger.verify(cid, evidence=evidence))
            self.assertEqual(ledger.get(cid).status, "failed")

    def test_arbitrary_existing_file_cannot_verify_without_executed_evidence(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "anything.txt"
            artifact.write_text("exists", encoding="utf-8")
            ledger = ClaimLedger(base_path=td)
            cid = ledger.add(claim="arbitrary", basis="artifact", artifacts=[str(artifact)])
            self.assertFalse(ledger.verify(cid))
            self.assertEqual(ledger.get(cid).status, "failed")

    def test_corrupt_claim_or_receipt_is_an_integrity_error(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        from bago_core.operational_integrity import CandidateIdentity, EvidenceRecord
        with tempfile.TemporaryDirectory() as td:
            ledger = ClaimLedger(base_path=td)
            ledger.claims_file.write_text("{broken\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "claims.jsonl corrupt"):
                ledger.report()
        with tempfile.TemporaryDirectory() as td:
            ledger = ClaimLedger(base_path=td)
            artifact = Path(td) / "gate.log"
            artifact.write_text("PASS", encoding="utf-8")
            cid = ledger.add(claim="x", basis="test_result", command="pytest", artifacts=[str(artifact)])
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            evidence = EvidenceRecord(
                "x", "pytest", (str(artifact),), command=("pytest",), exit_code=0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                candidate=CandidateIdentity("a" * 40, "main", "local-only:C:/BAGO"),
                artifact_sha256=(digest,), receipt_id="test-gate",
            )
            ledger._append_evidence(cid, evidence)
            ledger.update_status(cid, "verified", _evidence_verified=True)
            ledger.receipts_file.write_text("{broken\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "claim_receipts.jsonl corrupt"):
                ledger.report()

    def test_direct_verified_status_is_rejected(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        with tempfile.TemporaryDirectory() as td:
            ledger = ClaimLedger(base_path=td)
            cid = ledger.add(claim="x", basis="observation")
            with self.assertRaisesRegex(ValueError, "material evidence"):
                ledger.update_status(cid, "verified")

    def test_claim_cannot_be_created_as_verified(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        with tempfile.TemporaryDirectory() as td:
            ledger = ClaimLedger(base_path=td)
            with self.assertRaises(ValueError):
                ledger.add(claim="x", basis="observation", status="verified")

    def test_cli_module(self) -> None:
        from bago_core import claim_cli
        self.assertTrue(callable(claim_cli.main))
        self.assertTrue(callable(claim_cli._run_tests))

    def test_cli_candidate_identity_is_derived_and_expected_values_must_match(self) -> None:
        from argparse import Namespace
        from bago_core import claim_cli
        candidate = claim_cli._derive_candidate(REPO)
        matching = Namespace(
            sha=candidate.sha, branch=candidate.branch, remote=candidate.remote,
            upstream=candidate.upstream, worktree_sha256=candidate.worktree_sha256,
        )
        forged = Namespace(
            sha="0" * 40, branch=candidate.branch, remote=candidate.remote,
            upstream=candidate.upstream, worktree_sha256=candidate.worktree_sha256,
        )
        self.assertTrue(claim_cli._matches_expected(candidate, matching))
        self.assertFalse(claim_cli._matches_expected(candidate, forged))

    def test_top_level_claim_verify_forwards_gate_receipt(self) -> None:
        from unittest.mock import patch
        from bago_core.commands.cmd_content import cmd_claim
        from bago_core.parsers import build_parser
        parser = build_parser("test", ".", "ollama-local", "model")
        args = parser.parse_args(["--base-path", "repo", "claim", "verify", "claim-1", "--gate-receipt", "gate.json"])
        captured: list[list[str]] = []
        fake = types.SimpleNamespace(_cli=lambda argv: captured.append(argv) or 0)
        with patch.dict(sys.modules, {"claim_ledger": fake}):
            self.assertEqual(cmd_claim(args), 0)
        self.assertEqual(captured, [["--base-path", "repo", "verify", "claim-1", "--gate-receipt", "gate.json"]])

    def test_real_gate_receipt_verifies_through_claim_cli(self) -> None:
        from bago_core.claim_storage import ClaimLedger
        from bago_core import claim_cli
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as extra_td:
            repo = Path(td)
            extra_repo = Path(extra_td)
            (repo / ".gitignore").write_text(".bago/evidence/\nevidence/\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("baseline", encoding="utf-8")
            for command in (
                ["git", "init", "-q"], ["git", "config", "user.email", "test@example.invalid"],
                ["git", "config", "user.name", "BAGO Test"], ["git", "add", "."], ["git", "commit", "-qm", "baseline"],
            ):
                subprocess.run(command, cwd=repo, check=True, capture_output=True)
            (extra_repo / "tracked.txt").write_text("extra baseline", encoding="utf-8")
            for command in (
                ["git", "init", "-q"], ["git", "config", "user.email", "test@example.invalid"],
                ["git", "config", "user.name", "BAGO Test"], ["git", "add", "."], ["git", "commit", "-qm", "baseline"],
            ):
                subprocess.run(command, cwd=extra_repo, check=True, capture_output=True)
            gate_name = "claim-e2e"
            result = subprocess.run(
                [sys.executable, str(REPO.parent / "scripts" / "record_remediation_gate.py"),
                 "--repo", str(repo), "--extra-repo", str(extra_repo), "--name", gate_name,
                 "--", sys.executable, "-c", "print('PASS')"],
                cwd=REPO.parent, capture_output=True, text=True, check=True,
            )
            receipt = repo / ".bago" / "evidence" / "remediation-gates" / f"{gate_name}.json"
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            artifacts = [str(receipt.parent / payload["stdout"]), str(receipt.parent / payload["stderr"])]
            ledger = ClaimLedger(repo)
            cid = ledger.add(
                claim="real gate passed", basis="test_result", command=shlex.join(payload["command"]), artifacts=artifacts,
            )
            self.assertEqual(claim_cli._cli(["--base-path", str(repo), "verify", cid, "--gate-receipt", str(receipt)]), 0)
            self.assertEqual(ledger.get(cid).status, "verified")
            stdout_path = Path(artifacts[0])
            stdout_original = stdout_path.read_bytes()
            stdout_path.write_text("tampered", encoding="utf-8")
            self.assertEqual(ledger.get(cid).status, "failed")
            stdout_path.write_bytes(stdout_original)
            self.assertEqual(ledger.get(cid).status, "verified")
            extra_repo.joinpath("tracked.txt").write_text("mutated", encoding="utf-8")
            self.assertEqual(ledger.get(cid).status, "failed")
            cid2 = ledger.add(
                claim="stale extra repo gate", basis="test_result", command=shlex.join(payload["command"]), artifacts=artifacts,
            )
            self.assertEqual(claim_cli._cli(["--base-path", str(repo), "verify", cid2, "--gate-receipt", str(receipt)]), 1)
            extra_repo.joinpath("tracked.txt").write_text("extra baseline", encoding="utf-8")
            self.assertEqual(ledger.get(cid).status, "verified")
            repo.joinpath("tracked.txt").write_text("new candidate", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "next candidate"], cwd=repo, check=True, capture_output=True)
            self.assertEqual(ledger.get(cid).status, "failed")

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
