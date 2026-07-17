"""handlers_rl.py \u2014 RLBridge endpoints for the BAGO HTTP bridge.

GET  /rl/status   \u2014 current RL shadow status
POST /rl/shadow   \u2014 {enabled: bool} toggle shadow mode
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _bridge(handler):
    """Return the RLBridge from the session manager, or None."""
    shadow = getattr(handler, "shadow", None)
    if shadow is not None:
        return shadow
    mgr = getattr(handler, "session_mgr", None)
    if mgr is None:
        return None
    try:
        return mgr.rl_bridge
    except AttributeError:
        pass
    # Fallback: try the legacy class-level rl_bridge attribute.
    try:
        return mgr._rl_bridge()
    except AttributeError:
        return None


def handle_status(handler):
    from api_serializers import send_json
    bridge = _bridge(handler)
    if bridge is None:
        send_json(handler, 503, {"error": "RLBridge no disponible"})
        return
    status = bridge.status()
    status.setdefault("can_execute", False)
    send_json(handler, 200, status)


def handle_shadow(handler, body):
    from api_serializers import send_json
    bridge = _bridge(handler)
    if bridge is None:
        send_json(handler, 503, {"error": "RLBridge no disponible"})
        return
    enabled = bool(body.get("enabled", True))
    if hasattr(bridge, "configure"):
        status = bridge.configure(enabled=enabled, mode="off" if not enabled else None)
    else:
        status = bridge.shadow(enabled)
    if isinstance(status, dict):
        status.setdefault("can_execute", False)
    send_json(handler, 200, status)
