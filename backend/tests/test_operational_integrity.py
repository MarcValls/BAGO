from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from bago_core.operational_integrity import (
    AuditTrail,
    CandidateIdentity,
    ClosureContract,
    ConflictDetector,
    EvidenceRecord,
    GateRegistry,
    StateTransitionPolicy,
    TruthPolicy,
)


def test_claim_cannot_be_verified_without_material_evidence():
    record = EvidenceRecord(claim="done", action="observe", artifacts=())
    assert TruthPolicy.can_claim_verified(record) is False
    assert StateTransitionPolicy.permits("EXECUTED", "VERIFIED", evidence=record) is False


def test_validation_requires_clean_candidate_closure_and_review(tmp_path):
    artifact = tmp_path / "gate.log"
    artifact.write_text("PASS", encoding="utf-8")
    candidate = CandidateIdentity("a" * 40, "main", "https://example.invalid/BAGO.git", "origin/main", False, "b" * 64)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    record = EvidenceRecord(
        "candidate passes", "test", (str(artifact),), command=("pytest",),
        exit_code=0, timestamp=datetime.now(timezone.utc).isoformat(), candidate=candidate,
        artifact_sha256=(digest,), receipt_id="gate-1",
    )
    assert TruthPolicy.can_claim_validated(record, closure_complete=True, independent_review=False) is False
    # Aunque los campos parezcan plausibles, sin un recibo de gate validable
    # no puede autocertificarse VERIFIED/VALIDATED.
    assert TruthPolicy.can_claim_validated(record, closure_complete=True, independent_review=True) is False


def test_existing_unbound_file_and_missing_exit_code_cannot_verify(tmp_path):
    artifact = tmp_path / "unrelated.txt"
    artifact.write_text("exists", encoding="utf-8")
    record = EvidenceRecord("arbitrary claim", "observe", (str(artifact),))
    assert TruthPolicy.can_claim_verified(record) is False


def test_candidate_identity_rejects_malformed_or_ambiguous_provenance():
    assert CandidateIdentity("x", "main", "x").immutable is False
    assert CandidateIdentity("a" * 40, "", "https://example.invalid/BAGO.git").immutable is False
    assert CandidateIdentity("a" * 40, "main", "origin").immutable is False
    assert CandidateIdentity("a" * 40, "main", "local-only:C:/BAGO", worktree_sha256="bad").immutable is False
    assert CandidateIdentity("a" * 40, "main", "local-only:C:/BAGO", worktree_sha256="b" * 64).immutable is True


def test_evidence_requires_parseable_timezone_aware_timestamp(tmp_path):
    artifact = tmp_path / "gate.log"
    artifact.write_text("PASS", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    candidate = CandidateIdentity("a" * 40, "main", "local-only:C:/BAGO")
    base = dict(
        claim="x", action="pytest", artifacts=(str(artifact),), command=("pytest",), exit_code=0,
        candidate=candidate, artifact_sha256=(digest,), receipt_id="receipt",
    )
    assert TruthPolicy.can_claim_verified(EvidenceRecord(**base, timestamp="")) is False
    assert TruthPolicy.can_claim_verified(EvidenceRecord(**base, timestamp="2026-08-24T01:00:00")) is False
    assert TruthPolicy.can_claim_verified(EvidenceRecord(**base, timestamp="2026-08-24T01:00:00+00:00")) is False


def test_not_run_gate_and_open_finding_block_closure():
    gates = GateRegistry()
    gates.set("backend", "PASS")
    gates.set("electron", "NOT_RUN")
    closure = ClosureContract({"BAGO-AUD-001": "CLOSED", "BAGO-AUD-002": "OPEN"})
    assert gates.complete() is False
    assert closure.complete() is False


def test_conflicts_and_audit_trail_are_explicit(tmp_path):
    conflicts = ConflictDetector.detect(
        {"state": {"tests": 938}, "handoff": {"tests": 928}},
        ("tests",),
    )
    assert conflicts[0]["field"] == "tests"
    trail_path = tmp_path / "audit.jsonl"
    AuditTrail(trail_path).append({"finding": "BAGO-AUD-001", "state": "OPEN"})
    assert "BAGO-AUD-001" in trail_path.read_text(encoding="utf-8")
