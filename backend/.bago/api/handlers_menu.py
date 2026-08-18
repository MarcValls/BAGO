"""handlers_menu.py - GET /menu for the BAGO HTTP bridge.

Returns the canonical MenuState plus legacy `sections` for compatibility.
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
        menu_state = mgr.menu_state()
    except Exception as exc:
        send_json(handler, 200, {"contract_version": "bago.contract.ui.v1", "sections": [], "error": f"menu no disponible: {exc}"})
        return

    sections = []
    for center in menu_state.get("centros_operativos", []):
        items = []
        for item in center.get("items", []):
            items.append({
                "command": item.get("nombre", ""),
                "description": item.get("description", ""),
                "args_prompt": item.get("args", ""),
                "wizard": item.get("wizard", ""),
                "confirm": bool(item.get("confirm", False)),
            })
        sections.append({
            "title": center.get("nombre", center.get("center_id", "")),
            "description": center.get("descripción", ""),
            "items": items,
        })

    menu_state.setdefault("sections", sections)
    menu_state.setdefault("visible_sections", menu_state.get("secciones_visibles", []))
    send_json(handler, 200, menu_state)
