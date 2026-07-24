from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

class FakeConfig:
    def __init__(self, providers: dict | None = None):
        self.providers = providers or {}
        self.saved: list[tuple[str, dict]] = []

    def provider_config(self, provider: str) -> dict:
        return dict(self.providers.get(provider, {}))

    def get(self, key: str, default=None):
        return default

    def set(self, key: str, value: dict) -> None:
        provider = key.split(".", 1)[1]
        self.providers[provider] = dict(value)
        self.saved.append((key, dict(value)))


class FakeCredentials:
    @staticmethod
    def required_keys(_provider: str) -> list[str]:
        return []


def test_adapter_config_reads_registered_secret_and_default_model(monkeypatch, tmp_path):
    session_module = importlib.import_module("session_adapters_mixin")
    secrets_module = importlib.import_module("secret_store")
    manager = session_module.SessionAdaptersMixin()
    manager.provider = "openrouter"
    manager.base_path = Path(tmp_path)
    manager.config = FakeConfig({
        "openrouter": {
            "enabled": True,
            "default_model": "openai/gpt-4.1-mini",
        }
    })
    manager.credentials = FakeCredentials()

    store = SimpleNamespace(get_secret=lambda key: "secret-value" if key == "providers/openrouter/api_key" else None)
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)

    config = manager._build_adapter_config("openrouter")

    assert config["api_key"] == "secret-value"
    assert config["token"] == "secret-value"
    assert config["model"] == "openai/gpt-4.1-mini"


def test_configure_updates_live_config_without_returning_secret(monkeypatch):
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    config = FakeConfig({"openrouter": {"enabled": False}})
    manager = SimpleNamespace(config=config, invalidate_providers_cache=lambda: None)
    captured: dict = {}

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(handlers, "_store_secret", lambda provider, secret: f"bago://secrets/providers/{provider}/api_key")
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda _provider: True)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: captured.update(status=status, body=body))

    handlers.handle_configure(object(), {
        "provider": "openrouter",
        "enabled": True,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "must-not-leak",
        "model": "openai/gpt-4.1-mini",
    })

    persisted = config.providers["openrouter"]
    assert captured["status"] == 200
    assert persisted["enabled"] is True
    assert persisted["default_model"] == "openai/gpt-4.1-mini"
    assert "api_key" not in persisted
    assert "must-not-leak" not in str(captured["body"])
    assert captured["body"]["config"]["has_secret"] is True


def test_provider_list_uses_only_live_adapter_registry(monkeypatch):
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    manager = SimpleNamespace(
        config=FakeConfig({"ollama-local": {"enabled": True, "base_url": "http://127.0.0.1:11434"}}),
        available_providers=lambda: [{"name": "ollama-local", "configured": True, "models": ["qwen3:8b"]}],
    )
    captured: dict = {}

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda _provider: False)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: captured.update(status=status, body=body))

    handlers.handle(object())

    providers = captured["body"]["providers"]
    assert [provider["id"] for provider in providers] == ["ollama-local"]
    assert providers[0]["models"] == ["qwen3:8b"]
    assert providers[0]["models_source"] == "session-manager"

    bootstrap_payload = handlers.build_providers_payload(manager)
    assert bootstrap_payload == captured["body"]
