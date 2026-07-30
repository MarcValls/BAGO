from __future__ import annotations

import json
import urllib.error


def test_all_cloud_provider_adapters_pass_offline_contract():
    from bago_core.commands.cmd_chat import _verify_cloud_provider_contracts

    ok, checked = _verify_cloud_provider_contracts()
    assert ok
    assert checked == [
        "ollama-cloud",
        "copilot",
        "anthropic",
        "codex",
        "openrouter",
        "opencode",
    ]


def test_cloud_contract_http_surface_discloses_offline_scope(monkeypatch):
    import api_serializers
    from handlers_providers import handle_contracts

    captured = {}
    monkeypatch.setattr(api_serializers, "send_json", lambda _h, status, payload: captured.update(status=status, payload=payload))
    handle_contracts(object())

    assert captured["status"] == 200
    payload = captured["payload"]
    assert payload["ok"] is True
    assert payload["passed"] == payload["expected"] == 6
    assert payload["mode"] == "offline-contract"
    assert payload["live_calls"] is False
    assert payload["credential_required_for_live_calls"] is True


def test_ollama_cloud_sends_system_as_first_message(monkeypatch):
    from ollama_cloud import OllamaCloudAdapter

    payloads = []

    def fake_post(_url, payload, timeout=60.0):
        payloads.append(payload)
        return {"message": {"content": "ok"}, "done": True}

    adapter = OllamaCloudAdapter({"base_url": "https://contract.invalid", "api_key": "test"})
    monkeypatch.setattr(adapter, "_post", fake_post)

    adapter.chat([{"role": "user", "content": "hola"}], "test-model", system="Eres BAGO")

    assert payloads[0]["messages"][0] == {"role": "system", "content": "Eres BAGO"}
    assert "system" not in payloads[0]


def test_ollama_cloud_retries_legacy_key_only_after_unauthorized(monkeypatch):
    import ollama_cloud

    calls = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def read():
            return json.dumps({"message": {"content": "ok"}, "done": True}).encode()

    def fake_urlopen(request, timeout=60.0):
        calls.append(request.headers.get("Authorization"))
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", None, None)
        return Reply()

    monkeypatch.setattr(ollama_cloud.urllib.request, "urlopen", fake_urlopen)
    adapter = ollama_cloud.OllamaCloudAdapter({
        "base_url": "https://contract.invalid",
        "api_key": "canonical-secret",
        "fallback_api_key": "legacy-secret",
    })

    response = adapter.chat([{"role": "user", "content": "hola"}], "test-model", system="Eres BAGO")

    assert response.content == "ok"
    assert calls == ["Bearer canonical-secret", "Bearer legacy-secret"]
    assert adapter.api_key == "legacy-secret"


def test_ollama_cloud_stream_retries_legacy_key_after_unauthorized(monkeypatch):
    import ollama_cloud

    calls = []

    class StreamReply:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter([
                b'{"message":{"content":"Hola"},"done":false}\n',
                b'{"message":{"content":" BAGO"},"done":true}\n',
            ])

    def fake_urlopen(request, timeout=60.0):
        calls.append(request.headers.get("Authorization"))
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", None, None)
        return StreamReply()

    monkeypatch.setattr(ollama_cloud.urllib.request, "urlopen", fake_urlopen)
    adapter = ollama_cloud.OllamaCloudAdapter({
        "base_url": "https://contract.invalid",
        "api_key": "canonical-secret",
        "fallback_api_key": "legacy-secret",
    })

    text = "".join(adapter.chat_stream([{"role": "user", "content": "hola"}], "test-model", system="Eres BAGO"))

    assert text == "Hola BAGO"
    assert calls == ["Bearer canonical-secret", "Bearer legacy-secret"]
    assert adapter.api_key == "legacy-secret"
