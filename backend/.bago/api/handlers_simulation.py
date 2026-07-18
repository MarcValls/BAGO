"""handlers_simulation.py \u2014 ControlShadow endpoints for the BAGO HTTP bridge.

GET  /simulation/status   \u2014 current shadow status
GET  /simulation/events   \u2014 recent shadow events
POST /simulation/config   \u2014 {enabled: bool, mode: str}
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _shadow(handler):
    return getattr(handler, "shadow", None)


def handle_status(handler):
    from api_serializers import send_json
    shadow = _shadow(handler)
    if shadow is None:
        send_json(handler, 503, {"error": "ControlShadow no disponible"})
        return
    send_json(handler, 200, shadow.status())


def handle_events(handler):
    from api_serializers import send_json
    shadow = _shadow(handler)
    if shadow is None:
        send_json(handler, 503, {"error": "ControlShadow no disponible"})
        return
    send_json(handler, 200, {"events": shadow.recent_events()})


def handle_config(handler, body):
    from api_serializers import send_json
    shadow = _shadow(handler)
    if shadow is None:
        send_json(handler, 503, {"error": "ControlShadow no disponible"})
        return
    try:
        status = shadow.configure(enabled=body.get("enabled"), mode=body.get("mode"))
    except ValueError as exc:
        send_json(handler, 400, {"error": str(exc)})
        return
    send_json(handler, 200, status)
