"""handlers_history.py \u2014 GET /history for the BAGO HTTP bridge.

Returns the full chat history from the SessionManager store, along with
the session id and message count.
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
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    store = getattr(mgr, "store", None)
    if store is None:
        send_json(handler, 200, {
            "session_id": getattr(mgr, "session_id", "?"),
            "messages": [],
            "count": 0,
        })
        return
    history = store.get_history()
    send_json(handler, 200, {
        "session_id": getattr(mgr, "session_id", "?"),
        "messages": history,
        "count": len(history),
    })
