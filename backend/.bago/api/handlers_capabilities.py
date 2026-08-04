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
    capabilities = [{
        "id": snapshot["capability"]["id"],
        "name": snapshot["capability"]["name"],
        "description": snapshot["capability"]["description"],
        "availability": snapshot["capability"]["availability"],
        "definition_state": snapshot["capability"]["definition_state"],
        "piece_count": len(snapshot["pieces"]),
        "route_count": len(snapshot["routes"]),
        "revision": snapshot["revision"],
        "etag": snapshot["etag"],
    }]
    try:
        from capability_packages import list_packages
        capabilities.extend({
            "id": item["id"],
            "name": item["name"],
            "description": item["description"],
            "availability": "available" if item["enabled"] else "conditional",
            "definition_state": "prepared",
            "piece_count": 1,
            "route_count": 1,
            "revision": 1,
            "etag": item["digest"],
        } for item in list_packages())
    except Exception:
        pass
    send_json(handler, 200, {
        "ok": True,
        "feature_flag": FEATURE_FLAG,
        "mode": "read_only",
        "capabilities": capabilities,
    })


def handle_get(handler: "BaseHTTPRequestHandler", capability_id: str) -> None:
    from api_serializers import send_json
    if capability_id != CAPABILITY_ID:
        try:
            from capability_packages import build_package_snapshot
            send_json(handler, 200, build_package_snapshot(capability_id))
        except Exception as exc:
            send_json(handler, 404, {"error": str(exc) or "Capacidad no encontrada", "capability_id": capability_id})
        return
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    try:
        send_json(handler, 200, build_capability_snapshot(mgr))
    except Exception as exc:
        send_json(handler, 500, {"error": f"No se pudo construir la anatomía: {exc}"})
