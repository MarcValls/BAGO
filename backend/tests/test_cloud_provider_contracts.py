from __future__ import annotations


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
