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


class FakeGatewaySecretStore:
    def __init__(self, root: Path, initial: dict[str, str] | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for key, value in (initial or {}).items():
            self.path_for_key(key).write_bytes(self.protect_secret(value))

    def path_for_key(self, key: str) -> Path:
        safe = key.lower().replace("_", "-").replace("/", "-")
        return self.root / f"{safe}.bin"

    @staticmethod
    def protect_secret(value: str) -> bytes:
        return value.encode("utf-8")

    def get_secret(self, key: str) -> str | None:
        path = self.path_for_key(key)
        if not path.exists():
            return None
        return path.read_bytes().decode("utf-8")


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


def test_registered_secret_overrides_legacy_credential(monkeypatch, tmp_path):
    session_module = importlib.import_module("session_adapters_mixin")
    secrets_module = importlib.import_module("secret_store")
    manager = session_module.SessionAdaptersMixin()
    manager.provider = "ollama-cloud"
    manager.base_path = Path(tmp_path)
    manager.config = FakeConfig({"ollama-cloud": {"enabled": True}})
    manager.config.get = lambda key, default=None: default
    manager.credentials = SimpleNamespace(
        required_keys=lambda _provider: ["OLLAMA_CLOUD_KEY"],
        get=lambda _provider, _key: "legacy-secret",
    )
    store = SimpleNamespace(get_secret=lambda key: "canonical-secret" if key == "providers/ollama-cloud/api_key" else None)
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)

    config = manager._build_adapter_config("ollama-cloud")

    assert config["api_key"] == "canonical-secret"
    assert config["token"] == "canonical-secret"
    assert config["fallback_api_key"] == "legacy-secret"


