"""test_f1_version_workspace.py — Regression tests for F1: version/workspace unification.

- bago_core.__version__ is not hardcoded to 4.7.0
- SessionDB schema has workspace_state_root column
- SessionManager.save() persists workspace_state_root in session JSON
- SessionManager.load() restores workspace_state_root when it exists
- No '4.7.0' fallbacks remain in ui-react/src/**/*.{js,jsx}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


# ── 1. bago_core.__version__ is dynamic ──────────────────────────────

def test_bago_core_version_not_hardcoded_47():
    """bago_core.__init__.py must not contain a hardcoded 4.7.0 string."""
    init_file = REPO_ROOT / "bago_core" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    assert "4.7.0" not in content, (
        "bago_core/__init__.py still has hardcoded 4.7.0 — must use versioning.current()"
    )


def test_bago_core_version_matches_release():
    """bago_core.__version__ must equal release_version.txt."""
    from bago_core.versioning import current
    rv = (REPO_ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
    assert current() == rv, f"versioning.current()={current()!r} != release_version.txt={rv!r}"


# ── 2. SessionDB has workspace_state_root column ─────────────────────

def test_session_db_schema_has_workspace_state_root():
    """SessionDB schema must include workspace_state_root column."""
    schema_file = REPO_ROOT / ".bago" / "core" / "session_db.py"
    content = schema_file.read_text(encoding="utf-8")
    assert "workspace_state_root" in content, (
        "session_db.py must reference workspace_state_root in schema and upsert"
    )
    assert "context_revision" in content, (
        "session_db.py must track context_revision in schema and upsert"
    )


def test_session_db_upsert_accepts_workspace_state_root():
    """SessionDB.upsert() must accept workspace_state_root as a field."""
    from session_db import SessionDB
    with tempfile.TemporaryDirectory() as td:
        db = SessionDB(td)
        db.upsert("test-sid", last_provider="ollama-local", workspace_state_root="/tmp/fake-ws")
        row = db.get("test-sid")
        assert row is not None
        assert row["workspace_state_root"] == "/tmp/fake-ws"


def test_session_db_upsert_accepts_context_revision():
    """SessionDB.upsert() must accept context_revision as a field."""
    from session_db import SessionDB
    with tempfile.TemporaryDirectory() as td:
        db = SessionDB(td)
        db.upsert("test-sid", last_provider="ollama-local", context_revision="abc123")
        row = db.get("test-sid")
        assert row is not None
        assert row["context_revision"] == "abc123"


# ── 3. SessionManager persists workspace_state_root ──────────────────

def test_session_manager_save_persists_workspace_state_root():
    """SessionManager.save() must include workspace_state_root in session JSON."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f1-save",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
            session_path = Path(td) / "sessions" / "test-f1-save.json"
            data = json.loads(session_path.read_text(encoding="utf-8"))
            assert data.get("project_root") == ws, (
                f"project_root in JSON = {data.get('project_root')!r}, expected {ws!r}"
            )
            assert data.get("workspace_state_root") == str(Path(ws) / ".gabo"), (
                f"workspace_state_root in JSON = {data.get('workspace_state_root')!r}, expected {str(Path(ws) / '.gabo')!r}"
            )
        finally:
            mgr.close()


