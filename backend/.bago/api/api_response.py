"""Stable JSON response envelopes for BAGO API handlers."""

from __future__ import annotations

from typing import Any


def error_payload(code: str, message: str, *, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": str(message),
        "error_code": str(code),
    }
    if details is not None:
        payload["details"] = details
    return payload


def send_error(
    handler: Any,
    status: int,
    code: str,
    message: str,
    *,
    details: Any = None,
) -> None:
    from api_serializers import send_json

    send_json(handler, status, error_payload(code, message, details=details))
