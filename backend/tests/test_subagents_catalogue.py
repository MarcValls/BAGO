"""Contract tests for the canonical subagent catalogue."""

from __future__ import annotations


def test_subagents_catalogue_reads_active_roles(monkeypatch):
    import api_serializers
    from handlers_subagents import handle

    captured = {}

    def fake_send_json(_handler, status, payload):
        captured.update(status=status, payload=payload)

    monkeypatch.setattr(api_serializers, "send_json", fake_send_json)
    handle(object())

    payload = captured["payload"]
    assert captured["status"] == 200
    assert payload["ok"] is True
    assert payload["count"] == len(payload["agents"])
    assert payload["count"] > 0
    assert payload["source"] == ".bago/roles/manifest.json"
    assert all(agent["id"] and agent["name"] for agent in payload["agents"])
    assert all(agent["available"] for agent in payload["agents"])
