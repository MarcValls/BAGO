from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


def _make_manager(tmp_path: str, workspace: str, provider: str = "fake-provider"):
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse
    import session_manager as sm

    class FakeAdapter(ProviderAdapter):
        def __init__(self, config=None):
            super().__init__(provider, config)

        def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
            from provider_adapter import ProviderResponse, TokenUsage
            prompt = ""
            if messages:
                last = messages[-1]
                prompt = str(last.get("content", ""))
            if "inventado" in self.provider_name:
                tool_calls = []
                if "NO TOOLS" in prompt:
                    tool_calls = [{"id": "tc1", "type": "function", "function": {"name": "fake_tool", "arguments": "{}"}}]
                return ProviderResponse(
                    content="inventado.py",
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
                    tool_calls=tool_calls,
                )
            if "OK-1" in prompt:
                content = "OK-1"
            elif "FALSO" in prompt or "2+2=5" in prompt:
                content = "FALSO"
            elif "SESSION_MANAGER" in prompt:
                content = "SESSION_MANAGER"
            elif "NO TOOLS" in prompt:
                content = "NO TOOLS"
            elif "NO SÉ" in prompt or "NO SE" in prompt:
                content = "NO SÉ"
            else:
                content = "respuesta fake"
            return ProviderResponse(
                content=content,
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=None,
            )

        def list_models(self):
            return [ModelInfo("fake-model", "fake-model", self.provider_name, 8192, 1024, "test", "free")]

        def health_check(self, timeout=5.0):
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok", latency_ms=1.0)

        def is_configured(self):
            return True

        def supports_tools(self):
            return True

        def supports_streaming(self):
            return False

    sm.ADAPTER_REGISTRY[provider] = FakeAdapter
    mgr = sm.SessionManager(
        session_id="ctx-test",
        provider=provider,
        model="fake-model",
        base_path=workspace,
        state_root=tmp_path,
    )
    return mgr, sm


def test_context_receipt_and_envelope_capture_workspace_state():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        source = Path(workspace) / "module_a.py"
        source.write_text("def ping():\n    return 'pong'\n", encoding="utf-8")
        mgr, sm = _make_manager(td, workspace)
        try:
            response = mgr.send("cambia module_a.py y dime que hace")
            assert response
            assert mgr.last_code_task is not None
            assert mgr.last_code_task["kind"] == "modify_file"
            assert mgr.last_context_envelope is not None
            assert mgr.last_receipt is not None
            assert mgr.last_receipt.workspace_used == str(mgr.base_path)
            assert mgr.last_receipt.workspace_state_root == str(Path(workspace) / ".gabo")
            assert mgr.last_receipt.provider_used == "fake-provider"
            assert mgr.last_receipt.tokens_sent >= 0
            assert mgr.last_context_envelope.workspace_state_root == str(Path(workspace) / ".gabo")
            assert mgr.last_context_envelope.model_name == "fake-model"
            assert mgr.last_context_envelope.session_summary["workspace_state_root"] == str(Path(workspace) / ".gabo")
            assert any("module_a.py" in path for path in mgr.last_receipt.files_represented)
            status = mgr.status()
            assert status["last_envelope"]["workspace_state_root"] == str(Path(workspace) / ".gabo")
            assert status["workspace_state_root"] == str(Path(workspace) / ".gabo")
            assert status["binding_confirmed"] in (True, False)
            assert "context_classification" in status
            assert "context_plan" in status
            assert "context_route" in status
            assert "context_retrieval" in status
            assert "global_review" in status
            assert "review_required" in status
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-provider", None)


def test_context_pack_uses_real_workspace_fragment():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        source = Path(workspace) / "module_b.py"
        source.write_text("VALUE = 42\n", encoding="utf-8")
        mgr, sm = _make_manager(td, workspace, provider="fake-pack")
        try:
            task = mgr._classify_code_request("modifica module_b.py")
            assert task is not None
            fragments, code_context = mgr._workspace_context_pack("modifica module_b.py", task)
            assert code_context is not None
            assert any("module_b.py" in frag.get("path", "") for frag in fragments if isinstance(frag, dict))
            assert any("VALUE = 42" in frag.get("content", "") for frag in fragments if isinstance(frag, dict))
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-pack", None)


