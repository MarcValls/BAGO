"""handlers_health.py — GET /health for the BAGO HTTP bridge.

Minimal readiness probe used by Electron warmup. It must stay tiny and
side-effect free so startup checks do not depend on heavy session state.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "ready": False, "error": "SessionManager no disponible"})
        return
    send_json(handler, 200, {
        "ok": True,
        "ready": True,
        "session_id": getattr(mgr, "session_id", "?"),
        "provider": getattr(mgr, "provider", "?"),
        "model": getattr(mgr, "model", "?"),
    })
