from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_error_payload_has_stable_compatible_shape() -> None:
    from api_response import error_payload

    payload = error_payload("question_required", "Campo requerido", details={"field": "question"})
    assert payload == {
        "ok": False,
        "error": "Campo requerido",
        "error_code": "question_required",
        "details": {"field": "question"},
    }
    json.dumps(payload)


def test_interpret_missing_question_exposes_error_code(monkeypatch) -> None:
    import api_serializers
    from handlers_interpret import handle_post

    captured = {}
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )

    class FakeHandler:
        session_mgr = object()

    handle_post(FakeHandler(), {})
    assert captured["status"] == 400
    assert captured["payload"]["error_code"] == "question_required"
    assert captured["payload"]["error"] == "Campo 'question' requerido"
