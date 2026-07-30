"""Endpoints de actualización integrada."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle_check(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from update_manager import check
    result = check()
    send_json(handler, 200 if "error" not in result else 502, result)


def handle_status(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from update_manager import status
    send_json(handler, 200, status())


def handle_update(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    from api_serializers import send_json
    from update_manager import start_update
    tag = str((body or {}).get("tag", "")).strip()
    result = start_update(tag)
    send_json(handler, 202 if result.get("ok") else 409, result)
