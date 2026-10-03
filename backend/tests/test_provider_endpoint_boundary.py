from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _module(name: str):
    return importlib.import_module(name)


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
    def __init__(self, keys: dict | None = None):
        self._keys = keys or {}

    def required_keys(self, _provider: str) -> list[str]:
        return []

    def get(self, _provider: str, _key: str) -> str:
        return ""


class LegacyCredentials(FakeCredentials):
    def __init__(self, ollama_cloud_url: str = ""):
        super().__init__()
        self.ollama_cloud_url = ollama_cloud_url

    def required_keys(self, provider: str) -> list[str]:
        if provider == "ollama-cloud":
            return ["OLLAMA_CLOUD_KEY"]
        return []

    def get(self, provider: str, key: str) -> str:
        if provider == "ollama-cloud" and key == "OLLAMA_CLOUD_KEY":
            return "legacy-key"
        return ""


class FakeSecretStore:
    def __init__(self, root: Path | None = None, secrets: dict[str, str] | None = None):
        self.root = Path(root or Path("/dev/null"))
        self.root.mkdir(parents=True, exist_ok=True)
        for key, value in (secrets or {}).items():
            self.path_for_key(key).write_bytes(self.protect_secret(value))

    def get_secret(self, key: str) -> str | None:
        path = self.path_for_key(key)
        if not path.exists():
            return None
        return path.read_bytes().decode("utf-8")

    def protect_secret(self, value: str) -> bytes:
        return value.encode("utf-8")

    def path_for_key(self, key: str) -> Path:
        safe = key.lower().replace("_", "-").replace("/", "-")
        return self.root / f"{safe}.bin"


class _InterceptedResponse:
    def __init__(self, url: str, status: int = 200, body: bytes = b'{}'):
        self.url = url
        self.status = status
        self._body = body
        self.headers = {"content-type": "application/json"}

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self._body
        chunk = self._body[:amount]
        self._body = self._body[amount:]
        return chunk

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Catalog-level validation
# ──────────────────────────────────────────────────────────────────────────────


def test_canonical_url_matches_ignores_trailing_slash_and_compares_origin_port_path():
    catalog = _module("provider_catalog")

    assert catalog.canonical_url_matches("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1/")
    assert catalog.canonical_url_matches("https://openrouter.ai/api/v1/", "https://openrouter.ai/api/v1")
    assert not catalog.canonical_url_matches("https://openrouter.ai/api", "https://openrouter.ai/api/v1")
    assert not catalog.canonical_url_matches("http://openrouter.ai/api/v1", "https://openrouter.ai/api/v1")
    assert not catalog.canonical_url_matches("https://openrouter.ai:8443/api/v1", "https://openrouter.ai/api/v1")
    assert not catalog.canonical_url_matches("https://evil.com/api/v1", "https://openrouter.ai/api/v1")


@pytest.mark.parametrize("url", [
    "https://openrouter.ai:invalid/api/v1",
    "https://[broken/api/v1",
    "https://user:password@openrouter.ai/api/v1",
    "https://openrouter.ai/api/v1?redirect=attacker",
    "https://openrouter.ai/api/v1#ignored-path",
])
def test_rejects_malformed_or_noncanonical_url_components(url):
    catalog = _module("provider_catalog")
    assert not catalog.validate_provider_endpoint("openrouter", url)[0]


def test_network_import_does_not_change_default_opener():
    import urllib.request
    before = urllib.request._opener
    importlib.reload(_module("execution_adapters.network"))
    assert urllib.request._opener is before


def test_normalize_then_match_allows_ollama_api_suffix():
    catalog = _module("provider_catalog")

    normalized = catalog.normalize_provider_base_url("ollama-cloud", "https://ollama.com/api/")
    assert catalog.canonical_url_matches(normalized, "https://ollama.com")


def test_validate_provider_endpoint_blocks_fixed_cloud_url_mismatches():
    catalog = _module("provider_catalog")

    for provider in ("openrouter", "anthropic", "ollama-cloud"):
        ok, code = catalog.validate_provider_endpoint(provider, "http://attacker.invalid")
        assert not ok
        assert code == "provider_endpoint_canonical_mismatch"

    # Private / local-looking URLs are not acceptable for fixed cloud providers.
    for url in ("http://127.0.0.1:11434", "http://localhost:8080", "https://192.168.1.10"):
        ok, _ = catalog.validate_provider_endpoint("openrouter", url)
        assert not ok

    # Equal-looking host with a drifted API version path is rejected.
    ok, _ = catalog.validate_provider_endpoint(
        "anthropic", "https://api.anthropic.com/v2"
    )
    assert not ok


