"""api_auth.py \u2014 auth + CORS helpers for the BAGO HTTP bridge.

Mixins that the BaseHTTPRequestHandler subclass uses. Pulled out of
bridge.py so that bridge.py can focus on routing, and so the auth
policy is testable in isolation (no HTTP server required).

CORS policy (mirrors the original implementation):
  - Allow localhost/127.0.0.1/[::1] implicitly (any port).
  - Allow any origin in extra_cors_origins (set from env var
    BAGO_API_CORS_ORIGINS by the server runner).

Auth policy:
  - If api_token is empty, every request is allowed (dev mode).
  - Otherwise the X-Bago-Token header must match api_token exactly.
"""

from __future__ import annotations

import os
from typing import FrozenSet
from urllib.parse import urlparse


def _load_cors_origins_from_env() -> FrozenSet[str]:
    raw = os.environ.get("BAGO_API_CORS_ORIGINS", "")
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


class BagoAuthMixin:
    """Auth + CORS policy for BagoAPIHandler.

    The handler instance is expected to expose:
      - self.api_token:    str (empty => auth disabled)
      - self.extra_cors_origins: frozenset[str] (set by the server runner)
      - self.headers:      MessageHeaders
      - self.send_header / self.end_headers
    """

    api_token: str = ""
    extra_cors_origins: FrozenSet[str] = frozenset()

    @classmethod
    def _normalized_cors_origin(cls, origin: str) -> str:
        if not origin or "\r" in origin or "\n" in origin:
            return ""
        try:
            parsed = urlparse(origin)
            port = parsed.port
        except (TypeError, ValueError):
            return ""
        if parsed.scheme not in ("http", "https"):
            return ""
        if parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
            return ""

        hostname = (parsed.hostname or "").lower()
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            safe_host = f"[{hostname}]" if ":" in hostname else hostname
            return f"{parsed.scheme}://{safe_host}{f':{port}' if port is not None else ''}"

        for allowed_origin in cls.extra_cors_origins:
            if origin == allowed_origin:
                return allowed_origin
        return ""

    @classmethod
    def _cors_origin_allowed(cls, origin: str) -> bool:
        return bool(cls._normalized_cors_origin(origin))

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed_origin = self._normalized_cors_origin(origin)
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")

    def _check_auth(self) -> bool:
        if not self.api_token:
            return True
        token = self.headers.get("X-Bago-Token", "")
        return token == self.api_token
