"""handlers_providers.py \u2014 GET /providers for the BAGO HTTP bridge.

Returns the list of available providers + the active model catalog mode.
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
    providers = mgr.available_providers()
    cfg = getattr(mgr, "config", None)
    mode = cfg.get("model_catalog.mode", "all") if cfg else "all"
    send_json(handler, 200, {"providers": providers, "mode": mode})