def test_validate_provider_endpoint_allows_local_and_custom_providers():
    catalog = _module("provider_catalog")

    for provider in ("ollama-local", "cpp-local", "opencode", "custom-openai-compatible"):
        ok, code = catalog.validate_provider_endpoint(provider, "http://127.0.0.1:9999")
        assert ok
        assert code == ""


def test_validate_provider_endpoint_allows_exact_canonical_cloud_urls():
    catalog = _module("provider_catalog")

    assert catalog.validate_provider_endpoint("openrouter", "https://openrouter.ai/api/v1")[0]
    assert catalog.validate_provider_endpoint("anthropic", "https://api.anthropic.com")[0]
    assert catalog.validate_provider_endpoint("ollama-cloud", "https://ollama.com")[0]
    assert catalog.validate_provider_endpoint("ollama-cloud", "https://ollama.com/api/")[0]


# ──────────────────────────────────────────────────────────────────────────────
# handle_test endpoint boundary
# ──────────────────────────────────────────────────────────────────────────────


def _fake_openrouter_chat_response(*_args, **_kwargs):
    """Return a minimal OpenAI-compatible chat response."""
    return _InterceptedResponse(
        url="https://openrouter.ai/api/v1/chat/completions",
        body=b'{"choices":[{"message":{"content":"BAGO_OK"},"finish_reason":"stop"}],"model":"openai/gpt-4.1-mini"}',
    )


def _make_manager(provider: str, config: FakeConfig, tmp_path: Path):
    session_module = _module("session_adapters_mixin")
    manager = session_module.SessionAdaptersMixin()
    manager.provider = provider
    manager.base_path = Path(tmp_path)
    manager.config = config
    manager.credentials = FakeCredentials()
    manager.session_id = f"test-{provider}-session"
    manager._providers_cache = None
    manager._providers_cache_at = 0.0
    manager._providers_cache_ttl = 0.0
    return manager


def test_handle_test_rejects_malicious_openrouter_base_url_before_secret_or_transport(monkeypatch, tmp_path):
    handlers = _module("handlers_providers")
    serializers = _module("api_serializers")
    openrouter = _module("openrouter")
    secret_store_module = _module("secret_store")

    responses: list[tuple[int, dict]] = []
    config = FakeConfig({"openrouter": {"enabled": True, "default_model": "openai/gpt-4.1-mini"}})
    manager = _make_manager("openrouter", config, tmp_path)

    secret = "fake-secret-must-not-leak"
    store = FakeSecretStore(tmp_path / "secrets", {"providers/openrouter/api_key": secret})

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(secret_store_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("transport must not be reached")))

    handlers.handle_test(SimpleNamespace(headers={}), {
        "provider": "openrouter",
        "base_url": "https://attacker.invalid/api/v1",
        "model": "openai/gpt-4.1-mini",
    })

    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "provider_endpoint_canonical_mismatch"
    assert responses[-1][1]["provider"] == "openrouter"


def test_handle_test_allows_canonical_openrouter_url_and_intercepts_fake_key(monkeypatch, tmp_path):
    handlers = _module("handlers_providers")
    serializers = _module("api_serializers")
    openrouter = _module("openrouter")
    secret_store_module = _module("secret_store")

    responses: list[tuple[int, dict]] = []
    transport_calls: list[object] = []

    config = FakeConfig({"openrouter": {"enabled": True, "default_model": "openai/gpt-4.1-mini"}})
    manager = _make_manager("openrouter", config, tmp_path)

    secret = "fake-secret-intercepted"
    store = FakeSecretStore(tmp_path / "secrets", {"providers/openrouter/api_key": secret})

    def intercepted_urlopen(request, **kwargs):
        transport_calls.append(request)
        return _fake_openrouter_chat_response(request.full_url)

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(secret_store_module, "get_secret_store", lambda: store)
    network = _module("execution_adapters.network")
    guards = []
    def build_opener(guard):
        guards.append(guard)
        return SimpleNamespace(open=intercepted_urlopen)
    monkeypatch.setattr(network.urllib.request, "build_opener", build_opener)

    handlers.handle_test(SimpleNamespace(headers={}), {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1/",
        "model": "openai/gpt-4.1-mini",
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["ok"] is True
    assert responses[-1][1]["provider"] == "openrouter"
    assert transport_calls
    assert isinstance(guards[0], network._ProviderRedirectGuard)
    intercepted = transport_calls[0]
    auth = intercepted.headers.get("Authorization", "")
    assert auth == f"Bearer {secret}"
    assert intercepted.full_url.startswith("https://openrouter.ai/api/v1")


def test_handle_test_uses_manager_config_base_url_and_rejects_drift(monkeypatch, tmp_path):
    handlers = _module("handlers_providers")
    serializers = _module("api_serializers")
    openrouter = _module("openrouter")
    secret_store_module = _module("secret_store")

    responses: list[tuple[int, dict]] = []

    config = FakeConfig({"openrouter": {"enabled": True, "base_url": "https://drifted.example/api/v1"}})
    manager = _make_manager("openrouter", config, tmp_path)

    store = FakeSecretStore(tmp_path / "secrets", {"providers/openrouter/api_key": "drift-secret"})

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(secret_store_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("transport must not be reached")))

    handlers.handle_test(SimpleNamespace(headers={}), {
        "provider": "openrouter",
        "model": "openai/gpt-4.1-mini",
    })

    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "provider_endpoint_canonical_mismatch"


# ──────────────────────────────────────────────────────────────────────────────
# handle_configure endpoint boundary
# ──────────────────────────────────────────────────────────────────────────────


def test_model_discovery_rejects_persisted_drift_before_credentials_or_transport(monkeypatch):
    handlers = _module("handlers_providers")
    monkeypatch.setattr(handlers, "_load_config", lambda: {
        "providers": {"openrouter": {"base_url": "https://attacker.invalid/api/v1"}}
    })
    def forbidden(*args, **kwargs):
        pytest.fail("credential access/transport before endpoint validation")
    monkeypatch.setattr(handlers, "_get_api_key", forbidden)
    monkeypatch.setattr(handlers, "_http_get_json", forbidden)
    models, error, source = handlers._discover_models("openrouter")
    assert models == [] and error == "provider_endpoint_canonical_mismatch"
    assert source == "openai_models"


def test_handle_configure_rejects_malicious_base_url_before_persistence_or_secret(monkeypatch, tmp_path):
    handlers = _module("handlers_providers")
    serializers = _module("api_serializers")
    secret_store_module = _module("secret_store")

    responses: list[tuple[int, dict]] = []
    config = FakeConfig({"openrouter": {"enabled": False}})
    manager = SimpleNamespace(
        session_id="configure-endpoint-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    store = FakeSecretStore(tmp_path / "user" / "secrets")

    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda _provider: False)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(secret_store_module, "get_secret_store", lambda: store)

    handlers.handle_configure(SimpleNamespace(headers={}), {
        "provider": "openrouter",
        "enabled": True,
        "base_url": "https://attacker.invalid/api/v1",
        "api_key": "should-not-be-written",
    })

    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "provider_endpoint_canonical_mismatch"
    assert config.saved == []
    assert store.get_secret("providers/openrouter/api_key") is None


def test_handle_configure_allows_canonical_base_url_and_persists(monkeypatch, tmp_path):
    handlers = _module("handlers_providers")
    serializers = _module("api_serializers")
    secret_store_module = _module("secret_store")
    auth = _module("authorization_boundary")

    responses: list[tuple[int, dict]] = []
    config = FakeConfig({"openrouter": {"enabled": False}})
    manager = SimpleNamespace(
        session_id="configure-ok-session",
        config=config,
        invalidate_providers_cache=lambda: None,
    )
    store = FakeSecretStore(tmp_path / "user" / "secrets")

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    monkeypatch.setattr(handlers, "_mgr", lambda _handler: manager)
    monkeypatch.setattr(handlers, "_has_provider_secret", lambda provider: store.get_secret(f"providers/{provider}/api_key") is not None)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(secret_store_module, "get_secret_store", lambda: store)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(auth, "confirm_strong_challenge", lambda _challenge: True)

    handlers.handle_configure(SimpleNamespace(headers={"X-Bago-Channel": "ui-react"}), {
        "provider": "openrouter",
        "enabled": True,
        "base_url": "https://openrouter.ai/api/v1/",
        "model": "openai/gpt-4.1-mini",
        "api_key": "persisted-secret",
        "authorization_action": "challenge",
        "interaction_id": "configure-ok-interaction",
    })
    challenge = responses[-1][1]["authorization"]["challenge"]

    handlers.handle_configure(SimpleNamespace(headers={"X-Bago-Channel": "ui-react"}), {
        "provider": "openrouter",
        "enabled": True,
        "base_url": "https://openrouter.ai/api/v1/",
        "model": "openai/gpt-4.1-mini",
        "api_key": "persisted-secret",
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
        "interaction_id": "configure-ok-interaction",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]

    handlers.handle_configure(SimpleNamespace(headers={"X-Bago-Channel": "ui-react"}), {
        "provider": "openrouter",
        "enabled": True,
        "base_url": "https://openrouter.ai/api/v1/",
        "model": "openai/gpt-4.1-mini",
        "api_key": "persisted-secret",
        "authorization_action": "execute",
        "authorization_permit": permit,
        "interaction_id": "configure-ok-interaction",
    })

    assert responses[-1][0] == 200
    persisted = config.providers["openrouter"]
    assert persisted["enabled"] is True
    assert persisted["base_url"] == "https://openrouter.ai/api/v1"
    assert persisted["default_model"] == "openai/gpt-4.1-mini"
    assert "api_key" not in persisted
    assert store.get_secret("providers/openrouter/api_key") == "persisted-secret"


# ──────────────────────────────────────────────────────────────────────────────
# _build_adapter_config endpoint boundary
# ──────────────────────────────────────────────────────────────────────────────


def test_build_adapter_config_rejects_persisted_drift_before_reading_secret(monkeypatch, tmp_path):
    session_module = _module("session_adapters_mixin")
    secrets_module = _module("secret_store")

    manager = session_module.SessionAdaptersMixin()
    manager.provider = "openrouter"
    manager.base_path = Path(tmp_path)
    manager.config = FakeConfig({
        "openrouter": {
            "enabled": True,
            "base_url": "https://drifted.example/api/v1",
        }
    })
    manager.credentials = FakeCredentials()

    secret_accessed: list[str] = []

    class SpyingStore(FakeSecretStore):
        def get_secret(self, key: str) -> str | None:
            secret_accessed.append(key)
            return super().get_secret(key)

    store = SpyingStore(tmp_path / "secrets", {"providers/openrouter/api_key": "must-not-be-read"})
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)

    with pytest.raises(RuntimeError, match="persisted endpoint drift blocked"):
        manager._build_adapter_config("openrouter")

    assert "providers/openrouter/api_key" not in secret_accessed


def test_build_adapter_config_accepts_canonical_url_and_reads_secret(monkeypatch, tmp_path):
    session_module = _module("session_adapters_mixin")
    secrets_module = _module("secret_store")

    manager = session_module.SessionAdaptersMixin()
    manager.provider = "openrouter"
    manager.base_path = Path(tmp_path)
    manager.config = FakeConfig({
        "openrouter": {
            "enabled": True,
            "base_url": "https://openrouter.ai/api/v1",
        }
    })
    manager.credentials = FakeCredentials()

    store = FakeSecretStore(tmp_path / "secrets", {"providers/openrouter/api_key": "canonical-secret"})
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)

    config = manager._build_adapter_config("openrouter")

    assert config["api_key"] == "canonical-secret"
    assert config["base_url"] == "https://openrouter.ai/api/v1"


def test_build_adapter_config_rejects_legacy_env_override_before_secret(monkeypatch, tmp_path):
    session_module = _module("session_adapters_mixin")
    secrets_module = _module("secret_store")

    monkeypatch.setenv("OLLAMA_CLOUD_URL", "https://attacker.invalid")

    manager = session_module.SessionAdaptersMixin()
    manager.provider = "ollama-cloud"
    manager.base_path = Path(tmp_path)
    manager.config = FakeConfig({"ollama-cloud": {"enabled": True}})
    manager.credentials = LegacyCredentials()

    secret_accessed: list[str] = []

    class SpyingStore(FakeSecretStore):
        def get_secret(self, key: str) -> str | None:
            secret_accessed.append(key)
            return super().get_secret(key)

    store = SpyingStore(tmp_path / "secrets", {"providers/ollama-cloud/api_key": "must-not-be-read"})
    monkeypatch.setattr(secrets_module, "get_secret_store", lambda: store)

    with pytest.raises(RuntimeError, match="persisted endpoint drift blocked"):
        manager._build_adapter_config("ollama-cloud")

    assert "providers/ollama-cloud/api_key" not in secret_accessed


# ──────────────────────────────────────────────────────────────────────────────
# Network adapter redirect guard
# ──────────────────────────────────────────────────────────────────────────────


def test_provider_redirect_guard_blocks_cross_origin_redirect():
    network = _module("execution_adapters.network")
    req = SimpleNamespace(
        full_url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": "Bearer secret"},
        unredirected_hdrs={},
    )
    guard = network._ProviderRedirectGuard()

    with pytest.raises(Exception) as exc:
        guard.redirect_request(req, None, 302, "Found", {"Location": "https://evil.com/x"}, "https://evil.com/x")

    assert exc.value.code == "network_read_provider_redirect_blocked"


def test_provider_redirect_guard_allows_same_origin_redirect():
    network = _module("execution_adapters.network")
    req = network.urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer secret"}
    )
    guard = network._ProviderRedirectGuard()
    redirected = guard.redirect_request(req, None, 302, "Found", {}, "https://openrouter.ai/api/v1/other")
    assert redirected.full_url == "https://openrouter.ai/api/v1/other"
    assert redirected.get_header("Authorization") == "Bearer secret"


def test_provider_redirect_guard_ignores_requests_without_auth_headers():
    network = _module("execution_adapters.network")
    req = network.urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", headers={"Content-Type": "application/json"}
    )
    guard = network._ProviderRedirectGuard()
    redirected = guard.redirect_request(req, None, 302, "Found", {}, "https://evil.com/x")
    assert redirected.full_url == "https://evil.com/x"


def test_network_adapter_post_hoc_redirect_blocks_cross_origin_with_auth(monkeypatch, tmp_path):
    network = _module("execution_adapters.network")
    request_module = _module("execution_request")
    urllib_module = _module("urllib.request")

    def fake_urlopen(request, **kwargs):
        return _InterceptedResponse(url="https://evil.com/exfil", body=b'{}')

    monkeypatch.setattr(urllib_module, "build_opener", lambda guard: SimpleNamespace(open=fake_urlopen))

    request = request_module.build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="redirect-block-session",
        source_surface="server.network.provider_transport",
        target={
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "method": "POST",
            "network_class": "provider_transport",
            "timeout": 30.0,
        },
        arguments={
            "headers": {"Authorization": "Bearer secret"},
            "data_b64": "",
        },
        scope="external",
    )

    adapter = network.NetworkReadEffectAdapter()
    with pytest.raises(Exception) as exc:
        adapter.execute(request, SimpleNamespace(services={"_authorization": {"kind": "server_policy"}}))

    assert exc.value.code == "network_read_provider_redirect_blocked"


def test_network_adapter_post_hoc_redirect_allows_same_origin_with_auth(monkeypatch, tmp_path):
    network = _module("execution_adapters.network")
    request_module = _module("execution_request")
    urllib_module = _module("urllib.request")

    def fake_urlopen(request, **kwargs):
        return _InterceptedResponse(url="https://openrouter.ai/api/v1/chat/completions", body=b'{}')

    monkeypatch.setattr(urllib_module, "build_opener", lambda guard: SimpleNamespace(open=fake_urlopen))

    request = request_module.build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="redirect-allow-session",
        source_surface="server.network.provider_transport",
        target={
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "method": "POST",
            "network_class": "provider_transport",
            "timeout": 30.0,
        },
        arguments={
            "headers": {"Authorization": "Bearer secret"},
            "data_b64": "",
        },
        scope="external",
    )

    adapter = network.NetworkReadEffectAdapter()
    response = adapter.execute(request, SimpleNamespace(services={"_authorization": {"kind": "server_policy"}}))

    assert response.status == 200
