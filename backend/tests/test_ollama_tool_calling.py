from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]

import ollama_local  # noqa: E402
import session_manager  # noqa: E402


class _DummySimple:
    def __init__(self, *args, **kwargs):
        pass

    def close(self):
        pass

    def validate(self, *args, **kwargs):
        return SimpleNamespace(warning="", has_claim=False, has_evidence=False)

    def implicit(self, *args, **kwargs):
        return None


class _DummyConfig:
    default_provider = "ollama-local"
    default_model = "llama3.2:3b"

    def __init__(self, *args, **kwargs):
        self.values = {
            "features.tool_calling": True,
            "features.auto_allow_tools": False,
            "features.tool_approval_policy": "ask",
        }

    def provider_config(self, provider: str) -> dict:
        return {"base_url": "http://127.0.0.1:11434"}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value

    def is_provider_enabled(self, provider: str) -> bool:
        return True


class _DummyCreds:
    def __init__(self, *args, **kwargs):
        pass

    def required_keys(self, provider: str) -> list[str]:
        return []

    def get(self, provider: str, key: str):
        return ""


class _DummyAgentGateway:
    def __init__(self, *args, **kwargs):
        self.active = SimpleNamespace(name="default")

    def activate(self, name: str):
        self.active = SimpleNamespace(name=name)


class _ToolRegistry:
    def __init__(self, workspace_root=None, **kwargs):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None

    def __len__(self) -> int:
        return 2

    def to_openai(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "file-read",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file-edit",
                    "description": "Edit a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                    },
                },
            }
        ]

    def parse_tool_calls(self, payload):
        calls = []
        for raw in payload.get("tool_calls", []) or []:
            function = raw.get("function", {}) if isinstance(raw, dict) else {}
            calls.append(
                SimpleNamespace(
                    call_id=str(raw.get("id") or raw.get("tool_call_id") or function.get("name") or "tool-call"),
                    name=str(function.get("name") or raw.get("name") or ""),
                    arguments=function.get("arguments", {}) or {},
                )
            )
        return calls

    def execute_call(self, call):
        root = self.workspace_root or Path.cwd()
        path = root / str(call.arguments.get("path", ""))
        if call.name == "file-read":
            content = path.read_text(encoding="utf-8")
            return SimpleNamespace(call_id=call.call_id, name=call.name, ok=True, returncode=0, content=content)
        if call.name == "file-edit":
            original = path.read_text(encoding="utf-8")
            old = str(call.arguments.get("old", ""))
            new = str(call.arguments.get("new", ""))
            replacements = original.count(old)
            path.write_text(original.replace(old, new), encoding="utf-8")
            return SimpleNamespace(
                call_id=call.call_id,
                name=call.name,
                ok=True,
                returncode=0,
                content=f'{{"ok":true,"replacements":{replacements}}}',
            )
        return SimpleNamespace(call_id=call.call_id, name=call.name, ok=False, returncode=1, content=f"Tool not registered: {call.name}")


