"""tests/test_api_origin_protection.py — Origin execution boundary for mutating API methods.

Regression coverage for the backend audit remediation item:
- Disallowed browser Origin must be rejected before body read / dispatch.
- Tokenless and authenticated modes both enforce the origin boundary.
- Native originless calls and configured/trusted local origins remain allowed.
- Origin:null is rejected.
- Content-Type is not the gate; an untrusted Origin with text/plain JSON is still blocked.
- HTTP 403 is used exclusively for the origin policy; 401 remains token auth.

Imports are kept inside helpers/fixtures because the project conftest clears
bago modules between tests; module-level imports would become stale references.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from api_auth import LOCAL_CORS_ORIGINS


_DISALLOWED_ORIGIN = "http://evil.example"
_TRUSTED_LOCAL_ORIGIN = "http://localhost:5173"  # member of LOCAL_CORS_ORIGINS
_CONFIGURED_ORIGIN = "https://trusted-ui.example"
_API_TOKEN = "test-token-123"


class _FakeLogger:
    def __init__(self):
        self.entries: list[tuple[str, str, dict[str, Any]]] = []

    def _emit(self, level: str, event: str, **fields: Any) -> None:
        self.entries.append((level, event, fields))

    def debug(self, event: str, **fields: Any) -> None:
        self._emit("DEBUG", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit("INFO", event, **fields)

    def warn(self, event: str, **fields: Any) -> None:
        self._emit("WARN", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit("ERROR", event, **fields)


def _fail_reader() -> dict[str, Any]:
    raise AssertionError("read_body must not be called for origin-blocked requests")


def _make_handler_class(bridge, extra_cors: set[str] | frozenset[str] | None = None):
    """Build an unbound handler subclass that captures response bytes."""

    class _CaptureHandler(bridge.BagoAPIHandler):
        def __init__(
            self,
            path: str = "/test",
            headers: dict[str, str] | None = None,
            api_token: str = "",
        ) -> None:
            self.client_address = ("127.0.0.1", 12345)
            self.request_version = "HTTP/1.1"
            self.protocol_version = "HTTP/1.1"
            self.close_connection = False
            self.path = path
            self.headers = headers or {}
            self.wfile = io.BytesIO()
            self.api_token = api_token
            self._status: int | None = None
            self._body_reads = 0
            self._dispatched = False
            self._dispatch_body: Any = None

        def send_response(self, code: int, message: str | None = None) -> None:
            self._status = code
            super().send_response(code, message)

        # Avoid requiring a parsed request line; we only need status capture.
        def log_request(self, code: str = "-", size: str = "-") -> None:
            pass

        def _read_body(self) -> dict[str, Any]:
            self._body_reads += 1
            return {"_test": True}

        def _send_ok(self) -> None:
            self._send_json(200, {"ok": True})

    if extra_cors:
        _CaptureHandler.extra_cors_origins = frozenset(extra_cors)
    return _CaptureHandler


def _response(handler) -> tuple[int, dict[str, Any] | None]:
    raw = handler.wfile.getvalue()
    _, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        return handler._status or 0, None
    try:
        return handler._status or 0, json.loads(body.decode("utf-8"))
    except Exception:
        return handler._status or 0, None


def _make_dispatch(name: str):
    """Return a fake resolver that records dispatch and emits a 200 response."""
    if name == "DELETE":
        def _resolve_delete(handler, path: str):
            handler._dispatched = True
            return (True, lambda h: h._send_ok())
        return _resolve_delete

    def _resolve(handler, path: str, body: dict[str, Any] | None = None):
        handler._dispatched = True
        handler._dispatch_body = body
        return (True, lambda h, b=None: h._send_ok())
    return _resolve


class _PatchedEnv:
    def __init__(self, bridge, api_dispatch, logger: _FakeLogger):
        self.bridge = bridge
        self.api_dispatch = api_dispatch
        self.logger = logger


@pytest.fixture
def env(monkeypatch):
    """Import bridge/api_dispatch fresh, then patch helpers for the test."""
    import bridge
    import api_dispatch

    logger = _FakeLogger()
    monkeypatch.setattr(bridge, "get_logger", lambda: logger)

    # do_POST uses top-level imports from bridge.py
    monkeypatch.setattr(bridge, "resolve_post", _make_dispatch("POST"), raising=False)
    monkeypatch.setattr(bridge, "resolve_router", lambda *a, **kw: (False, None), raising=False)
    monkeypatch.setattr(bridge, "handle_legacy_alias", lambda *a, **kw: False, raising=False)
    # do_PUT / doDELETE import resolve_* at call time from the api_dispatch module
    monkeypatch.setattr(api_dispatch, "resolve_put", _make_dispatch("PUT"), raising=False)
    monkeypatch.setattr(api_dispatch, "resolve_delete", _make_dispatch("DELETE"), raising=False)
    return _PatchedEnv(bridge, api_dispatch, logger)


# ── Disallowed origins must be rejected first ───────────────────────────────


def test_post_disallowed_origin_tokenless_rejected_before_body_and_dispatch(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={"Origin": _DISALLOWED_ORIGIN, "Content-Type": "application/json"},
        api_token="",
    )
    h._read_body = _fail_reader
    h.do_POST()
    status, body = _response(h)
    assert status == 403
    assert body and "Origin" in body.get("error", "")
    assert not h._dispatched
    assert h._body_reads == 0


def test_post_disallowed_origin_authenticated_still_rejected(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={
            "Origin": _DISALLOWED_ORIGIN,
            "X-Bago-Token": _API_TOKEN,
            "Content-Type": "application/json",
        },
        api_token=_API_TOKEN,
    )
    h._read_body = _fail_reader
    h.do_POST()
    status, body = _response(h)
    assert status == 403
    assert not h._dispatched
    assert h._body_reads == 0


def test_post_origin_null_rejected(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={"Origin": "null", "Content-Type": "application/json"},
        api_token="",
    )
    h._read_body = _fail_reader
    h.do_POST()
    status, _ = _response(h)
    assert status == 403
    assert not h._dispatched
    assert h._body_reads == 0


def test_post_text_plain_untrusted_origin_rejected_without_content_type_check(env):
    """The origin gate runs before body parsing; Content-Type application/json is not required."""
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={"Origin": _DISALLOWED_ORIGIN, "Content-Type": "text/plain"},
        api_token="",
    )
    h._read_body = _fail_reader
    h.do_POST()
    status, _ = _response(h)
    assert status == 403
    assert not h._dispatched
    assert h._body_reads == 0


def test_put_disallowed_origin_rejected(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/agents/a-1",
        headers={"Origin": _DISALLOWED_ORIGIN, "Content-Type": "application/json"},
        api_token=_API_TOKEN,
    )
    h._read_body = _fail_reader
    h.do_PUT()
    status, _ = _response(h)
    assert status == 403
    assert not h._dispatched
    assert h._body_reads == 0


def test_delete_disallowed_origin_rejected(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/agents/a-1",
        headers={"Origin": _DISALLOWED_ORIGIN, "X-Bago-Token": _API_TOKEN},
        api_token=_API_TOKEN,
    )
    h.do_DELETE()
    status, _ = _response(h)
    assert status == 403
    assert not h._dispatched


# ── Allowed origins / native callers proceed ──────────────────────────────────


def test_post_native_originless_tokenless_proceeds(env):
    H = _make_handler_class(env.bridge)
    h = H(path="/test", headers={"Content-Type": "application/json"}, api_token="")
    h.do_POST()
    status, body = _response(h)
    assert status == 200
    assert body == {"ok": True}
    assert h._dispatched
    assert h._body_reads == 1


def test_post_trusted_local_origin_tokenless_proceeds(env):
    assert _TRUSTED_LOCAL_ORIGIN in LOCAL_CORS_ORIGINS
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={"Origin": _TRUSTED_LOCAL_ORIGIN, "Content-Type": "application/json"},
        api_token="",
    )
    h.do_POST()
    status, _ = _response(h)
    assert status == 200
    assert h._dispatched


def test_post_configured_extra_origin_tokenless_proceeds(env):
    H = _make_handler_class(env.bridge, extra_cors={_CONFIGURED_ORIGIN})
    h = H(
        path="/test",
        headers={"Origin": _CONFIGURED_ORIGIN, "Content-Type": "application/json"},
        api_token="",
    )
    h.do_POST()
    status, _ = _response(h)
    assert status == 200
    assert h._dispatched


# ── Auth boundary remains 401 and is only checked after origin passes ─────────


def test_post_allowed_origin_missing_token_in_auth_mode_returns_401(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={"Origin": _TRUSTED_LOCAL_ORIGIN, "Content-Type": "application/json"},
        api_token=_API_TOKEN,
    )
    h._read_body = _fail_reader
    h.do_POST()
    status, body = _response(h)
    assert status == 401
    assert body and "Token" in body.get("error", "")
    assert not h._dispatched
    assert h._body_reads == 0


def test_post_allowed_origin_valid_token_proceeds(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/test",
        headers={
            "Origin": _TRUSTED_LOCAL_ORIGIN,
            "Content-Type": "application/json",
            "X-Bago-Token": _API_TOKEN,
        },
        api_token=_API_TOKEN,
    )
    h.do_POST()
    status, body = _response(h)
    assert status == 200
    assert body == {"ok": True}
    assert h._dispatched


def test_put_allowed_origin_valid_token_proceeds(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/agents/a-1",
        headers={
            "Origin": _TRUSTED_LOCAL_ORIGIN,
            "Content-Type": "application/json",
            "X-Bago-Token": _API_TOKEN,
        },
        api_token=_API_TOKEN,
    )
    h.do_PUT()
    status, _ = _response(h)
    assert status == 200
    assert h._dispatched


def test_delete_allowed_origin_valid_token_proceeds(env):
    H = _make_handler_class(env.bridge)
    h = H(
        path="/agents/a-1",
        headers={"Origin": _TRUSTED_LOCAL_ORIGIN, "X-Bago-Token": _API_TOKEN},
        api_token=_API_TOKEN,
    )
    h.do_DELETE()
    status, _ = _response(h)
    assert status == 200
    assert h._dispatched
