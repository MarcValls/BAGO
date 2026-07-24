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


def _base_path(handler):
    mgr = getattr(handler, "session_mgr", None)
    return str(getattr(mgr, "base_path", "."))


def handle_train_bc(handler, body):
    from api_serializers import send_json
    from bago_core.rl_policies import train_bc_policy
    try:
        report = train_bc_policy(_base_path(handler), n_actions=4, n_features=4)
        report.setdefault("can_execute", False)
        send_json(handler, 200, report)
    except Exception as exc:
        send_json(handler, 500, {"error": f"RL BC train falló: {exc}", "can_execute": False})


def handle_eval(handler, body):
    from api_serializers import send_json
    from bago_core.rl_policies import eval_bc_policy
    try:
        report = eval_bc_policy(_base_path(handler), n_features=4)
        report.setdefault("can_execute", False)
        send_json(handler, 200, report)
    except Exception as exc:
        send_json(handler, 500, {"error": f"RL eval falló: {exc}", "can_execute": False})
