"""handlers_status.py \u2014 GET /status for the BAGO HTTP bridge.

Returns a snapshot of the SessionManager state (provider, model, role,
uptime). 503 if no SessionManager is wired in.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = getattr(handler, "session_mgr", None)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    try:
        send_json(handler, 200, mgr.status())
    except Exception as exc:
        # If status() raises (e.g. mid-init), return a minimal snapshot.
        send_json(handler, 200, {
            "session_id": getattr(mgr, "session_id", "?"),
            "provider": getattr(mgr, "provider", "?"),
            "model": getattr(mgr, "model", "?"),
            "status_error": str(exc),
        })
