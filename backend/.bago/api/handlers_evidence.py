"""handlers_evidence.py - Evidence endpoints for the BAGO HTTP bridge."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _evidence_items(mgr: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    last_receipt = getattr(mgr, "last_receipt", None)
    if last_receipt and hasattr(last_receipt, "to_dict"):
        payload = dict(last_receipt.to_dict())
        payload.setdefault("id", payload.get("receipt_id") or payload.get("envelope_id"))
        payload.setdefault("type", "receipt")
        payload.setdefault("state", payload.get("verification_state") or payload.get("state") or "unknown")
        items.append(payload)
    retrieval = dict(getattr(mgr, "last_context_retrieval", {}) or {})
    for entry in _safe_list(retrieval.get("evidence_by_assertion")):
        if isinstance(entry, dict):
            payload = dict(entry)
            payload.setdefault("type", "assertion")
            payload.setdefault("state", payload.get("state") or "confirmed")
            items.append(payload)
    claim_verification = _safe_list((getattr(mgr, "last_context_retrieval", {}) or {}).get("assertions"))
    for entry in claim_verification:
        if isinstance(entry, dict):
            payload = dict(entry)
            payload.setdefault("type", "claim")
            payload.setdefault("state", payload.get("state") or "unknown")
            items.append(payload)
    history = list(getattr(getattr(mgr, "store", None), "get_history", lambda: [])() or [])
    for message in history[-20:]:
        if not isinstance(message, dict):
            continue
        receipt = message.get("receipt") or message.get("context_receipt")
        if isinstance(receipt, dict):
            payload = dict(receipt)
            payload.setdefault("type", "history_receipt")
            payload.setdefault("id", payload.get("receipt_id") or payload.get("envelope_id") or message.get("id"))
            payload.setdefault("state", payload.get("verification_state") or payload.get("state") or "unknown")
            items.append(payload)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("id") or item.get("receipt_id") or item.get("envelope_id") or item.get("claim_id") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(item)
    return unique


def handle_latest(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    items = _evidence_items(mgr)
    latest = items[0] if items else {}
    send_json(handler, 200, {
        "ok": True,
        "latest": latest,
        "items": items[:20],
        "count": len(items),
    })


def handle_claims(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    claims = []
    retrieval = dict(getattr(mgr, "last_context_retrieval", {}) or {})
    for entry in _safe_list(retrieval.get("assertions")):
        if isinstance(entry, dict):
            claims.append(dict(entry))
    send_json(handler, 200, {
        "ok": True,
        "claims": claims,
        "count": len(claims),
        "receipt_id": getattr(getattr(mgr, "last_receipt", None), "envelope_id", ""),
    })


def handle_receipts(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    items = _evidence_items(mgr)
    receipts = [item for item in items if str(item.get("type", "")).endswith("receipt") or item.get("receipt_id") or item.get("envelope_id")]
    send_json(handler, 200, {
        "ok": True,
        "receipts": receipts,
        "count": len(receipts),
    })


def handle_receipt(handler: "BaseHTTPRequestHandler", receipt_id: str) -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    target = str(receipt_id or "").strip()
    for item in _evidence_items(mgr):
        candidate = str(item.get("receipt_id") or item.get("envelope_id") or item.get("id") or "")
        if candidate == target:
            send_json(handler, 200, {"ok": True, "receipt": item})
            return
    send_json(handler, 404, {"ok": False, "state": "blocked", "error_code": "RECEIPT_NOT_FOUND", "message": f"No existe el receipt {target}"})


def handle_claim(handler: "BaseHTTPRequestHandler", claim_id: str) -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    target = str(claim_id or "").strip()
    for item in _evidence_items(mgr):
        candidate = str(item.get("claim_id") or item.get("id") or "")
        if candidate == target:
            send_json(handler, 200, {"ok": True, "claim": item})
            return
    send_json(handler, 404, {"ok": False, "state": "blocked", "error_code": "CLAIM_NOT_FOUND", "message": f"No existe la claim {target}"})