class _CaptureOllamaAdapter:
    def __init__(self):
        self.systems: list[str] = []
        self.max_tokens: list[int | None] = []
        self.chat_calls = 0

    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        self.chat_calls += 1
        self.systems.append(system)
        self.max_tokens.append(max_tokens)
        return session_manager.ProviderResponse(content="ok", provider="ollama-local", model_used=model)

    def supports_tools(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return False

    def supports_embeddings(self) -> bool:
        return False

    def health_check(self, timeout: float = 5.0):
        return SimpleNamespace(ok=True, detail="ok", latency_ms=0.0)


class _StreamingOllamaAdapter(_CaptureOllamaAdapter):
    def __init__(self):
        super().__init__()
        self.stream_calls = 0

    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        raise AssertionError("plain chat should use chat_stream")

    def chat_stream(self, messages, model, *, system="", temperature=0.7, max_tokens=None, tools=None):
        self.stream_calls += 1
        self.systems.append(system)
        self.max_tokens.append(max_tokens)
        yield "stream-ok"

    def supports_streaming(self) -> bool:
        return True


class _ReadThenEditAdapter(_CaptureOllamaAdapter):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        self.calls += 1
        self.systems.append(system)
        if self.calls == 1:
            return session_manager.ProviderResponse(
                content="",
                provider="ollama-local",
                model_used=model,
                tool_calls=[
                    {
                        "id": "read-1",
                        "type": "function",
                        "function": {"name": "file-read", "arguments": {"path": "note.txt"}},
                    }
                ],
            )
        if self.calls == 2:
            return session_manager.ProviderResponse(
                content="",
                provider="ollama-local",
                model_used=model,
                tool_calls=[
                    {
                        "id": "edit-1",
                        "type": "function",
                        "function": {
                            "name": "file-edit",
                            "arguments": {"path": "note.txt", "old": "old content", "new": "new content"},
                        },
                    }
                ],
            )
        assert any(m.get("role") == "tool" and "replacements" in m.get("content", "") for m in messages)
        return session_manager.ProviderResponse(content="Archivo actualizado.", provider="ollama-local", model_used=model)


def test_ollama_tool_result_messages_use_tool_name():
    adapter = ollama_local.OllamaLocalAdapter()
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "file-read", "arguments": {"path": "README.md"}},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "{\"ok\":true}"},
    ]

    formatted = adapter._format_messages_for_ollama(messages)

    assert formatted[1] == {"role": "tool", "content": "{\"ok\":true}", "tool_name": "file-read"}


def test_ollama_parses_fallback_tool_call_markup():
    adapter = ollama_local.OllamaLocalAdapter()
    result = adapter._fallback_tool_calls_from_content(
        '<tool_call>{"name":"file-read","arguments":{"path":"src/App.jsx"}}</tool_call>'
    )

    assert result == [
        {
            "id": "ollama-fallback-0",
            "type": "function",
            "function": {"name": "file-read", "arguments": {"path": "src/App.jsx"}},
        }
    ]


def test_ollama_adapter_uses_configured_timeout():
    adapter = ollama_local.OllamaLocalAdapter({"timeout_seconds": 12.5})

    assert adapter.timeout_seconds == 12.5


def test_ollama_local_system_prompt_includes_tool_fallback(tmp_path, monkeypatch):
    adapter = _CaptureOllamaAdapter()
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(session_manager, "ConfigManager", _DummyConfig)
    monkeypatch.setattr(session_manager, "CredentialManager", _DummyCreds)
    monkeypatch.setattr(session_manager, "ScriptRegistry", _DummySimple)
    monkeypatch.setattr(session_manager, "ToolRegistry", lambda *args, **kwargs: _ToolRegistry(kwargs.get("workspace_root")))
    monkeypatch.setattr(session_manager, "KnowledgeBase", _DummySimple)
    monkeypatch.setattr(session_manager, "EmbeddingStore", _DummySimple)
    monkeypatch.setattr(session_manager, "GaboConnector", _DummySimple)
    monkeypatch.setattr(session_manager, "PathGuard", _DummySimple)
    monkeypatch.setattr(session_manager, "ToolLogger", _DummySimple)
    monkeypatch.setattr(session_manager, "ClaimValidator", _DummySimple)
    monkeypatch.setattr(session_manager, "PlanEngine", _DummySimple)
    monkeypatch.setattr(session_manager, "PreferenceModel", _DummySimple)
    monkeypatch.setattr(session_manager, "FeedbackCollector", _DummySimple)
    monkeypatch.setattr(session_manager, "AgentGateway", _DummyAgentGateway)
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_init_adapter",
        lambda self: setattr(self, "_adapter", adapter) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []},
    )

    mgr = session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))
    try:
        mgr.send("lee README.md")
    finally:
        mgr.close()

    assert any("OLLAMA LOCAL TOOL FORMAT" in system for system in adapter.systems)
    assert any("<tool_call>" in system for system in adapter.systems)
    assert 1024 in adapter.max_tokens


