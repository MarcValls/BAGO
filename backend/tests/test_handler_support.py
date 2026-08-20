"""Tests for the shared API handler support helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import handler_support as support


class FakeRequestHandler:
    """Minimal stand-in for BaseHTTPRequestHandler that records send_json calls."""

    def __init__(self):
        self.sent = []

    def send_response(self, status: int) -> None:
        self._status = status

    def send_header(self, key: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    @property
    def wfile(self):
        class _Writer:
            def __init__(self, handler):
                self._handler = handler

            def write(self, data: bytes) -> None:
                self._handler.sent.append((self._handler._status, data))

        return _Writer(self)

    def _send_cors_headers(self) -> None:
        pass


def test_safe_handler_returns_payload_on_success():
    handler = FakeRequestHandler()

    @support.safe_handler
    def handle_ok(h, body):
        support.send_error(h, 200, "ok", code="OK")

    handle_ok(handler, {})
    assert len(handler.sent) == 1
    status, payload_bytes = handler.sent[0]
    assert status == 200
    payload = json.loads(payload_bytes.decode("utf-8"))
    assert payload == {"ok": False, "error": "ok", "code": "OK"}


def test_safe_handler_catches_unhandled_exceptions():
    handler = FakeRequestHandler()

    @support.safe_handler
    def handle_boom(h, body):
        raise RuntimeError("something went wrong")

    # Should not raise — the decorator catches it.
    handle_boom(handler, {})

    assert len(handler.sent) == 1
    status, payload_bytes = handler.sent[0]
    assert status == 500
    payload = json.loads(payload_bytes.decode("utf-8"))
    assert payload["ok"] is False
    assert payload["code"] == "INTERNAL_ERROR"
    assert "Internal server error" in payload["error"]
