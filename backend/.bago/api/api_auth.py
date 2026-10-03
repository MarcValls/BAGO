"""api_auth.py \u2014 auth + CORS helpers for the BAGO HTTP bridge.

Mixins that the BaseHTTPRequestHandler subclass uses. Pulled out of
bridge.py so that bridge.py can focus on routing, and so the auth
policy is testable in isolation (no HTTP server required).

CORS policy:
  - Allow trusted local development origins.
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


LOCAL_CORS_ORIGINS: FrozenSet[str] = frozenset(
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1", "[::1]")
    for port in (3000, 4173, 5173, 5179, 8080)
)


def _valid_configured_origin(origin: str) -> bool:
    if not origin or "\r" in origin or "\n" in origin:
        return False
    try:
        parsed = urlparse(origin)
        _ = parsed.port
    except (TypeError, ValueError):
        return False
    return bool(
        parsed.scheme in ("http", "https")
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and parsed.path in ("", "/")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def _load_cors_origins_from_env() -> FrozenSet[str]:
    raw = os.environ.get("BAGO_API_CORS_ORIGINS", "")
    if not raw:
        return frozenset()
    origins = (part.strip() for part in raw.split(","))
    return frozenset(origin for origin in origins if _valid_configured_origin(origin))


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
        for allowed_origin in LOCAL_CORS_ORIGINS | cls.extra_cors_origins:
            if not _valid_configured_origin(allowed_origin):
                continue
            if origin == allowed_origin:
                return allowed_origin
        return ""

    @classmethod
    def _cors_origin_allowed(cls, origin: str) -> bool:
        return bool(cls._normalized_cors_origin(origin))

    def _origin_allowed_for_mutation(self) -> bool:
        """Execution boundary for browser-originated mutating requests.

        POST/PUT/DELETE may be issued by browsers with an ``Origin`` header.
        Only native/originless callers and explicitly trusted origins are
        allowed to drive mutations. A literal ``null`` origin, and any other
        untrusted origin, must be rejected with HTTP 403 before auth, body
        parsing, or dispatch.

        CORS response headers are a separate concern managed by
        ``_send_cors_headers``; this check is the execution gate.
        """
        origin = self.headers.get("Origin", "")
        # Native or originless callers are allowed (e.g. local scripts, Electron).
        if not origin:
            return True
        # Sandbox / opaque origins are never trusted for mutations.
        if origin == "null":
            return False
        return self._cors_origin_allowed(origin)

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