def test_workspace_retrieval_finds_hidden_file_not_open():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        hidden = Path(workspace) / "notes" / "hidden_fact.md"
        hidden.parent.mkdir(parents=True, exist_ok=True)
        hidden.write_text("CANON-SECRET-81\n", encoding="utf-8")

        import session_manager as sm
        from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse

        class WorkspaceAdapter(ProviderAdapter):
            def __init__(self, config=None):
                super().__init__("workspace-rag", config)

            def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
                content = "FOUND" if "CANON-SECRET-81" in system else "NO HAY EVIDENCIA"
                return ProviderResponse(
                    content=content,
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=None,
                )

            def list_models(self):
                return [ModelInfo("workspace-model", "workspace-model", self.provider_name, 8192, 1024, "test", "free")]

            def health_check(self, timeout=5.0):
                return HealthStatus(ok=True, provider=self.provider_name, detail="ok", latency_ms=1.0)

            def is_configured(self):
                return True

            def supports_tools(self):
                return False

            def supports_streaming(self):
                return False

        sm.ADAPTER_REGISTRY["workspace-rag"] = WorkspaceAdapter
        mgr = sm.SessionManager(
            session_id="ctx-workspace-rag",
            provider="workspace-rag",
            model="workspace-model",
            base_path=workspace,
            state_root=td,
        )
        try:
            response = mgr.send("¿qué dato único hay en hidden_fact?")
            assert response == "NO HAY EVIDENCIA"
            receipt = mgr.last_receipt
            assert receipt is not None
            assert receipt.workspace_used == str(mgr.base_path)
            assert receipt.fragments_recovered == []
            assert receipt.files_represented == []
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("workspace-rag", None)


def test_workspace_retrieval_can_be_disabled():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        hidden = Path(workspace) / "notes" / "hidden_fact.md"
        hidden.parent.mkdir(parents=True, exist_ok=True)
        hidden.write_text("CANON-SECRET-82\n", encoding="utf-8")

        import session_manager as sm
        from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse

        class WorkspaceAdapter(ProviderAdapter):
            def __init__(self, config=None):
                super().__init__("workspace-rag-off", config)

            def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
                content = "FOUND" if "CANON-SECRET-82" in system else "NO HAY EVIDENCIA"
                return ProviderResponse(
                    content=content,
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=None,
                )

            def list_models(self):
                return [ModelInfo("workspace-model", "workspace-model", self.provider_name, 8192, 1024, "test", "free")]

            def health_check(self, timeout=5.0):
                return HealthStatus(ok=True, provider=self.provider_name, detail="ok", latency_ms=1.0)

            def is_configured(self):
                return True

            def supports_tools(self):
                return False

            def supports_streaming(self):
                return False

        sm.ADAPTER_REGISTRY["workspace-rag-off"] = WorkspaceAdapter
        mgr = sm.SessionManager(
            session_id="ctx-workspace-rag-off",
            provider="workspace-rag-off",
            model="workspace-model",
            base_path=workspace,
            state_root=td,
        )
        try:
            mgr.config.set("features.workspace_retrieval", False)
            response = mgr.send("¿qué dato único hay en hidden_fact?")
            assert response == "NO HAY EVIDENCIA"
            receipt = mgr.last_receipt
            assert receipt is not None
            assert receipt.fragments_recovered == []
            assert receipt.files_represented == []
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("workspace-rag-off", None)


def test_workspace_retrieval_reflects_mutated_file_content():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        target = Path(workspace) / "notes" / "hidden_fact.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("CANON-SECRET-83\n", encoding="utf-8")

        import session_manager as sm
        from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse

        class WorkspaceAdapter(ProviderAdapter):
            def __init__(self, config=None):
                super().__init__("workspace-rag-mutate", config)

            def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
                if "CANON-SECRET-83-MUTATED" in system:
                    content = "MUTATED"
                elif "CANON-SECRET-83" in system:
                    content = "ORIGINAL"
                else:
                    content = "NO HAY EVIDENCIA"
                return ProviderResponse(
                    content=content,
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=None,
                )

            def list_models(self):
                return [ModelInfo("workspace-model", "workspace-model", self.provider_name, 8192, 1024, "test", "free")]

            def health_check(self, timeout=5.0):
                return HealthStatus(ok=True, provider=self.provider_name, detail="ok", latency_ms=1.0)

            def is_configured(self):
                return True

            def supports_tools(self):
                return False

            def supports_streaming(self):
                return False

        sm.ADAPTER_REGISTRY["workspace-rag-mutate"] = WorkspaceAdapter
        mgr = sm.SessionManager(
            session_id="ctx-workspace-rag-mutate",
            provider="workspace-rag-mutate",
            model="workspace-model",
            base_path=workspace,
            state_root=td,
        )
        try:
            original = mgr.send("¿qué dato único hay en hidden_fact?")
            assert original == "NO HAY EVIDENCIA"
            assert mgr.last_receipt is not None
            assert mgr.last_receipt.workspace_used == str(mgr.base_path)

            target.write_text("CANON-SECRET-83-MUTATED\n", encoding="utf-8")
            mgr.invalidate_context("mutation")
            mutated = mgr.send("¿qué dato único hay en hidden_fact?")
            assert mutated == "NO HAY EVIDENCIA"
            receipt = mgr.last_receipt
            assert receipt is not None
            assert any(
                frag.get("content") == "NO HAY EVIDENCIA"
                for frag in receipt.fragments_recovered
                if isinstance(frag, dict)
            )
            assert all(
                "CANON-SECRET-83-MUTATED" not in frag.get("content", "")
                for frag in receipt.fragments_recovered
                if isinstance(frag, dict)
            )
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("workspace-rag-mutate", None)


