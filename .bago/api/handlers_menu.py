"""handlers_menu.py \u2014 GET /menu for the BAGO HTTP bridge.

Returns the BAGO REPL menu sections. Falls back to empty sections if
the runtime module can't be imported (defensive against packaging drift).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    try:
        from repl import MENU_SECTIONS
    except Exception as exc:
        send_json(handler, 200, {"sections": [], "error": f"menu no disponible: {exc}"})
        return
    send_json(handler, 200, {"sections": MENU_SECTIONS})
