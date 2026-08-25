from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _capture(monkeypatch):
    captured = {}

    def send_json(_handler, status, payload):
        captured.update(status=status, payload=payload)

    import api_serializers
    monkeypatch.setattr(api_serializers, "send_json", send_json)
    return captured


def test_evidence_claims_uses_same_durable_ledger_as_cli(tmp_path, monkeypatch):
    from bago_core.claim_storage import ClaimLedger
    from handlers_evidence import handle_claim, handle_claims

    ledger = ClaimLedger(tmp_path)
    claim_id = ledger.add("gate passed", "test_result", command="pytest", artifacts=["gate.log"])

    class Manager:
        base_path = tmp_path
        last_context_retrieval = {"assertions": [{"claim_id": "ephemeral", "claim": "not authoritative"}]}

    class Handler:
        session_mgr = Manager()

    captured = _capture(monkeypatch)
    handle_claims(Handler())
    assert captured["status"] == 200
    assert captured["payload"]["source"] == "claim_ledger"
    assert [item["claim_id"] for item in captured["payload"]["claims"]] == [claim_id]

    handle_claim(Handler(), claim_id)
    assert captured["status"] == 200
    assert captured["payload"]["claim"]["claim_id"] == claim_id
    assert captured["payload"]["source"] == "claim_ledger"


def test_evidence_claims_fails_closed_on_corrupt_ledger(tmp_path, monkeypatch):
    from handlers_evidence import handle_claims

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "claims.jsonl").write_text("{not-json}\n", encoding="utf-8")

    class Manager:
        base_path = tmp_path

    class Handler:
        session_mgr = Manager()

    captured = _capture(monkeypatch)
    handle_claims(Handler())
    assert captured["status"] == 500
    assert captured["payload"]["error_code"] == "CLAIM_LEDGER_INVALID"
