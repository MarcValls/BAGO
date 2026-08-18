from __future__ import annotations

import json
from pathlib import Path

from handlers_router import restore_session_model, restore_session_reasoning
from handlers_router import handle_auto


class FakeManager:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.provider = "ollama-local"
        self.model = "llama3.2:3b"
        self.reasoning_depth = "normal"
        self.reasoning_effort = "low"
        self.switches: list[tuple[str, str, bool]] = []

    def switch(self, provider: str, model: str, force: bool = False):
        self.switches.append((provider, model, force))
        self.provider = provider
        self.model = model
        return {"ok": True}


class AutoRouterManager(FakeManager):
    def list_model_catalog(self):
        return [
            {
                "id": "local-fast",
                "model_id": "local-fast",
                "wire_name": "local-fast",
                "provider": "ollama-local",
                "context_tokens": 32768,
                "best_for": "general",
                "available": True,
            },
            {
                "id": "cloud-pro",
                "model_id": "cloud-pro",
                "wire_name": "cloud-pro",
                "provider": "openrouter",
                "context_tokens": 128000,
                "best_for": "general",
                "available": True,
            },
        ]

    def provider_availability(self):
        return [
            {
                "name": "openrouter",
                "configured": True,
                "healthy": True,
                "usable": True,
                "available_tokens": 9000,
                "token_source": "provider-quota",
                "token_limited": False,
                "models": ["cloud-pro"],
                "detail": "ready",
            },
            {
                "name": "ollama-local",
                "configured": True,
                "healthy": True,
                "usable": True,
                "available_tokens": 1200,
                "token_source": "provider-quota",
                "token_limited": False,
                "models": ["local-fast"],
                "detail": "ready",
            },
        ]


class FakeHandler:
    def __init__(self, state_root: Path, manager):
        self.state_root = state_root
        self.session_mgr = manager
        self.response = None


def _send_json(handler, status_code, payload):
    handler.response = (status_code, payload)


def test_restore_session_model_reapplies_persisted_provider_and_model(tmp_path: Path):
    (tmp_path / ".bago_session_model.json").write_text(
        json.dumps({"model": "copilot/gpt-5.4-mini"}), encoding="utf-8",
    )
    manager = FakeManager(tmp_path)

    report = restore_session_model(manager)

    assert report["ok"] is True
    assert report["restored"] is True
    assert manager.switches == [("copilot", "gpt-5.4-mini", True)]
    assert (manager.provider, manager.model) == ("copilot", "gpt-5.4-mini")


def test_restore_session_reasoning_reapplies_persisted_depth(tmp_path: Path):
    (tmp_path / ".bago_reasoning_depth.json").write_text(
        json.dumps({"depth": "maxima"}), encoding="utf-8",
    )
    manager = FakeManager(tmp_path)

    report = restore_session_reasoning(manager)

    assert report["ok"] is True
    assert report["restored"] is True
    assert manager.reasoning_depth == "maxima"
    assert manager.reasoning_effort == "xhigh"


def test_handle_auto_switch_picks_provider_with_more_available_tokens(tmp_path: Path, monkeypatch):
    manager = AutoRouterManager(tmp_path)
    handler = FakeHandler(tmp_path, manager)
    monkeypatch.setattr("handlers_router._state_root", lambda _handler: tmp_path)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    monkeypatch.setattr("event_bus.emit", lambda *_args, **_kwargs: None)

    (tmp_path / ".bago_model_selection.json").write_text(json.dumps({
        "entries": [
            {
                "provider": "ollama-local",
                "model_id": "local-fast",
                "wire_name": "local-fast",
                "context_tokens": 32768,
                "best_for": "general",
                "available": True,
                "selected": True,
            },
            {
                "provider": "openrouter",
                "model_id": "cloud-pro",
                "wire_name": "cloud-pro",
                "context_tokens": 128000,
                "best_for": "general",
                "available": True,
                "selected": True,
            },
        ],
        "auto_switch": False,
        "last_pick": "",
        "last_pick_at": "",
    }), encoding="utf-8")

    handle_auto(handler, {"enabled": True})

    assert handler.response is not None
    assert handler.response[0] == 200
    assert handler.response[1]["picked"] == "openrouter/cloud-pro"
    assert manager.switches[-1] == ("openrouter", "cloud-pro", True)
