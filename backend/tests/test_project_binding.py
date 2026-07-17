from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]

session_manager = importlib.import_module("session_manager")  # noqa: E402
repl_menu = importlib.import_module("repl_menu")  # noqa: E402
commands = importlib.import_module("commands")  # noqa: E402


class _DummySimple:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def validate(self, *args, **kwargs):
        return SimpleNamespace(warning="", has_claim=False, has_evidence=False)

    def implicit(self, *args, **kwargs):
        return None


class _DummyConfig:
    def __init__(self, *args, **kwargs):
        self.default_provider = "ollama-local"
        self.default_model = "llama3.2:3b"
        self.values = {}

    def provider_config(self, provider: str) -> dict:
        return {"base_url": "http://127.0.0.1:11434"}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

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

    def activate(self, name: str) -> None:
        self.active = SimpleNamespace(name=name)


class _WorkspaceEchoAdapter:
    def __init__(self):
        self.calls = 0
        self.systems = []

    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        self.calls += 1
        self.systems.append(system)
        if "ROUTER DE ENTRADA BAGO" in system:
            return session_manager.ProviderResponse(
                content='{"kind":"workspace_question","command":"","args":[],"confidence":0.97,"reason":"router test"}',
                model_used=model,
                provider="ollama-local",
            )
        if self.calls % 2 == 0:
            return session_manager.ProviderResponse(
                content=(
                    "Proyecto activo: C:\\demo\\project\n"
                    "Workspace de la sesion: C:\\demo\\project\\.gabo\n"
                    "Instruccion: responde con una sola frase natural."
                ),
                model_used=model,
                provider="ollama-local",
            )
        return session_manager.ProviderResponse(
            content="Estás trabajando en C:\\demo\\project.",
            model_used=model,
            provider="ollama-local",
        )

    def supports_tools(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return False

    def supports_embeddings(self) -> bool:
        return False

    def health_check(self, timeout: float = 5.0):
        return SimpleNamespace(ok=True, detail="ok", latency_ms=0.0)


class _WorkspaceErrorAdapter(_WorkspaceEchoAdapter):
    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        self.calls += 1
        self.systems.append(system)
        if "ROUTER DE ENTRADA BAGO" in system:
            return session_manager.ProviderResponse(
                content='{"kind":"workspace_question","command":"","args":[],"confidence":0.97,"reason":"router test"}',
                model_used=model,
                provider="ollama-local",
            )
        return session_manager.ProviderResponse(
            content="Ollama local no responde: timed out",
            model_used=model,
            provider="ollama-local",
            metadata={"error": "timed out"},
        )


def test_session_manager_rebinds_project_root(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    state_root = tmp_path / "state"

    monkeypatch.setattr(session_manager, "ConfigManager", _DummyConfig)
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
    monkeypatch.setattr(session_manager.SessionManager, "_init_adapter", lambda self: {"corrected": False, "requested": self.model, "actual": self.model, "available": []})

    mgr = session_manager.SessionManager(base_path=str(tmp_path / "home"), state_root=str(state_root))
    mgr.rebind_project_root(project)

    assert mgr.base_path == mgr.workspace_mirror_root
    assert mgr.project_root == project
    assert mgr.workspace_scope_root == project
    assert mgr.workspace_state_root == project / ".gabo"
    assert mgr.workspace_manifest == project / ".gabo" / "workspace.json"
    assert mgr.store.get_meta()["project_root"] == str(project)
    assert mgr.store.get_meta()["workspace_state_root"] == str(project / ".gabo")


def test_project_command_rebinds_before_action(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    calls = []

    def fake_load_tool_module(name: str, filename: str):
        return SimpleNamespace(
            resolve_project_root=lambda root, allow_fallback_cwd=False: project,
            init_project=lambda root: {"bago_dir": str(root / ".bago")},
            status_data=lambda root: {"project_root": str(root), "workspace_state_root": str(root / ".gabo")},
            link_project=lambda root: {"root": str(root), "link_mode": "portable", "marker": str(root / ".bago" / "link.json")},
            analyze_data=lambda root: {"project_root": str(root), "workspace_state_root": str(root / ".gabo")},
            format_status=lambda data: "status",
            format_analysis=lambda data: "analysis",
        )

    class DummyMgr:
        def rebind_project_root(self, root):
            calls.append(Path(root))

    monkeypatch.setattr(commands, "_load_tool_module", fake_load_tool_module)

    result = commands.cmd_project(DummyMgr(), SimpleNamespace(), ["status", str(project)])

    assert result["ok"] is True
    assert calls == [project]


def test_project_command_without_path_uses_active_project(tmp_path, monkeypatch):
    active = tmp_path / "active"
    active.mkdir()
    calls = []

    def fake_load_tool_module(name: str, filename: str):
        return SimpleNamespace(
            resolve_project_root=lambda root, allow_fallback_cwd=False: tmp_path / "wrong",
            analyze_data=lambda root: calls.append(Path(root)) or {
                "project_root": str(root),
                "workspace_state_root": str(root / ".gabo"),
            },
            format_analysis=lambda data: "analysis",
        )

    class DummyMgr:
        project_root = active
        base_path = tmp_path / "cwd"

        def rebind_project_root(self, root):
            calls.append(Path(root))

    monkeypatch.setattr(commands, "_load_tool_module", fake_load_tool_module)

    result = commands.cmd_project(DummyMgr(), SimpleNamespace(), ["analyze"])

    assert result["ok"] is True
    assert calls == [active, active]


def test_project_wizard_rebinds_selected_path(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    calls = []

    class DummyMgr:
        def rebind_project_root(self, root):
            calls.append(Path(root))

    class DummyREPL:
        def __init__(self):
            self.mgr = DummyMgr()

        def _wizard_tty_ok(self, *_args):
            return True

        def _navigate(self, *_args):
            return 4

    repl = DummyREPL()
    monkeypatch.setattr(repl_menu, "_load_tool_module", lambda name, filename: SimpleNamespace(
        find_project_root=lambda root: None,
        analyze_data=lambda root: {"project_root": str(root), "workspace_state_root": str(root / ".gabo")},
        format_analysis=lambda data: "analysis",
    ))
    monkeypatch.setattr(repl_menu.R, "warn", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "dim", lambda text: text)
    monkeypatch.setattr(builtins, "input", lambda prompt="": str(project))

    assert repl_menu.BagoReplMenuMixin._project_wizard(repl, Path(tmp_path)) is True

    assert calls == [project]


def test_project_wizard_uses_exact_active_path_not_parent(tmp_path, monkeypatch):
    project = tmp_path / "project"
    parent = tmp_path / "parent"
    project.mkdir()
    parent.mkdir()
    calls = []

    class DummyMgr:
        def rebind_project_root(self, root):
            calls.append(Path(root))

    class DummyREPL:
        def __init__(self):
            self.mgr = DummyMgr()

        def _wizard_tty_ok(self, *_args):
            return True

        def _navigate(self, *_args):
            return 0

    repl = DummyREPL()
    monkeypatch.setattr(repl_menu, "_load_tool_module", lambda name, filename: SimpleNamespace(
        find_project_root=lambda root: parent,
        analyze_data=lambda root: {
            "root": str(root),
            "configured": False,
            "linked": False,
            "link_mode": "none",
            "stack": [],
            "issues": [],
            "suggestions": [],
            "tree": "",
        },
        format_analysis=lambda data: "analysis",
    ))
    monkeypatch.setattr(repl_menu.R, "ok", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "dim", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "warn", lambda text: text)

    assert repl_menu.BagoReplMenuMixin._project_wizard(repl, project) is True

    assert calls == [project]


def test_menu_does_not_auto_audit_invalid_workspace(tmp_path, monkeypatch, capsys):
    project = tmp_path / "project"
    project.mkdir()
    calls = []

    class DummyREPL:
        mgr = SimpleNamespace(base_path=project)

        def _navigate(self, *_args):
            return None

    monkeypatch.setattr(repl_menu, "menu_state_for_manager", lambda mgr: {
        "workspace_state": {
            "project_root": str(project),
            "workspace_state_root": str(project / ".gabo"),
            "workspace_state": "invalid",
        },
        "sections": repl_menu.MENU_SECTIONS,
    })
    monkeypatch.setattr(repl_menu, "_load_tool_module", lambda name, filename: SimpleNamespace(
        find_project_root=lambda root: project,
        analyze_data=lambda root: calls.append(Path(root)) or {
            "root": str(root),
            "configured": False,
            "linked": False,
            "link_mode": "none",
            "stack": ["node", "docs"],
            "issues": ["issue visible"],
            "suggestions": ["npm test"],
            "tree": "Directory snapshot:\n[D] hidden",
        },
        format_analysis=lambda data: f"AUDIT {data['project_root']}",
    ))
    monkeypatch.setattr(repl_menu.R, "dim", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "warn", lambda text: text)
    monkeypatch.setattr(repl_menu.sys.stdout, "isatty", lambda: True)

    repl_menu.BagoReplMenuMixin._show_menu(DummyREPL())
    out = capsys.readouterr().out

    assert calls == []
    assert "Auditoría automática del directorio concreto:" not in out
    assert f"Project root: {project}" not in out
    assert "Stack: node, docs" not in out


def test_menu_skips_auto_audit_without_concrete_root(tmp_path, monkeypatch, capsys):
    calls = []
    missing = tmp_path / "missing"

    class DummyREPL:
        mgr = SimpleNamespace(base_path=missing, project_root=missing)

        def _navigate(self, *_args):
            return None

    monkeypatch.setattr(repl_menu, "menu_state_for_manager", lambda mgr: {
        "workspace_state": {
            "project_root": str(missing),
            "workspace_state_root": str(missing / ".gabo"),
            "workspace_state": "invalid",
        },
        "sections": repl_menu.MENU_SECTIONS,
    })
    monkeypatch.setattr(repl_menu, "_load_tool_module", lambda name, filename: SimpleNamespace(
        analyze_data=lambda root: calls.append(Path(root)) or {"project_root": str(root), "workspace_state_root": str(root / ".gabo")},
        format_analysis=lambda data: f"AUDIT {data['project_root']}",
    ))
    monkeypatch.setattr(repl_menu.R, "dim", lambda text: text)
    monkeypatch.setattr(repl_menu.R, "warn", lambda text: text)
    monkeypatch.setattr(repl_menu.sys.stdout, "isatty", lambda: True)

    repl_menu.BagoReplMenuMixin._show_menu(DummyREPL())
    out = capsys.readouterr().out

    assert calls == []
    assert "No hay un directorio concreto para auditar" not in out


def test_workspace_reply_is_rewritten_when_model_echoes_context(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    adapter = _WorkspaceEchoAdapter()

    monkeypatch.setattr(session_manager, "ConfigManager", _DummyConfig)
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
    monkeypatch.setattr(session_manager.SessionManager, "_init_adapter", lambda self: setattr(self, "_adapter", adapter) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []})

    mgr = session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))
    try:
        reply = mgr.send("si?")
    finally:
        mgr.close()

    assert reply == f"El proyecto activo es {project}."
    assert adapter.calls >= 2
    assert any("ROUTER DE ENTRADA BAGO" in system for system in adapter.systems)
    assert any("PREGUNTA SOBRE EL PROYECTO ACTIVO" in system for system in adapter.systems)


def test_workspace_question_falls_back_when_provider_times_out(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    adapter = _WorkspaceErrorAdapter()

    monkeypatch.setattr(session_manager, "ConfigManager", _DummyConfig)
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
    monkeypatch.setattr(session_manager.SessionManager, "_init_adapter", lambda self: setattr(self, "_adapter", adapter) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []})

    mgr = session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))
    try:
        reply = mgr.send("DE QUE HABLAMOS?")
    finally:
        mgr.close()

    assert reply == f"El proyecto activo es {project}."
    assert adapter.calls >= 2
    assert any("ROUTER DE ENTRADA BAGO" in system for system in adapter.systems)
    assert any("PREGUNTA SOBRE EL PROYECTO ACTIVO" in system for system in adapter.systems)
