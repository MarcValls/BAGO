"""Loopback desktop diagnostics forwarded to the canonical structured logger."""
from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle_viewer_log(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    from api_serializers import send_json
    from structured_log import get_logger

    try:
        address = ipaddress.ip_address(str(handler.client_address[0]))
    except (ValueError, IndexError, TypeError):
        send_json(handler, 403, {"ok": False, "code": "DESKTOP_LOG_LOCAL_ONLY"})
        return
    if not address.is_loopback:
        send_json(handler, 403, {"ok": False, "code": "DESKTOP_LOG_LOCAL_ONLY"})
        return

    payload = body if isinstance(body, dict) else {}
    if payload.get("source") != "electron-viewer":
        send_json(handler, 400, {"ok": False, "code": "DESKTOP_LOG_SOURCE_INVALID"})
        return
    kind = payload.get("kind")
    message = payload.get("message")
    if kind not in {"boot", "request"} or not isinstance(message, str) or not message or len(message) > 2048:
        send_json(handler, 400, {"ok": False, "code": "DESKTOP_LOG_RECORD_INVALID"})
        return

    get_logger().info("electron_viewer_diagnostic", source="electron-viewer", kind=kind, message=message)
    send_json(handler, 200, {"ok": True})
