"""handlers_interpret.py - Reflexive Interpreter API endpoints."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

CORE_DIR = Path(__file__).resolve().parents[1] / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _question_from_body(body: dict[str, Any]) -> str:
    for key in ("question", "text", "message", "prompt"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _analyze(mgr: Any, question: str) -> dict[str, Any]:
    if hasattr(mgr, "analyze_reflexive_turn"):
        return dict(mgr.analyze_reflexive_turn(question))
    from reflexive_interpreter import analyze_question

    context = {
        "domain": "bago-api",
        "metadata": {
            "session_id": getattr(mgr, "session_id", ""),
            "provider": getattr(mgr, "provider", ""),
            "model": getattr(mgr, "model", ""),
        },
    }
    return analyze_question(question, context).to_dict()


def handle_post(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from api_serializers import send_json
    from reflexive_interpreter import format_reflexive_report

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    question = _question_from_body(body)
    if not question:
        send_json(handler, 400, {"ok": False, "error": "Campo 'question' requerido"})
        return

    analysis = _analyze(mgr, question)
    report = format_reflexive_report(analysis)
    audit = None
    if hasattr(mgr, "record_reflexive_command_audit"):
        audit = mgr.record_reflexive_command_audit(
            analysis=analysis,
            response_content=report,
            command="/api/interpret",
        )
        analysis["reflexive_audit"] = audit

    send_json(handler, 200, {
        "ok": True,
        "session_id": getattr(mgr, "session_id", ""),
        "provider": getattr(mgr, "provider", ""),
        "model": getattr(mgr, "model", ""),
        "question": question,
        "analysis": analysis,
        "report": report,
        "audit": audit,
    })


def handle_history(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    if not hasattr(mgr, "reflexive_audit_tail"):
        send_json(handler, 503, {"ok": False, "error": "Auditoria reflexiva no disponible"})
        return

    parsed = urlparse(getattr(handler, "path", ""))
    query = parse_qs(parsed.query)
    try:
        limit = int((query.get("limit") or query.get("n") or ["10"])[0])
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))

    data = dict(mgr.reflexive_audit_tail(limit))
    data.update({
        "ok": True,
        "session_id": getattr(mgr, "session_id", ""),
        "provider": getattr(mgr, "provider", ""),
        "model": getattr(mgr, "model", ""),
    })
    send_json(handler, 200, data)


def handle_rules(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from reflexive_interpreter import rules_contract_info

    send_json(handler, 200, {
        "ok": True,
        "rules": rules_contract_info(),
    })
