from __future__ import annotations

import json
from pathlib import Path

import authorization_boundary as auth

from handlers_router import (
    handle_auto,
    handle_session_model,
    handle_session_model_get,
    restore_session_model,
    restore_session_reasoning,
)


class FakeManager:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.provider = "ollama-local"
        self.model = "llama3.2:3b"
        self.session_id = "router-session"
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
        self.headers = {"X-Bago-Channel": "ui-react"}
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


def test_session_model_post_get_and_clear_round_trip(tmp_path: Path, monkeypatch):
    manager = FakeManager(tmp_path)
    handler = FakeHandler(tmp_path, manager)
    monkeypatch.setattr("handlers_router._state_root", lambda _handler: tmp_path)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    monkeypatch.setattr("event_bus.emit", lambda *_args, **_kwargs: None)

    handle_session_model(handler, {"model": "copilot/gpt-5.4-mini"})

    assert handler.response == (200, {
        "ok": True,
        "session_model": "copilot/gpt-5.4-mini",
        "effective_provider": "copilot",
        "effective_model": "gpt-5.4-mini",
    })
    assert json.loads((tmp_path / ".bago_session_model.json").read_text(encoding="utf-8")) == {
        "model": "copilot/gpt-5.4-mini",
        "automatic_provider": "ollama-local",
        "automatic_model": "llama3.2:3b",
    }

    handle_session_model_get(handler)

    assert handler.response is not None
    assert handler.response[0] == 200
    assert handler.response[1]["session_model"] == "copilot/gpt-5.4-mini"
    assert handler.response[1]["effective_provider"] == "copilot"
    assert handler.response[1]["effective_model"] == "gpt-5.4-mini"

    switches_before_clear = list(manager.switches)
    handle_session_model(handler, {
        "model": None,
        "authorization_action": "challenge",
        "interaction_id": "router-clear",
    })
    assert handler.response[0] == 200
    challenge = handler.response[1]["authorization"]["challenge"]
    assert handler.response[1]["authorization"]["state"] == "challenge"
    assert list(manager.switches) == switches_before_clear
    assert (tmp_path / ".bago_session_model.json").exists()

    handle_session_model(handler, {
        "model": None,
        "authorization_action": "approve",
        "interaction_id": "router-clear",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    assert handler.response[0] == 200
    authorization = handler.response[1]["authorization"]
    assert authorization["state"] == "authorized"
    permit = authorization["permit"]["token"]

    handle_session_model(handler, {
        "model": None,
        "authorization_action": "execute",
        "interaction_id": "router-clear",
        "authorization_permit": permit,
    })
    assert handler.response[0] == 200
    assert handler.response[1]["ok"] is True
    assert handler.response[1]["session_model"] is None
    assert handler.response[1]["cleared"] is True
    assert handler.response[1]["receipt"]["effect_id"] == "state.delete"
    assert handler.response[1]["receipt"]["deleted"] is True
    assert handler.response[1]["authorization"]["state"] == "consumed"
    assert manager.switches[-1] == ("ollama-local", "llama3.2:3b", True)
    assert not (tmp_path / ".bago_session_model.json").exists()

    handle_session_model_get(handler)
    assert handler.response == (200, {
        "ok": True,
        "session_model": None,
        "effective_provider": "ollama-local",
        "effective_model": "llama3.2:3b",
    })


def test_session_model_clear_requires_authorization_before_switch_or_delete(tmp_path: Path, monkeypatch):
    manager = FakeManager(tmp_path)
    handler = FakeHandler(tmp_path, manager)
    monkeypatch.setattr("handlers_router._state_root", lambda _handler: tmp_path)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_serializers.send_json", _send_json)

    override = tmp_path / ".bago_session_model.json"
    override.write_text(json.dumps({
        "model": "copilot/gpt-5.4-mini",
        "automatic_provider": "ollama-local",
        "automatic_model": "llama3.2:3b",
    }), encoding="utf-8")

    handle_session_model(handler, {"model": None})

    assert handler.response[0] == 403
    assert handler.response[1]["code"] == "authorization_action_required"
    assert manager.switches == []
    assert override.exists()


def test_session_model_clear_switch_failure_preserves_override(tmp_path: Path, monkeypatch):
    class FailingManager(FakeManager):
        def switch(self, provider: str, model: str, force: bool = False):
            self.switches.append((provider, model, force))
            return {"ok": False, "error": "switch blocked"}

    manager = FailingManager(tmp_path)
    handler = FakeHandler(tmp_path, manager)
    monkeypatch.setattr("handlers_router._state_root", lambda _handler: tmp_path)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_serializers.send_json", _send_json)

    override = tmp_path / ".bago_session_model.json"
    override.write_text(json.dumps({
        "model": "copilot/gpt-5.4-mini",
        "automatic_provider": "openrouter",
        "automatic_model": "cloud-pro",
    }), encoding="utf-8")

    handle_session_model(handler, {
        "model": None,
        "authorization_action": "challenge",
        "interaction_id": "router-switch-failure",
    })
    challenge = handler.response[1]["authorization"]["challenge"]
    handle_session_model(handler, {
        "model": None,
        "authorization_action": "approve",
        "interaction_id": "router-switch-failure",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = handler.response[1]["authorization"]["permit"]["token"]

    handle_session_model(handler, {
        "model": None,
        "authorization_action": "execute",
        "interaction_id": "router-switch-failure",
        "authorization_permit": permit,
    })

    assert handler.response == (400, {"ok": False, "error": "switch blocked"})
    assert override.exists()
    assert json.loads(override.read_text(encoding="utf-8"))["model"] == "copilot/gpt-5.4-mini"


def test_session_model_clear_invalid_permit_never_deletes_override(tmp_path: Path, monkeypatch):
    manager = FakeManager(tmp_path)
    handler = FakeHandler(tmp_path, manager)
    monkeypatch.setattr("handlers_router._state_root", lambda _handler: tmp_path)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_serializers.send_json", _send_json)

    override = tmp_path / ".bago_session_model.json"
    override.write_text(json.dumps({
        "model": "copilot/gpt-5.4-mini",
        "automatic_provider": "ollama-local",
        "automatic_model": "llama3.2:3b",
    }), encoding="utf-8")

    handle_session_model(handler, {
        "model": None,
        "authorization_action": "execute",
        "authorization_permit": "not-a-permit",
    })

    assert handler.response[0] == 403
    assert handler.response[1]["code"] == "authorization_permit_invalid"
    assert override.exists()


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