def test_configure_requires_strong_gateway_authorization_without_disclosing_secret(monkeypatch, tmp_path):
    auth = importlib.import_module("authorization_boundary")
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    secrets_module = importlib.import_module("secret_store")
    config = FakeConfig({"openrouter": {"enabled": False}})
    manager = SimpleNamespace(
        session_id="provider-config-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    captured: list[tuple[int, dict]] = []
    secret_key = "providers/openrouter/api_key"
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    store = FakeGatewaySecretStore(tmp_path / "user" / "secrets")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    secret = "must-not-leak"
    base_body = {
        "provider": "openrouter",
        "enabled": True,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": secret,
        "model": "openai/gpt-4.1-mini",
        "interaction_id": "provider-config-interaction",
    }

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda provider: store.get_secret(f"providers/{provider}/api_key") is not None)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: captured.append((status, body)))

    handlers.handle_configure(handler, {**base_body, "authorization_action": "challenge"})
    challenge = captured[-1][1]["authorization"]["challenge"]
    assert captured[-1][0] == 200
    assert config.saved == []
    assert store.get_secret(secret_key) is None
    assert secret not in str(captured[-1][1])

    handlers.handle_configure(handler, {
        **base_body,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = captured[-1][1]["authorization"]["permit"]["token"]
    assert captured[-1][0] == 200
    assert config.saved == []
    assert store.get_secret(secret_key) is None
    assert secret not in str(captured[-1][1])

    handlers.handle_configure(handler, {
        **base_body,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    persisted = config.providers["openrouter"]
    assert captured[-1][0] == 200
    assert persisted["enabled"] is True
    assert persisted["default_model"] == "openai/gpt-4.1-mini"
    assert "api_key" not in persisted
    assert store.get_secret(secret_key) == secret
    assert secret not in str(captured[-1][1])
    assert captured[-1][1]["config"]["has_secret"] is True
    assert captured[-1][1]["credential_receipt"]["effect_id"] == "credential.write"
    assert secret not in (tmp_path / "authorization" / "authorization" / "ledger.json").read_text(encoding="utf-8")


def test_configure_rejects_tampered_fingerprint_and_noninteractive_approval(monkeypatch, tmp_path):
    auth = importlib.import_module("authorization_boundary")
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    secrets_module = importlib.import_module("secret_store")
    config = FakeConfig({"openrouter": {"enabled": False}})
    manager = SimpleNamespace(
        session_id="provider-tamper-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    responses: list[tuple[int, dict]] = []
    secret_key = "providers/openrouter/api_key"
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    store = FakeGatewaySecretStore(tmp_path / "user" / "secrets")
    common = {
        "provider": "openrouter",
        "enabled": True,
        "model": "model-a",
        "api_key": "provider-secret",
        "interaction_id": "provider-tamper-interaction",
    }
    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda provider: store.get_secret(f"providers/{provider}/api_key") is not None)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))

    noninteractive = SimpleNamespace(headers={"X-Bago-Channel": "api"})
    handlers.handle_configure(noninteractive, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    handlers.handle_configure(noninteractive, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "authorization_user_origin_unverified"
    assert store.get_secret(secret_key) is None
    assert config.saved == []

    interactive = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    handlers.handle_configure(interactive, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    handlers.handle_configure(interactive, {
        **common,
        "model": "model-b",
        "authorization_action": "execute",
        "authorization_permit": permit,
    })
    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert store.get_secret(secret_key) is None
    assert config.saved == []


def test_configure_clear_secret_executes_only_after_approval(monkeypatch, tmp_path):
    auth = importlib.import_module("authorization_boundary")
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    secrets_module = importlib.import_module("secret_store")
    config = FakeConfig({"openrouter": {"enabled": True, "secret_ref": "bago://secrets/providers/openrouter/api_key"}})
    manager = SimpleNamespace(
        session_id="provider-delete-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    responses: list[tuple[int, dict]] = []
    secret_key = "providers/openrouter/api_key"
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    store = FakeGatewaySecretStore(tmp_path / "user" / "secrets", {secret_key: "existing-secret"})
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    common = {
        "provider": "openrouter",
        "clear_secret": True,
        "interaction_id": "provider-delete-interaction",
    }
    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda provider: store.get_secret(f"providers/{provider}/api_key") is not None)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))

    handlers.handle_configure(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert store.get_secret(secret_key) == "existing-secret"
    assert config.saved == []
    handlers.handle_configure(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    assert store.get_secret(secret_key) == "existing-secret"
    assert config.saved == []
    handlers.handle_configure(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert store.get_secret(secret_key) is None
    assert "secret_ref" not in config.providers["openrouter"]
    assert "existing-secret" not in str(responses[-1][1])


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
    assert providers[0]["canonical_id"] == "ollama-local"
    assert providers[0]["model_discovery"] == {"type": "ollama_tags", "path": "/api/tags"}
    assert any(entry["id"] == "copilot" for entry in captured["body"]["catalog"])

    bootstrap_payload = handlers.build_providers_payload(manager)
    assert bootstrap_payload == captured["body"]


def test_provider_catalog_resolves_legacy_aliases():
    catalog = importlib.import_module("provider_catalog")

    descriptor = catalog.provider_descriptor("llama-cpp-local")

    assert descriptor["canonical_id"] == "cpp-local"
    assert descriptor["base_url"] == "http://localhost:8080/v1"
    assert catalog.provider_discovery("llama-cpp-local") == {
        "type": "openai_models",
        "path": "/models",
    }


def test_ollama_cloud_uses_host_url_and_ollama_discovery():
    catalog = importlib.import_module("provider_catalog")

    descriptor = catalog.provider_descriptor("ollama-cloud")

    assert descriptor["base_url"] == "https://ollama.com"
    assert descriptor["model_discovery"] == {"type": "ollama_tags", "path": "/api/tags"}
    assert catalog.normalize_provider_base_url("ollama-cloud", "https://ollama.com/api/") == "https://ollama.com"
    assert catalog.provider_base_url("ollama-cloud", {"providers": {}}) == "https://ollama.com"


class DriftingFakeConfig:
    """FakeConfig variant whose provider_config() return value drifts after
    a fixed number of reads, modeling a concurrent backend config write that
    lands between the handler's own digest snapshot and the gateway
    adapter's later, closer-to-mutation revalidation read.
    """

    def __init__(self, stable: dict, drifted: dict, drift_after_calls: int) -> None:
        self.stable = stable
        self.drifted = drifted
        self.drift_after_calls = drift_after_calls
        self.calls = 0
        self.saved: list[tuple[str, dict]] = []

    def provider_config(self, provider: str) -> dict:
        self.calls += 1
        source = self.drifted if self.calls > self.drift_after_calls else self.stable
        return dict(source.get(provider, {}))

    def get(self, key: str, default=None):
        return default

    def set(self, key: str, value: dict) -> None:
        provider = key.split(".", 1)[1]
        self.saved.append((key, dict(value)))


def test_configure_legitimate_nonsecret_update_with_secret_set_succeeds(monkeypatch, tmp_path):
    """Non-secret field changes bound into the same request as a secret set
    still succeed: the recomputed candidate (live config + this request's
    own patch) matches the authorized digest.
    """
    auth = importlib.import_module("authorization_boundary")
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    secrets_module = importlib.import_module("secret_store")
    config = FakeConfig({"openrouter": {"enabled": False, "base_url": "https://openrouter.ai/api/v1"}})
    manager = SimpleNamespace(
        session_id="provider-legit-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    responses: list[tuple[int, dict]] = []
    secret_key = "providers/openrouter/api_key"
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    store = FakeGatewaySecretStore(tmp_path / "user" / "secrets")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    secret = "legit-secret"
    common = {
        "provider": "openrouter",
        "enabled": True,
        "model": "openai/gpt-4.1-mini",
        "api_key": secret,
        "interaction_id": "provider-legit-interaction",
    }
    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda provider: store.get_secret(f"providers/{provider}/api_key") is not None)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))

    handlers.handle_configure(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    handlers.handle_configure(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    handlers.handle_configure(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    persisted = config.providers["openrouter"]
    assert persisted["enabled"] is True
    assert persisted["default_model"] == "openai/gpt-4.1-mini"
    assert "api_key" not in persisted
    assert store.get_secret(secret_key) == secret
    assert secret not in str(responses[-1][1])


def test_configure_blocks_on_live_backend_drift_between_approval_and_execute(monkeypatch, tmp_path):
    """Backend config that drifts (e.g. a concurrent write) between the
    handler's digest snapshot and the gateway adapter's own revalidation
    read must block the credential write with zero secret/config mutation,
    even though the same-request non-secret patch was itself authorized.
    """
    auth = importlib.import_module("authorization_boundary")
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    secrets_module = importlib.import_module("secret_store")

    stable = {"openrouter": {"enabled": False, "base_url": "https://openrouter.ai/api/v1"}}
    drifted = {"openrouter": {"enabled": False, "base_url": "https://drifted.example/api"}}
    # 3 handler-level reads happen before the gateway adapter's own read
    # (one per challenge/approve/execute handle_configure call); the 4th
    # read is the adapter's revalidation, immediately before SecretStore
    # access, and it observes the drifted value.
    config = DriftingFakeConfig(stable, drifted, drift_after_calls=3)
    manager = SimpleNamespace(
        session_id="provider-drift-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    responses: list[tuple[int, dict]] = []
    secret_key = "providers/openrouter/api_key"
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    store = FakeGatewaySecretStore(tmp_path / "user" / "secrets")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    secret = "must-not-be-persisted"
    common = {
        "provider": "openrouter",
        "enabled": True,
        "api_key": secret,
        "interaction_id": "provider-drift-interaction",
    }
    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda provider: store.get_secret(f"providers/{provider}/api_key") is not None)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))

    handlers.handle_configure(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    handlers.handle_configure(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]

    handlers.handle_configure(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "credential_write_configuration_changed"
    assert store.get_secret(secret_key) is None
    assert config.saved == []
    assert secret not in str(responses[-1][1])


def test_configure_normalizes_ollama_api_suffix(monkeypatch):
    handlers = importlib.import_module("handlers_providers")
    serializers = importlib.import_module("api_serializers")
    config = FakeConfig({"ollama-cloud": {"enabled": False}})
    manager = SimpleNamespace(config=config, invalidate_providers_cache=lambda: None)
    captured: dict = {}

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda _provider: False)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: captured.update(status=status, body=body))

    handlers.handle_configure(object(), {
        "provider": "ollama-cloud",
        "enabled": True,
        "base_url": "https://ollama.com/api/",
    })

    assert captured["status"] == 200
    assert config.providers["ollama-cloud"]["base_url"] == "https://ollama.com"


def test_cli_authenticated_provider_is_registered_without_copying_token(monkeypatch):
    session_module = importlib.import_module("session_adapters_mixin")

    class FakeAdapter:
        cli_authenticated = True

        def __init__(self, config=None):
            pass

        def is_configured(self):
            return True

    manager = session_module.SessionAdaptersMixin()
    manager.provider = "ollama-local"
    manager.base_path = Path(".")
    manager.config = FakeConfig({"codex": {"enabled": False}})
    manager.credentials = FakeCredentials()
    manager._providers_cache = None
    manager._providers_cache_at = 0.0
    manager._providers_cache_ttl = 0.0
    manager.list_model_catalog = lambda provider=None: []
    monkeypatch.setattr(session_module, "ADAPTER_REGISTRY", {"codex": FakeAdapter})

    providers = manager.available_providers()

    assert len(providers) == 1
    assert {key: providers[0][key] for key in ("name", "configured", "models")} == {"name": "codex", "configured": True, "models": []}
    assert providers[0]["usable"] is True
    assert manager.config.providers["codex"]["enabled"] is True
    assert manager.config.providers["codex"]["auth_source"] == "cli"
    assert manager.config.providers["codex"]["transport"] == "cli"
    assert "api_key" not in manager.config.providers["codex"]
