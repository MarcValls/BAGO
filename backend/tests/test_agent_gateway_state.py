from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

AGENT_GATEWAY_PATH = Path(__file__).resolve().parents[1] / ".bago" / "agents" / "agent_gateway.py"
_SPEC = importlib.util.spec_from_file_location("agent_gateway_runtime_under_test", AGENT_GATEWAY_PATH)
assert _SPEC is not None and _SPEC.loader is not None
agent_gateway = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = agent_gateway
_SPEC.loader.exec_module(agent_gateway)


def test_neural_bus_events_use_server_state_append_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_gateway, "_STATE_DIR", tmp_path)
    calls = []

    def append_text_durable(path, content, **kwargs):
        calls.append((path, content, kwargs))
        return {"ok": True}

    monkeypatch.setattr(agent_gateway, "append_text_durable", append_text_durable)
    request = agent_gateway.AgentRequest(intent="status", source={"adapter": "local"})

    gateway = agent_gateway.AgentGateway()
    gateway._emit_event("agent.request", request)

    assert gateway._event_log[0]["type"] == "agent.request"
    path, content, kwargs = calls[0]
    assert path == tmp_path / "neural_events.jsonl"
    assert '"type": "agent.request"' in content
    assert content.endswith("\n")
    assert kwargs["trusted_root"] == tmp_path
    assert kwargs["source_surface"] == "agent.gateway.event"
    assert kwargs["session_id"] == f"agent-gateway:{tmp_path.resolve()}"


def test_codex_health_checks_path_without_spawning_process(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_gateway.shutil, "which", lambda name: calls.append(name) or r"C:\Tools\codex.exe")
    monkeypatch.setattr(agent_gateway.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")))

    assert agent_gateway.CodexAdapter().health() is True
    assert calls == ["codex"]
