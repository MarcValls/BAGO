from __future__ import annotations

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
    record = EvidenceRecord("candidate passes", "test", (str(artifact),), exit_code=0, candidate=candidate)
    assert TruthPolicy.can_claim_validated(record, closure_complete=True, independent_review=False) is False
    assert TruthPolicy.can_claim_validated(record, closure_complete=True, independent_review=True) is True


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
