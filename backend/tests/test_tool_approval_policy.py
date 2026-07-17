from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


import repl_menu  # noqa: E402
import session_manager  # noqa: E402


class _DummySimple:
    def __init__(self, *args, **kwargs):
        pass

    def close(self):
        pass


class _PolicyConfig:
    def __init__(self, *args, **kwargs):
        self.default_provider = "ollama-local"
        self.default_model = "llama3.2:3b"
        self.data = {
            "features": {
                "tool_calling": True,
                "auto_allow_tools": False,
                "tool_approval_policy": "ask",
            }
        }

    def _walk(self, key: str):
        node = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        return node, parts[-1]

    def get(self, key: str, default=None):
        node = self.data
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, key: str, value):
        node, last = self._walk(key)
        node[last] = value

    def provider_config(self, provider: str) -> dict:
        return {"base_url": "http://127.0.0.1:11434"}

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


class _DummyREPL:
    def __init__(self, mgr, selected: int):
        self.mgr = mgr
        self.selected = selected

    def _navigate(self, *_args, **_kwargs):
        return self.selected


def _make_manager(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(session_manager, "ConfigManager", _PolicyConfig)
    monkeypatch.setattr(session_manager, "CredentialManager", _DummyCreds)
    monkeypatch.setattr(session_manager, "ScriptRegistry", _DummySimple)
    monkeypatch.setattr(session_manager, "ToolRegistry", _DummySimple)
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
        lambda self: setattr(
            self,
            "_adapter",
            SimpleNamespace(
                health_check=lambda timeout=5.0: SimpleNamespace(ok=True, detail="ok", latency_ms=0.0),
                supports_tools=lambda: False,
                supports_streaming=lambda: False,
                supports_embeddings=lambda: False,
            ),
        ) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []},
    )
    return session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))


def test_tool_approval_policy_persists_on_manager(tmp_path, monkeypatch):
    mgr = _make_manager(tmp_path, monkeypatch)
    try:
        assert mgr.tool_approval_policy() == "ask"

        assert mgr.set_tool_approval_policy("always") == "always"
        assert mgr.config.get("features.tool_approval_policy") == "always"
        assert mgr.config.get("features.auto_allow_tools") is True
        assert mgr.tool_approval_policy() == "always"

        assert mgr.set_tool_approval_policy("ask") == "ask"
        assert mgr.config.get("features.tool_approval_policy") == "ask"
        assert mgr.config.get("features.auto_allow_tools") is False
    finally:
        mgr.close()


def test_pending_tool_selector_maps_to_policy_actions(tmp_path, monkeypatch, capsys):
    class _SelectorMgr:
        def __init__(self):
            self.calls: list[tuple[str, str]] = []
            self._pending_tools = [{"function": {"name": "file-read", "arguments": {"path": "README.md"}}}]
            self._pending_normalized = [{"role": "user", "content": "lee README.md"}]
            self._pending_tools_kwargs = {}
            self._pending_user_message = "lee README.md"
            self.config = SimpleNamespace(
                get=lambda key, default=None: {"features.tool_approval_policy": "ask", "features.auto_allow_tools": False}.get(key, default)
            )

        def tool_approval_policy(self):
            return "ask"

        def approve_tools(self, mode="once"):
            self.calls.append(("approve", mode))
            self._pending_tools = None
            self._pending_normalized = None
            return f"approved:{mode}"

        def deny_tools(self, mode="once"):
            self.calls.append(("deny", mode))
            self._pending_tools = None
            self._pending_normalized = None
            return f"denied:{mode}"

    printed: list[tuple[str, str]] = []
    monkeypatch.setattr(repl_menu.R, "dim", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "ok", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "warn", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "print_message", lambda role, content: printed.append((role, content)))
    monkeypatch.setattr(repl_menu.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(repl_menu.sys.stdout, "isatty", lambda: True)

    mgr = _SelectorMgr()
    repl = _DummyREPL(mgr, selected=1)
    assert repl_menu.BagoReplMenuMixin._pending_tool_approval_wizard(repl) is True
    assert mgr.calls == [("approve", "always")]
    assert printed and printed[-1][0] == "assistant"

    mgr = _SelectorMgr()
    printed.clear()

    repl = _DummyREPL(mgr, selected=2)
    assert repl_menu.BagoReplMenuMixin._pending_tool_approval_wizard(repl) is True
    assert mgr.calls == [("deny", "ask")]
    assert printed == []

    out = capsys.readouterr().out
    assert "Solicitud de herramientas pendiente" in out
