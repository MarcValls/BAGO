from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


def test_context_fragment_and_envelope_round_trip():
    from context_envelope import ContextEnvelope, ContextFragment, ContextReceipt

    fragment = ContextFragment.from_any({
        "content": "def ping(): return 'pong'",
        "source": "workspace_file",
        "path": "src/ping.py",
        "scope": "Project",
        "authority_level": "project",
        "reason_for_inclusion": "workspace file",
    })
    envelope = ContextEnvelope(
        system_prompt="SYS",
        messages=[{"role": "user", "content": "hola"}],
        fragments=[fragment],
        request_id="req-1",
        creation_timestamp="2026-06-30T00:00:00+00:00",
    )
    receipt = ContextReceipt.from_response(
        envelope=envelope,
        response_content="ok",
        model_used="m",
        finish_reason="stop",
        usage_input=1,
        usage_output=1,
        usage_total=2,
        latency_ms=5.0,
        context_details={
            "verification_state": "verified",
            "considered_fragments": [fragment.to_dict()],
            "accepted_fragments": [fragment.to_dict()],
        },
    )

    json.dumps(envelope.to_dict())
    json.dumps(receipt.to_dict())
    assert envelope.fragments[0].source_uri == "src/ping.py"
    assert receipt.considered_fragments[0]["source_uri"] == "src/ping.py"
    assert receipt.verification_state == "verified"


def test_claim_verifier_requires_evidence_for_verified():
    from context_governance import ClaimVerifier

    verifier = ClaimVerifier()
    blocked = verifier.verify(["algo importante"], evidence=[], response_text="algo importante")
    assert blocked["verified"] == []
    assert blocked["unverified"]

    allowed = verifier.verify(
        [{"claim": "algo importante", "evidence_refs": [{"type": "file", "path": "src/a.py"}]}],
        evidence=[{"content": "dato", "source": "workspace_file", "source_uri": "src/a.py"}],
        response_text="algo importante",
    )
    assert allowed["verified"]
    assert allowed["verified"][0]["status"] == "verified"
    assert not allowed["verified_without_evidence_blocked"]


def test_context_router_and_canon_cache_invalidate_on_source_change():
    from context_governance import CanonCache, ContextClassifier, ContextPlanner

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "CANON.MD").write_text("canon old line\n", encoding="utf-8")

        classifier = ContextClassifier()
        plan = ContextPlanner().plan(
            classifier.classify("revisa el canon y el contrato"),
            available_sources=["canonical_cache", "dynamic_retrieval", "session_memory"],
            model_context_tokens=4096,
        )
        assert "canonical_cache" in plan.sources_required

        cache = CanonCache(root, root / ".gabo" / "context")
        first = cache.retrieve("canon", limit=2)
        assert first
        assert "old" in first[0]["content"]

        (root / "CANON.MD").write_text("canon new line\n", encoding="utf-8")
        second = cache.retrieve("canon", limit=2)
        assert second
        assert "new" in second[0]["content"]
