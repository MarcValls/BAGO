"""handlers_session.py \u2014 GET /session for the BAGO HTTP bridge.

Returns the current SessionManager's identity (session_id, provider, model,
active agent, tool calling flag, model catalog mode). 503 if no
SessionManager is wired in.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    return getattr(handler, "session_mgr", None)


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    active_agent = "main"
    gateway = getattr(mgr, "agent_gateway", None)
    if gateway is not None and getattr(gateway, "active", None) is not None:
        active_agent = gateway.active.name
    cfg = getattr(mgr, "config", None)
    tool_calling = cfg.get("features.tool_calling", False) if cfg else False
    catalog_mode = cfg.get("model_catalog.mode", "all") if cfg else "all"
    send_json(handler, 200, {
        "session_id": getattr(mgr, "session_id", "?"),
        "provider": getattr(mgr, "provider", "?"),
        "model": getattr(mgr, "model", "?"),
        "status": mgr.status(),
        "active_agent": active_agent,
        "tool_calling": tool_calling,
        "model_catalog_mode": catalog_mode,
    })