def test_plain_chat_streams_even_when_tools_are_registered(tmp_path, monkeypatch):
    adapter = _StreamingOllamaAdapter()
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(session_manager, "ConfigManager", _DummyConfig)
    monkeypatch.setattr(session_manager, "CredentialManager", _DummyCreds)
    monkeypatch.setattr(session_manager, "ScriptRegistry", _DummySimple)
    monkeypatch.setattr(session_manager, "ToolRegistry", lambda *args, **kwargs: _ToolRegistry(kwargs.get("workspace_root")))
    monkeypatch.setattr(session_manager, "KnowledgeBase", _DummySimple)
    monkeypatch.setattr(session_manager, "EmbeddingStore", _DummySimple)
    monkeypatch.setattr(session_manager, "GaboConnector", _DummySimple)
    monkeypatch.setattr(session_manager, "PathGuard", _DummySimple)
    monkeypatch.setattr(session_manager, "ToolLogger", _DummySimple)
    monkeypatch.setattr(session_manager, "ClaimValidator", _DummySimple)
    monkeypatch.setattr(session_manager, "PlanEngine", _DummySimple)
    monkeypatch.setattr(session_manager, "PreferenceModel", _DummySimple)
    monkeypatch.setattr(session_manager, "FeedbackCollector", _DummySimple)
    monkeypatch.setattr(session_manager, "AgentGateway", _DummyAgentGateway)
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_init_adapter",
        lambda self: setattr(self, "_adapter", adapter) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []},
    )

    mgr = session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))
    try:
        response = "".join(mgr.send_stream("HOLA"))
    finally:
        mgr.close()

    assert response == "stream-ok"
    assert adapter.stream_calls == 1
    assert adapter.chat_calls == 0
    assert adapter.max_tokens[0] == 160


def test_session_manager_allows_read_then_edit_tool_rounds(tmp_path, monkeypatch):
    adapter = _ReadThenEditAdapter()
    project = tmp_path / "project"
    project.mkdir()
    target = project / "note.txt"
    target.write_text("old content\n", encoding="utf-8")

    monkeypatch.setattr(session_manager, "ConfigManager", _DummyConfig)
    monkeypatch.setattr(session_manager, "CredentialManager", _DummyCreds)
    monkeypatch.setattr(session_manager, "ScriptRegistry", _DummySimple)
    monkeypatch.setattr(session_manager, "ToolRegistry", lambda *args, **kwargs: _ToolRegistry(kwargs.get("workspace_root")))
    monkeypatch.setattr(session_manager, "KnowledgeBase", _DummySimple)
    monkeypatch.setattr(session_manager, "EmbeddingStore", _DummySimple)
    monkeypatch.setattr(session_manager, "GaboConnector", _DummySimple)
    monkeypatch.setattr(session_manager, "PlanEngine", _DummySimple)
    monkeypatch.setattr(session_manager, "PreferenceModel", _DummySimple)
    monkeypatch.setattr(session_manager, "FeedbackCollector", _DummySimple)
    monkeypatch.setattr(session_manager, "AgentGateway", _DummyAgentGateway)
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_init_adapter",
        lambda self: setattr(self, "_adapter", adapter) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []},
    )

    mgr = session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))
    mirror_target = Path(mgr.workspace_mirror_root) / "note.txt"
    try:
        mgr.config.set("features.auto_allow_tools", True)
        mgr.config.set("features.tool_approval_policy", "always")
        response = mgr.send("lee note.txt y cambia old content por new content")
    finally:
        mgr.close()

    assert response == "Archivo actualizado."
    assert target.read_text(encoding="utf-8") == "old content\n"
    assert mirror_target.read_text(encoding="utf-8") == "new content\n"
    assert adapter.calls == 3
