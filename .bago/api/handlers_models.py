"""handlers_models.py \u2014 GET /models/<provider> for the BAGO HTTP bridge.

Returns the model catalog for a single provider.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler", provider: str) -> None:
    from api_serializers import send_json
    mgr = getattr(handler, "session_mgr", None)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    catalog = mgr.list_model_catalog(provider)
    send_json(handler, 200, {"provider": provider, "models": catalog})
