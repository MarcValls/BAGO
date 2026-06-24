"""api_serializers.py \u2014 JSON serialization helpers for the BAGO HTTP bridge.

Owns:
  - send_json(handler, status, data)  : writes a JSON response with CORS headers
  - send_bytes(handler, status, ct, b) : writes a raw byte response (static files)
  - json_safe(value)                   : dataclass/dict/list/tuple -> JSON-safe tree
  - read_body(handler, max_bytes)      : parse a JSON request body with size cap

Why a separate module: bridge.py used to mix HTTP plumbing with
serialization concerns; this module isolates the latter so handlers can
be tested without spinning up a server.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any


def json_safe(value: Any) -> Any:
    """Convert dataclass/dict/list/tuple/Path/Enum to JSON-safe tree.

    Strings, ints, floats, bools, and None pass through. Anything else
    falls back to str(value) so the encoder never raises.
    """
    if dataclasses.is_dataclass(value):
        return json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def send_json(handler, status: int, data: dict[str, Any]) -> None:
    """Write a JSON response with the bridge's standard CORS headers."""
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler._send_cors_headers()
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header(
        "Access-Control-Allow-Headers", "Content-Type, X-Bago-Token, X-Bago-Channel"
    )
    handler.end_headers()
    handler.wfile.write(json.dumps(json_safe(data), ensure_ascii=False).encode("utf-8"))


def send_bytes(handler, status: int, content_type: str, data: bytes) -> None:
    """Write a raw byte response (e.g. static file)."""
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_body(handler, max_bytes: int) -> dict[str, Any]:
    """Parse a JSON request body with a hard size cap.

    Returns {} on missing Content-Length or malformed JSON. Returns
    {"_error": "payload_too_large", ...} if the body exceeds max_bytes
    (the body is drained before returning so the client can finish writing
    without the server tearing down the socket mid-stream).
    """
    try:
        length = int(handler.headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        return {}
    if length < 0:
        return {}
    if length > max_bytes:
        try:
            remaining = length
            while remaining > 0:
                chunk = handler.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except Exception:
            pass
        return {"_error": "payload_too_large", "_max_bytes": max_bytes}
    if length:
        data = handler.rfile.read(length).decode("utf-8")
        try:
            parsed = json.loads(data)
            return parsed if isinstance(parsed, dict) else {"_value": parsed}
        except json.JSONDecodeError:
            pass
    return {}