def test_session_manager_load_restores_workspace_state_root():
    """SessionManager.load() must restore workspace_state_root when the path exists."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f1-load",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
        finally:
            mgr.close()

        # Load from a different CWD — should restore workspace_state_root, not use cwd
        other_cwd = tempfile.mkdtemp()
        os.chdir(other_cwd)
        try:
            loaded = SessionManager.load("test-f1-load", state_root=td)
            try:
                assert str(loaded.base_path) == str(loaded.workspace_mirror_root)
                assert str(loaded.project_root) == ws
                assert str(loaded.workspace_state_root) == str(Path(ws) / ".gabo")
            finally:
                loaded.close()
        finally:
            os.chdir(ws)  # restore


def test_session_manager_status_exposes_workspace_binding():
    """SessionManager.status() must expose workspace/repo binding and context revision."""
    from session_manager import ADAPTER_REGISTRY, SessionManager
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage

    class MockAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("workspace-mock", config)

        def chat(self, messages: list[dict], model: str, **kwargs):
            system = str(kwargs.get("system", ""))
            if "ROUTER DE ENTRADA BAGO" in system:
                text = " ".join(str(msg.get("content", "")) for msg in messages if str(msg.get("role", "")).lower() == "user").lower()
                if any(token in text for token in ("directorio", "workspace", "proyecto", "abierto", "activo", "operas")):
                    return ProviderResponse(
                        content='{"kind":"workspace_question","command":"","args":[],"confidence":0.97,"reason":"router test"}',
                        model_used=model,
                        provider=self.provider_name,
                        finish_reason="stop",
                        usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
                    )
                return ProviderResponse(
                    content="ok",
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
                )
            return ProviderResponse(
                content="ok",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5, calls=1),
            )

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("mock-model", "mock-model", self.provider_name, 4096, 1024, "test", "free")]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

    ADAPTER_REGISTRY["workspace-mock"] = MockAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = tempfile.mkdtemp()
            subprocess.run(["git", "-C", ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", ws, "-c", "user.name=Codex", "-c", "user.email=codex@example.com", "commit", "--allow-empty", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            mgr = SessionManager(
                session_id="test-f1-status",
                provider="workspace-mock",
                model="mock-model",
                base_path=ws,
                state_root=td,
            )
            try:
                status = mgr.status()
                assert status["project_root"] == ws
                assert status["workspace_state_root"] == str(Path(ws) / ".gabo")
                assert status["workspace_scope_root"] == ws
                assert status["framework_root"].endswith(".bago")
                assert status["authorized_root"] == str(mgr.workspace_mirror_root)
                assert status["objective"] == ""
                assert status["context_revision"] == ""
                assert status["context_measure"]["ok"] is True
                assert status["context_measure"]["budget"]["input_budget"] > 0

                mgr.set_goal("Inspeccionar contexto")
                response = mgr.send("hola")
                assert response == "ok"
                assert mgr.last_receipt is not None
                assert mgr.context_revision == mgr.last_receipt.envelope_id

                measure = mgr.measure_context()
                assert measure["ok"] is True
                assert measure["workspace_state_root"] == str(Path(ws) / ".gabo")
                assert "binding_reason" in measure["binding"]
                assert measure["budget"]["available_tokens"] >= 0
                assert mgr.last_budget_report is not None

                benchmark = mgr.benchmark_context(4)
                assert benchmark["ok"] is True
                assert benchmark["workspace_state_root"] == str(Path(ws) / ".gabo")
                assert benchmark["iterations"] == 4
                assert benchmark["elapsed_ms"]["avg"] >= 0
                assert benchmark["budget"]["available_tokens"]["min"] >= 0
                assert mgr.last_context_benchmark == benchmark

                certification = mgr.certify_context()
                assert certification["ok"] is False
                assert certification["workspace_state_root"] == str(Path(ws) / ".gabo")
                assert certification["status"] == "NO_CERTIFIED"
                assert any(item["name"] == "receipt_validation" for item in certification["failures"])
                assert mgr.last_context_certification == certification

                status_after = mgr.status()
                assert status_after["objective"] == "Inspeccionar contexto"
                assert status_after["context_revision"] == mgr.last_receipt.envelope_id
                assert status_after["last_receipt"]["envelope_id"] == mgr.last_receipt.envelope_id
                assert status_after["context_measure"]["ok"] is True
                assert status_after["context_benchmark"]["iterations"] == 4
                assert status_after["context_certification"]["status"] == "NO_CERTIFIED"

                mgr.save()
            finally:
                mgr.close()

            loaded = SessionManager.load("test-f1-status", state_root=td)
            try:
                loaded_status = loaded.status()
                assert loaded_status["project_root"] == ws
                assert loaded_status["workspace_state_root"] == str(Path(ws) / ".gabo")
                assert loaded_status["context_revision"] == status_after["context_revision"]
                assert loaded_status["last_receipt"]["envelope_id"] == status_after["context_revision"]
                assert loaded_status["context_certification"]["status"] == "NO_CERTIFIED"
            finally:
                loaded.close()
    finally:
        ADAPTER_REGISTRY.pop("workspace-mock", None)


def test_session_manager_global_review_activates_from_context_plan():
    """High-risk context plans must surface global review requirements."""
    from session_manager import ADAPTER_REGISTRY, SessionManager
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage

    class MockAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("workspace-mock-review", config)

        def chat(self, messages: list[dict], model: str, **kwargs):
            return ProviderResponse(
                content="ok",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
            )

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("mock-model", "mock-model", self.provider_name, 4096, 1024, "test", "free")]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

    ADAPTER_REGISTRY["workspace-mock-review"] = MockAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = tempfile.mkdtemp()
            subprocess.run(["git", "-C", ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", ws, "-c", "user.name=Codex", "-c", "user.email=codex@example.com", "commit", "--allow-empty", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            mgr = SessionManager(
                session_id="test-f1-global-review",
                provider="workspace-mock-review",
                model="mock-model",
                base_path=ws,
                state_root=td,
            )
            try:
                fragments, _ = mgr._workspace_context_pack("revisa contrato y branch del repo", None)
                assert fragments is not None
                status = mgr.status()
                review = status["global_review"]
                assert review["required"] is True
                assert any(reason.startswith("planner:") or reason in {"high_risk", "strict_verification"} for reason in review["reasons"])
                assert status["review_required"] is True
                assert status["context_plan"]["global_review_required"] is True
                assert status["context_route"]["request_id"]
            finally:
                mgr.close()
    finally:
        ADAPTER_REGISTRY.pop("workspace-mock-review", None)


def test_session_control_measure_command_exposes_budget():
    """session_control measure must expose a live context budget snapshot."""
    import bago_core.session_control as session_control
    from unittest.mock import patch

    class FakeAgentGateway:
        class _Agent:
            name = "main"

        active = _Agent()

        def list_agents(self):
            return []

    class FakeStore:
        def get_history(self):
            return [{"role": "user", "content": "hola"}]

    class FakeMgr:
        session_id = "sid-measure"
        provider = "ollama-local"
        model = "llama3.2:3b"
        agent_gateway = FakeAgentGateway()
        store = FakeStore()

        def measure_context(self):
            return {"ok": True, "budget": {"usage_fraction": 0.25, "available_tokens": 1024}}

        def status(self):
            return {
                "session_id": self.session_id,
                "provider": self.provider,
                "model": self.model,
                "workspace_state_root": "C:/ws",
                "authorized_root": "C:/ws",
                "repo_root": "C:/repo",
                "repo_branch": "main",
                "objective": "",
                "context_revision": "",
                "binding_confirmed": True,
                "binding_reason": "ok",
                "active_agent": "main",
                "active_bridges": ["ollama-local"],
                "health": {"ok": True, "detail": "ok", "latency_ms": 1.0},
                "messages": 1,
                "total_tokens": 0,
                "total_calls": 0,
                "created_at": 1.0,
                "last_switch_at": None,
                "switches": 0,
                "last_receipt": {},
                "context_measure": self.measure_context(),
            }

        def available_providers(self):
            return [{"id": "ollama-local"}]

        def save(self):
            return None

        def close(self):
            return None

    with patch.object(session_control.SessionManager, "load", return_value=FakeMgr()):
        args = session_control.build_parser().parse_args([
            "--base-path", "C:/ws",
            "measure",
            "--session-id", "sid-measure",
        ])
        payload = session_control.run(args)

    assert payload["ok"] is True
    assert payload["measure"]["budget"]["available_tokens"] == 1024
    assert payload["session"]["context_measure"]["ok"] is True


def test_session_control_benchmark_command_exposes_summary():
    """session_control benchmark must expose an aggregated benchmark summary."""
    import bago_core.session_control as session_control
    from unittest.mock import patch

    class FakeMgr:
        session_id = "sid-benchmark"
        provider = "ollama-local"
        model = "llama3.2:3b"
        last_context_benchmark = None

        class _AgentGateway:
            class _Agent:
                name = "main"

            def list_agents(self):
                return [self._Agent()]

        agent_gateway = _AgentGateway()

        class _Store:
            def get_history(self):
                return [{"role": "user", "content": "hola"}]

        store = _Store()

        def benchmark_context(self, iterations=3):
            self.last_context_benchmark = {
                "ok": True,
                "iterations": iterations,
                "elapsed_ms": {"avg": 1.5},
                "budget": {"available_tokens": {"min": 512}},
            }
            return self.last_context_benchmark

        def status(self):
            return {
                "session_id": self.session_id,
                "provider": self.provider,
                "model": self.model,
                "workspace_state_root": "C:/ws",
                "authorized_root": "C:/ws",
                "repo_root": "C:/repo",
                "repo_branch": "main",
                "objective": "",
                "context_revision": "",
                "binding_confirmed": True,
                "binding_reason": "ok",
                "active_agent": "main",
                "active_bridges": ["ollama-local"],
                "health": {"ok": True, "detail": "ok", "latency_ms": 1.0},
                "messages": 1,
                "total_tokens": 0,
                "total_calls": 0,
                "created_at": 1.0,
                "last_switch_at": None,
                "switches": 0,
                "last_receipt": {},
                "context_measure": {"ok": True, "budget": {"available_tokens": 1024}},
                "context_benchmark": self.last_context_benchmark,
            }

        def available_providers(self):
            return [{"id": "ollama-local"}]

        def save(self):
            return None

        def close(self):
            return None

    with patch.object(session_control.SessionManager, "load", return_value=FakeMgr()):
        args = session_control.build_parser().parse_args([
            "--base-path", "C:/ws",
            "benchmark",
            "--session-id", "sid-benchmark",
            "--iterations", "5",
        ])
        payload = session_control.run(args)

    assert payload["ok"] is True
    assert payload["benchmark"]["iterations"] == 5
    assert payload["benchmark"]["budget"]["available_tokens"]["min"] == 512
    assert payload["session"]["context_benchmark"]["iterations"] == 5


def test_session_control_certify_command_exposes_verdict():
    """session_control certify must expose a certification verdict."""
    import bago_core.session_control as session_control
    from unittest.mock import patch

    class FakeMgr:
        session_id = "sid-certify"
        provider = "ollama-local"
        model = "llama3.2:3b"
        last_context_certification = None

        class _AgentGateway:
            class _Agent:
                name = "main"

            def list_agents(self):
                return [self._Agent()]

        agent_gateway = _AgentGateway()

        class _Store:
            def get_history(self):
                return [{"role": "user", "content": "hola"}]

        store = _Store()

        def certify_context(self):
            self.last_context_certification = {
                "ok": True,
                "status": "CERTIFIED",
                "failures": [],
                "context_revision": "env-1",
            }
            return self.last_context_certification

        def status(self):
            return {
                "session_id": self.session_id,
                "provider": self.provider,
                "model": self.model,
                "workspace_state_root": "C:/ws",
                "authorized_root": "C:/ws",
                "repo_root": "C:/repo",
                "repo_branch": "main",
                "objective": "",
                "context_revision": "env-1",
                "binding_confirmed": True,
                "binding_reason": "ok",
                "active_agent": "main",
                "active_bridges": ["ollama-local"],
                "health": {"ok": True, "detail": "ok", "latency_ms": 1.0},
                "messages": 1,
                "total_tokens": 0,
                "total_calls": 0,
                "created_at": 1.0,
                "last_switch_at": None,
                "switches": 0,
                "last_receipt": {"envelope_id": "env-1"},
                "context_measure": {"ok": True, "budget": {"available_tokens": 1024}},
                "context_benchmark": {"ok": True, "iterations": 3, "elapsed_ms": {"avg": 1.0}, "budget": {"available_tokens": {"min": 512}}},
                "context_certification": self.last_context_certification,
            }

        def available_providers(self):
            return [{"id": "ollama-local"}]

        def save(self):
            return None

        def close(self):
            return None

    with patch.object(session_control.SessionManager, "load", return_value=FakeMgr()):
        args = session_control.build_parser().parse_args([
            "--base-path", "C:/ws",
            "certify",
            "--session-id", "sid-certify",
        ])
        payload = session_control.run(args)

    assert payload["ok"] is True
    assert payload["certification"]["status"] == "CERTIFIED"
    assert payload["session"]["context_certification"]["status"] == "CERTIFIED"


def test_chat_context_command_uses_workspace_state_root():
    """/context inspect and measure must read workspace_state_root, not workspace_root."""
    import importlib.util

    commands_path = REPO_ROOT / ".bago" / "chat" / "commands.py"
    spec = importlib.util.spec_from_file_location("bago_chat_commands", commands_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeMgr:
        def inspect_context(self):
            return {
                "session_id": "sid-context",
                "workspace_state_root": "C:/ws/.gabo",
                "repo_branch": "main",
                "repo_root": "C:/ws",
                "provider": "ollama-local",
                "model": "llama3.2:3b",
                "binding_confirmed": True,
                "binding_reason": "ok",
                "context_revision": "rev-1",
                "last_receipt": {"envelope_id": "rev-1"},
            }

        def measure_context(self):
            return {
                "workspace_state_root": "C:/ws/.gabo",
                "provider": "ollama-local",
                "model": "llama3.2:3b",
                "model_context_tokens": 8192,
                "budget": {"available_tokens": 1024, "usage_fraction": 0.25},
            }

    inspect = module.cmd_context(FakeMgr(), None, ["inspect"])
    measure = module.cmd_context(FakeMgr(), None, ["measure"])

    assert inspect["ok"] is True
    assert "Workspace  : C:/ws/.gabo" in inspect["message"]
    assert measure["ok"] is True
    assert "Workspace  : C:/ws/.gabo" in measure["message"]


def test_chat_status_and_session_expose_workspace_roots():
    """/status and /session must expose project_root and workspace_state_root."""
    import importlib.util

    commands_path = REPO_ROOT / ".bago" / "chat" / "commands.py"
    spec = importlib.util.spec_from_file_location("bago_chat_commands_status", commands_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeMgr:
        def status(self):
            return {
                "session_id": "sid-status",
                "project_root": "C:/ws",
                "workspace_state_root": "C:/ws/.gabo",
                "provider": "ollama-local",
                "model": "llama3.2:3b",
                "bago_mode": "B",
                "active_agent": "default",
                "active_bridges": ["ollama-local"],
                "health": {"ok": True, "detail": "ok"},
                "messages": 1,
                "total_tokens": 0,
                "total_calls": 0,
                "switches": 0,
                "created_at": 1.0,
            }

    status = module.cmd_status(FakeMgr(), None, [])
    session = module.cmd_session(FakeMgr(), None, [])

    assert status["ok"] is True
    assert "Project    : C:/ws" in status["message"]
    assert "Workspace  : C:/ws/.gabo" in status["message"]
    assert session["ok"] is True
    assert session["data"]["project_root"] == "C:/ws"
    assert session["data"]["workspace_state_root"] == "C:/ws/.gabo"
    assert "Workspace  : C:/ws/.gabo" in session["message"]


def test_menu_shows_workspace_roots_in_header():
    """The interactive menu must not dump workspace roots before rendering."""
    import io
    import importlib.util
    import sys

    repl_menu_path = REPO_ROOT / ".bago" / "chat" / "repl_menu.py"
    spec = importlib.util.spec_from_file_location("bago_repl_menu", repl_menu_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeMgr:
        def workspace_state(self):
            return {
                "project_root": "C:/ws",
                "workspace_state_root": "C:/ws/.gabo",
                "workspace_state": "linked_confirmed",
            }

    class FakeMenu(module.BagoReplMenuMixin):
        def __init__(self):
            self.mgr = FakeMgr()

        def _navigate(self, title: str, labels: list[str], hint: str | None = None):
            return None

    fake_stdout = io.StringIO()
    fake_stdout.isatty = lambda: True  # type: ignore[attr-defined]
    old_stdout = sys.stdout
    sys.stdout = fake_stdout
    try:
        shown = FakeMenu()._show_menu()
    finally:
        sys.stdout = old_stdout

    output = fake_stdout.getvalue()
    assert shown is True
    assert "Project   : C:/ws" not in output
    assert "Workspace : C:/ws/.gabo" not in output
    assert "Estado    : linked_confirmed" not in output


def test_session_manager_send_short_circuits_workspace_questions():
    """Workspace questions must still invoke the adapter and then normalize the reply."""
    from session_manager import ADAPTER_REGISTRY, SessionManager
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage

    class MockAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("workspace-mock", config)
            self.calls = 0
            self.stream_calls = 0

        def chat(self, messages: list[dict], model: str, **kwargs):
            self.calls += 1
            system = str(kwargs.get("system", ""))
            if "ROUTER DE ENTRADA BAGO" in system:
                all_text = " ".join(str(msg.get("content", "")) for msg in messages).lower()
                user_texts = [
                    str(msg.get("content", "")).lower()
                    for msg in messages
                    if str(msg.get("role", "")).lower() == "user"
                ]
                text = user_texts[-1] if user_texts else ""
                has_workspace_context = any(token in all_text for token in ("directorio", "workspace", "proyecto", "abierto", "activo", "operas"))
                short_followup = any(token in text for token in ("y ahora", "ahora", "de que", "de qué"))
                if has_workspace_context and (any(token in text for token in ("directorio", "workspace", "proyecto", "abierto", "activo", "operas")) or short_followup):
                    return ProviderResponse(
                        content='{"kind":"workspace_question","command":"","args":[],"confidence":0.97,"reason":"router test"}',
                        model_used=model,
                        provider=self.provider_name,
                        finish_reason="stop",
                        usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
                    )
                return ProviderResponse(
                    content="ok",
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5, calls=1),
                )
            return ProviderResponse(
                content="Proyecto activo: ?",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
            )

        def chat_stream(self, messages: list[dict], model: str, **kwargs):
            self.stream_calls += 1
            yield "Proyecto activo: ?"

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("mock-model", "mock-model", self.provider_name, 4096, 1024, "test", "free")]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return True

    ADAPTER_REGISTRY["workspace-mock"] = MockAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = tempfile.mkdtemp()
            canonical = f"El proyecto activo es {Path(ws)}."
            direct = "Trabajo sobre project_root="
            mgr = SessionManager(
                session_id="test-f1-direct-workspace",
                provider="workspace-mock",
                model="mock-model",
                base_path=ws,
                state_root=td,
            )
            try:
                response = mgr.send("¿Desde qué directorio trabajas?")
                assert response == canonical or response.startswith(direct)
                assert mgr.last_receipt is not None
                assert mgr._adapter.calls >= 1

                response2 = mgr.send("¿Cuál es el estado del workspace?")
                assert response2 == canonical or response2.startswith(direct)
                assert mgr.last_receipt is not None
                assert mgr._adapter.calls >= 2

                streamed = list(mgr.send_stream("¿Qué workspace tienes activo?"))
                assert len(streamed) == 1
                assert streamed[0] == canonical or streamed[0].startswith(direct)
                assert mgr.last_receipt is not None

                streamed2 = list(mgr.send_stream("¿Qué proyecto está abierto?"))
                assert len(streamed2) == 1
                assert streamed2[0] == canonical or streamed2[0].startswith(direct)
                assert mgr.last_receipt is not None

                followup = mgr.send("¿Y ahora?")
                assert followup == canonical or followup.startswith(direct)
                assert mgr.last_receipt is not None
                assert mgr._adapter.calls >= 3
            finally:
                mgr.close()
    finally:
        ADAPTER_REGISTRY.pop("workspace-mock", None)


def test_session_manager_certify_fails_when_benchmark_missing():
    """Missing benchmark must fail certification."""
    from session_manager import ADAPTER_REGISTRY, SessionManager
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage

    class MockAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("workspace-mock", config)

        def chat(self, messages: list[dict], model: str, **kwargs):
            system = str(kwargs.get("system", ""))
            if "ROUTER DE ENTRADA BAGO" in system:
                text = " ".join(str(msg.get("content", "")) for msg in messages if str(msg.get("role", "")).lower() == "user").lower()
                if any(token in text for token in ("directorio", "workspace", "proyecto", "abierto", "activo", "operas")):
                    return ProviderResponse(
                        content='{"kind":"workspace_question","command":"","args":[],"confidence":0.97,"reason":"router test"}',
                        model_used=model,
                        provider=self.provider_name,
                        finish_reason="stop",
                        usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
                    )
                return ProviderResponse(
                    content="ok",
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4, calls=1),
                )
            return ProviderResponse(
                content="ok",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5, calls=1),
            )

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("mock-model", "mock-model", self.provider_name, 4096, 1024, "test", "free")]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

    ADAPTER_REGISTRY["workspace-mock"] = MockAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = tempfile.mkdtemp()
            subprocess.run(["git", "-C", ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", ws, "-c", "user.name=Codex", "-c", "user.email=codex@example.com", "commit", "--allow-empty", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            mgr = SessionManager(
                session_id="test-f1-cert-fail",
                provider="workspace-mock",
                model="mock-model",
                base_path=ws,
                state_root=td,
            )
            try:
                mgr.set_goal("Inspeccionar contexto")
                mgr.send("hola")
                mgr.last_context_benchmark = None
                certification = mgr.certify_context()
                assert certification["ok"] is False
                assert certification["status"] == "NO_CERTIFIED"
                assert any(item["name"] == "benchmark_present" for item in certification["failures"])
            finally:
                mgr.close()
    finally:
        ADAPTER_REGISTRY.pop("workspace-mock", None)


def test_session_manager_certify_fails_on_mutated_benchmark():
    """Mutated benchmark state must fail certification."""
    from session_manager import ADAPTER_REGISTRY, SessionManager
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage

    class MockAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("workspace-mock", config)

        def chat(self, messages: list[dict], model: str, **kwargs):
            return ProviderResponse(
                content="ok",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5, calls=1),
            )

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("mock-model", "mock-model", self.provider_name, 4096, 1024, "test", "free")]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

    ADAPTER_REGISTRY["workspace-mock"] = MockAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            ws = tempfile.mkdtemp()
            subprocess.run(["git", "-C", ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", ws, "-c", "user.name=Codex", "-c", "user.email=codex@example.com", "commit", "--allow-empty", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            mgr = SessionManager(
                session_id="test-f1-cert-mut",
                provider="workspace-mock",
                model="mock-model",
                base_path=ws,
                state_root=td,
            )
            try:
                mgr.set_goal("Inspeccionar contexto")
                mgr.send("hola")
                mgr.benchmark_context(2)
                mgr.last_context_benchmark["session_id"] = "fake"
                certification = mgr.certify_context()
                assert certification["ok"] is False
                assert certification["status"] == "NO_CERTIFIED"
                assert any(item["name"] == "benchmark_session" for item in certification["failures"])
            finally:
                mgr.close()
    finally:
        ADAPTER_REGISTRY.pop("workspace-mock", None)


def test_session_manager_binding_breaks_on_workspace_mutation():
    """A persisted workspace_state_root mutation must break binding confirmation."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        subprocess.run(["git", "-C", ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
        mgr = SessionManager(
            session_id="test-f1-binding",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
        finally:
            mgr.close()

        session_path = Path(td) / "sessions" / "test-f1-binding.json"
        data = json.loads(session_path.read_text(encoding="utf-8"))
        mutated_ws = tempfile.mkdtemp()
        subprocess.run(["git", "-C", mutated_ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
        data["project_root"] = mutated_ws
        data["workspace_state_root"] = str(Path(mutated_ws) / ".gabo")
        data["authorized_root"] = mutated_ws
        data["repo_root"] = ws
        data["repo_branch"] = "main"
        session_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        loaded = SessionManager.load("test-f1-binding", state_root=td)
        try:
            status = loaded.status()
            assert status["project_root"] == mutated_ws
            assert status["binding_confirmed"] is False
            assert "mismatch" in status["binding_reason"]
        finally:
            loaded.close()


def test_session_manager_binding_breaks_on_repo_branch_mutation():
    """A persisted repo_branch mutation must break binding confirmation."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        subprocess.run(["git", "-C", ws, "init", "-b", "main"], check=True, capture_output=True, text=True)
        mgr = SessionManager(
            session_id="test-f1-branch",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
        finally:
            mgr.close()

        session_path = Path(td) / "sessions" / "test-f1-branch.json"
        data = json.loads(session_path.read_text(encoding="utf-8"))
        data["repo_branch"] = "feature/fake"
        session_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        loaded = SessionManager.load("test-f1-branch", state_root=td)
        try:
            status = loaded.status()
            assert status["binding_confirmed"] is False
            assert "branch" in status["binding_reason"]
        finally:
            loaded.close()


# ── 4. No 4.7.0 fallbacks in UI React ───────────────────────────────

def test_no_47_fallbacks_in_ui_react():
    """ui-react/src/**/*.{js,jsx} must not contain '4.7.0' fallbacks."""
    ui_dir = REPO_ROOT / "ui-react" / "src"
    if not ui_dir.exists():
        pytest.skip("ui-react/src not found")
    offenders = []
    for f in ui_dir.rglob("*"):
        if f.suffix not in (".js", ".jsx"):
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        if "4.7.0" in content:
            offenders.append(str(f.relative_to(REPO_ROOT)))
    assert not offenders, (
        f"Files still contain '4.7.0': {offenders}"
    )


def test_no_47_fallbacks_in_legacy_manager():
    """manager/js/legacy-manager.js must not contain '4.7' version strings."""
    legacy = REPO_ROOT / "manager" / "js" / "legacy-manager.js"
    if not legacy.exists():
        pytest.skip("legacy-manager.js not found")
    content = legacy.read_text(encoding="utf-8")
    # Look for version:"4.7" or '4.7' patterns (not 4.7.2 path references)
    matches = re.findall(r'version["\']?\s*[:=]\s*["\']4\.7[^.]', content)
    assert not matches, f"legacy-manager.js still has version 4.7 references: {matches}"
