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

    @staticmethod
    def _cors_origin_allowed(origin: str) -> bool:
        if not origin:
            return False
        try:
            parsed = urlparse(origin)
        except Exception:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            return True
        return origin in BagoAuthMixin.extra_cors_origins

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if self._cors_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _check_auth(self) -> bool:
        if not self.api_token:
            return True
        token = self.headers.get("X-Bago-Token", "")
        return token == self.api_token
