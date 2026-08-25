"""Smoke tests for handlers_agents."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import handlers_agents
import api_dispatch


class FakeHandler:
    def __init__(self):
        self._status = 200
        self._body = b""

    def send_response(self, status: int) -> None:
        self._status = status

    def send_header(self, key: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def _send_cors_headers(self) -> None:
        pass

    @property
    def wfile(self):
        h = self

        class _Writer:
            def write(self, data: bytes) -> None:
                h._body += data

        return _Writer()

    @property
    def response(self):
        return {"status": self._status, "body": json.loads(self._body.decode("utf-8")) if self._body else None}


@pytest.fixture
def isolated_agents_state(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp) / "agents"
        monkeypatch.setattr(handlers_agents, "AGENTS_STATE_DIR", state_dir)
        yield state_dir


def test_handle_get_list_returns_empty_registry(isolated_agents_state):
    handler = FakeHandler()
    handlers_agents.handle_get_list(handler)
    resp = handler.response
    assert resp["status"] == 200
    assert resp["body"]["ok"] is True
    assert resp["body"]["agents"] == []


def test_handle_get_unknown_agent_returns_404(isolated_agents_state):
    handler = FakeHandler()
    handlers_agents.handle_get(handler, "unknown-id")
    resp = handler.response
    assert resp["status"] == 404
    assert resp["body"]["ok"] is False


def test_handle_post_creates_agent(isolated_agents_state):
    handler = FakeHandler()
    handlers_agents.handle_post(handler, {"name": "Test Agent"})
    resp = handler.response
    assert resp["status"] == 201
    assert resp["body"]["ok"] is True
    assert resp["body"]["agent"]["name"] == "Test Agent"
    assert resp["body"]["agent"]["id"]


def test_safe_handler_catches_registry_corruption(isolated_agents_state, monkeypatch):
    handler = FakeHandler()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(handlers_agents, "_load_agents_registry", boom)
    handlers_agents.handle_get_list(handler)
    resp = handler.response
    assert resp["status"] == 500
    assert resp["body"]["ok"] is False
    assert resp["body"]["code"] == "INTERNAL_ERROR"


def test_dispatch_invokes_agent_crud_and_duplicate_contract(isolated_agents_state):
    create_handler = FakeHandler()
    matched, create = api_dispatch.resolve_post(create_handler, "/agents", {"name": "Routed Agent"})
    assert matched and create
    create(create_handler, {"name": "Routed Agent", "model": "qwen3", "provider": "ollama-local"})
    assert create_handler.response["status"] == 201
    agent_id = create_handler.response["body"]["agent"]["id"]

    get_handler = FakeHandler()
    matched, get_agent = api_dispatch.resolve_get(get_handler, f"/agents/{agent_id}")
    assert matched and get_agent
    get_agent(get_handler)
    assert get_handler.response["body"]["agent"]["name"] == "Routed Agent"

    put_handler = FakeHandler()
    matched, put_agent = api_dispatch.resolve_put(put_handler, f"/agents/{agent_id}", {})
    assert matched and put_agent
    put_agent(put_handler, {"name": "Updated Agent", "revision": "1"})
    assert put_handler.response["body"]["agent"]["name"] == "Updated Agent"

    duplicate_handler = FakeHandler()
    matched, duplicate = api_dispatch.resolve_post(duplicate_handler, f"/agents/{agent_id}/duplicate", {})
    assert matched and duplicate
    duplicate(duplicate_handler, {})
    assert duplicate_handler.response["status"] == 201
    assert duplicate_handler.response["body"]["agent"]["name"] == "Updated Agent (copy)"

    delete_handler = FakeHandler()
    matched, delete_agent = api_dispatch.resolve_delete(delete_handler, f"/agents/{agent_id}")
    assert matched and delete_agent
    delete_agent(delete_handler)
    assert delete_handler.response == {"status": 200, "body": {"ok": True}}
