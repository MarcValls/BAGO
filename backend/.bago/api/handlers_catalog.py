"""handlers_catalog.py \u2014 catalog mode endpoints for the BAGO HTTP bridge.

GET  /catalog/status   \u2014 current model_catalog.mode + production_mode
POST /catalog/config    \u2014 set model_catalog.mode to "all" or "available-only"
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def handle_status(handler):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    send_json(handler, 200, {
        "mode": mgr.config.get("model_catalog.mode", "all"),
        "production_mode": mgr.config.get("model_catalog.production_mode", "available-only"),
    })


def handle_config(handler, body):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    mode = str(body.get("mode", "")).strip()
    if mode not in ("all", "available-only"):
        send_json(handler, 400, {"error": "Modo inv\u00e1lido. Usa all|available-only"})
        return
    mgr.config.set("model_catalog.mode", mode)
    mgr.invalidate_providers_cache()
    send_json(handler, 200, {
        "ok": True,
        "mode": mode,
        "production_mode": mgr.config.get("model_catalog.production_mode", "available-only"),
    })