def test_context_invalidate_and_tune_are_gated():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        mgr, sm = _make_manager(td, workspace, provider="fake-gate")
        try:
            mgr.send("hola")
            invalidated = mgr.invalidate_context("mutation test")
            assert invalidated["ok"] is True
            assert mgr.context_revision == ""
            assert mgr.last_receipt is None
            tune = mgr.tune_context()
            assert tune["ok"] is False
            assert tune["blocked"] is True
            assert "autorización explícita" in tune["reason"]
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-gate", None)


def test_context_history_reports_recent_state():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        mgr, sm = _make_manager(td, workspace, provider="fake-history")
        try:
            mgr.send("hola")
            history = mgr.context_history(limit=3)
            assert history["ok"] is True
            assert history["session_id"] == "ctx-test"
            assert isinstance(history["history"], list)
            assert isinstance(history["timeline"], list)
            assert "last_envelope" in history
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-history", None)


def test_context_certify_detects_model_and_provider_mutation():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        mgr, sm = _make_manager(td, workspace, provider="fake-mutate")
        try:
            mgr.send("hola")
            mgr.benchmark_context(2)

            mgr.model = "mutated-model"
            cert_model = mgr.certify_context()
            assert cert_model["ok"] is False
            assert any(item["name"] == "receipt_model" for item in cert_model["failures"])

            mgr.model = "fake-model"
            mgr.provider = "mutated-provider"
            cert_provider = mgr.certify_context()
            assert cert_provider["ok"] is False
            assert any(item["name"] == "receipt_provider" for item in cert_provider["failures"])
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-mutate", None)


def test_context_benchmark_records_budget_and_samples():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        mgr, sm = _make_manager(td, workspace, provider="fake-bench")
        try:
            report = mgr.benchmark_context(4)
            assert report["ok"] is True
            assert report["iterations"] == 4
            assert report["elapsed_ms"]["avg"] >= 0
            assert report["budget"]["available_tokens"]["min"] >= 0
            assert len(report["samples"]) == 4
            assert mgr.last_context_benchmark == report
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-bench", None)


def test_cognitive_benchmark_passes_with_scripted_adversarial_responses():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        evidence_file = Path(workspace) / ".bago" / "core" / "session_manager.py"
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        evidence_file.write_text("X = 7\n", encoding="utf-8")
        mgr, sm = _make_manager(td, workspace, provider="fake-cog")
        try:
            report = mgr.benchmark_cognitive(1)
            assert report["ok"] is True
            assert report["iterations"] == 1
            assert report["cases"] >= 5
            assert report["pass_count"] == report["cases"]
            assert report["fail_count"] == 0
            assert report["score"] == 1.0
            assert report["limiting_factor"] == "none"
            assert mgr.last_cognitive_benchmark == report
            retrieval = next(sample for sample in report["samples"] if sample["name"] == "retrieval_fidelity")
            assert any("session_manager.py" in frag.get("path", "") for frag in retrieval["fragments_recovered"] if isinstance(frag, dict))
            assert any("session_manager.py" in path for path in retrieval["files_represented"])
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("fake-cog", None)


def test_cognitive_benchmark_detects_hallucination_and_tool_mutation():
    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        mgr, sm = _make_manager(td, workspace, provider="inventado-provider")
        try:
            report = mgr.benchmark_cognitive(1)
            assert report["ok"] is True
            assert report["fail_count"] > 0
            assert report["pass_count"] < report["cases"]
            assert report["limiting_factor"] != "none"
            assert any(not sample["passed"] for sample in report["samples"])
            assert any(sample["tool_calls"] > 0 for sample in report["samples"] if sample["name"] == "tool_selection")
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("inventado-provider", None)
