"""handler_support.py — Shared helpers for BAGO API handlers.

Provides:
- send_error: consistent JSON error responses.
- safe_handler: decorator that catches unhandled exceptions and returns
  a standardized 500 response.
- bad_request / not_found: convenience helpers for common HTTP errors.
"""

from __future__ import annotations

import logging
import typing
from typing import Any, Callable

if typing.TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

logger = logging.getLogger("bago.api")


def send_error(
    handler: "BaseHTTPRequestHandler",
    status: int,
    message: str,
    code: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Send a consistent JSON error response."""
    from api_serializers import send_json

    payload: dict[str, Any] = {"ok": False, "error": message}
    if code:
        payload["code"] = code
    if details:
        payload["details"] = details
    send_json(handler, status, payload)


def bad_request(handler: "BaseHTTPRequestHandler", message: str, code: str | None = None) -> None:
    send_error(handler, 400, message, code=code or "BAD_REQUEST")


def not_found(handler: "BaseHTTPRequestHandler", message: str, code: str | None = None) -> None:
    send_error(handler, 404, message, code=code or "NOT_FOUND")


def conflict(handler: "BaseHTTPRequestHandler", message: str, code: str | None = None, details: dict[str, Any] | None = None) -> None:
    send_error(handler, 409, message, code=code or "CONFLICT", details=details)


def safe_handler(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that catches unhandled exceptions and returns 500.

    Use this on the entry-point functions registered in api_dispatch so
    every handler has a last-resort error response instead of crashing
    the bridge thread.
    """

    def wrapper(handler: "BaseHTTPRequestHandler", *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(handler, *args, **kwargs)
        except Exception as exc:
            logger.exception("Unhandled error in handler %s: %s", fn.__name__, exc)
            send_error(handler, 500, "Internal server error", code="INTERNAL_ERROR")

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper
