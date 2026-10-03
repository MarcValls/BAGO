from __future__ import annotations

import importlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace


class _Config:
    def __init__(self, translation_config: dict) -> None:
        self.translation_config = translation_config

    def provider_config(self, _provider: str) -> dict:
        return {}

    def get(self, key: str, default=None):
        if key == "translation_middleware":
            return self.translation_config
        return default


class _Response:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.closed = True

    def read(self) -> bytes:
        return b"{}"


def _manager(monkeypatch, tmp_path: Path, *, model: str = "granite3.2:8b"):
    session_module = importlib.import_module("session_adapters_mixin")
    secrets_module = importlib.import_module("secret_store")
    monkeypatch.setattr(
        secrets_module,
        "get_secret_store",
        lambda: SimpleNamespace(get_secret=lambda _key: None),
    )

    class ProviderAdapter:
        provider_name = "ollama-local"

        def __init__(self, *, config):
            self.config = config
            self.timeout_seconds = 10

    monkeypatch.setitem(session_module.ADAPTER_REGISTRY, "ollama-local", ProviderAdapter)
    manager = session_module.SessionAdaptersMixin()
    manager.provider = "ollama-local"
    manager.model = model
    manager.base_path = tmp_path
    manager.config = _Config({
        "enabled": True,
        "target_models": [model],
        "target_keep_alive_minutes": 3,
        "translator_base_url": "http://127.0.0.1:11434",
    })
    manager.credentials = SimpleNamespace(required_keys=lambda _provider: [])
    manager.list_models = lambda _provider: [model]
    return session_module, manager


def test_translation_preload_dispatches_through_gateway_provider_transport(
    monkeypatch, tmp_path,
):
    from execution_adapters import network as network_adapter

    session_module, manager = _manager(monkeypatch, tmp_path)
    gateway_classes = []
    transport_requests = []
    entered = threading.Event()
    release = threading.Event()
    response = _Response()
    original_execute = network_adapter.NetworkReadEffectAdapter.execute

    def observe_gateway(self, request, context):
        gateway_classes.append(request.target["network_class"])
        return original_execute(self, request, context)

    def fake_urlopen(request, *, timeout):
        transport_requests.append((request, timeout))
        entered.set()
        assert release.wait(3)
        return response

    monkeypatch.setattr(network_adapter.NetworkReadEffectAdapter, "execute", observe_gateway)
    monkeypatch.setattr(network_adapter.urllib.request, "urlopen", fake_urlopen)

    initialized = threading.Event()
    initialization = []

    def initialize():
        try:
            initialization.append(manager._init_adapter())
        except Exception as exc:
            initialization.append(exc)
        finally:
            initialized.set()

    worker = threading.Thread(target=initialize, daemon=True)
    worker.start()
    try:
        assert initialized.wait(1)
        assert entered.wait(3)
        assert isinstance(initialization[0], dict)
        assert gateway_classes == ["provider_transport"]
        request, timeout = transport_requests[0]
        assert request.full_url == "http://127.0.0.1:11434/api/generate"
        assert request.get_method() == "POST"
        assert json.loads(request.data.decode("utf-8"))["keep_alive"] == "3m"
        assert timeout == 300
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()


def test_blocked_translation_preload_never_calls_underlying_transport(
    monkeypatch, tmp_path, caplog,
):
    from execution_adapters import network as network_adapter

    session_module, manager = _manager(monkeypatch, tmp_path)
    monkeypatch.setattr(
        network_adapter.NetworkReadEffectAdapter,
        "_ALLOWED_CLASSES",
        frozenset({"local_discovery"}),
    )
    transport_calls = []
    entered = threading.Event()

    def forbidden_urlopen(*_args, **_kwargs):
        transport_calls.append(True)
        raise AssertionError("blocked gateway dispatch reached urllib")

    monkeypatch.setattr(network_adapter.urllib.request, "urlopen", forbidden_urlopen)
    caplog.set_level("WARNING", logger=session_module.__name__)

    manager._init_adapter()
    # Wait for the background worker to report the gateway rejection.
    for _ in range(100):
        if any("ExecutionGatewayError" in record.message for record in caplog.records):
            entered.set()
            break
        entered.wait(0.01)

    assert entered.is_set()
    assert transport_calls == []
    assert any("granite3.2:8b" in record.message for record in caplog.records)
