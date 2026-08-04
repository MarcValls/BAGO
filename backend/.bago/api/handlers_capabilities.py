"""GET read-only de Anatomía de capacidades."""

from __future__ import annotations

from typing import TYPE_CHECKING

from capability_contract import CAPABILITY_ID, FEATURE_FLAG, build_capability_snapshot

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    try:
        snapshot = build_capability_snapshot(mgr)
    except Exception as exc:
        send_json(handler, 500, {"error": f"No se pudo construir la anatomía: {exc}"})
        return
    send_json(handler, 200, {
        "ok": True,
        "feature_flag": FEATURE_FLAG,
        "mode": "read_only",
        "capabilities": [{
            "id": snapshot["capability"]["id"],
            "name": snapshot["capability"]["name"],
            "description": snapshot["capability"]["description"],
            "availability": snapshot["capability"]["availability"],
            "definition_state": snapshot["capability"]["definition_state"],
            "piece_count": len(snapshot["pieces"]),
            "route_count": len(snapshot["routes"]),
            "revision": snapshot["revision"],
            "etag": snapshot["etag"],
        }],
    })


def handle_get(handler: "BaseHTTPRequestHandler", capability_id: str) -> None:
    from api_serializers import send_json
    if capability_id != CAPABILITY_ID:
        send_json(handler, 404, {"error": "Capacidad no encontrada", "capability_id": capability_id})
        return
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    try:
        send_json(handler, 200, build_capability_snapshot(mgr))
    except Exception as exc:
        send_json(handler, 500, {"error": f"No se pudo construir la anatomía: {exc}"})

