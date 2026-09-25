"""Tests for bago_core.agent_kit catalog/registry."""

from __future__ import annotations

from pathlib import Path

import json

import pytest

from bago_core.agent_kit.catalog import DEFAULT_CATALOG_PATH, default_catalog_path, list_agents, load_agent
from bago_core.agent_kit.errors import AgentNotFound, CatalogNotFound
from bago_core.agent_kit.models import AgentDefinition
from bago_core.agent_kit.registry import AgentRegistry
from bago_core.agent_kit.runner import AgentRunner, run_agent


CATALOG = DEFAULT_CATALOG_PATH


class TestCatalog:
    def test_default_catalog_exists(self):
        assert CATALOG.exists(), f"catalog missing: {CATALOG}"

    def test_list_agents_discovers_catalog_without_fixed_agent_allowlist(self):
        agents = list_agents(CATALOG)
        assert agents
        assert [agent.id for agent in agents] == sorted({agent.id for agent in agents})
        assert all(agent.source_path and agent.source_path.is_relative_to(CATALOG.resolve()) for agent in agents)

    def test_catalog_default_can_be_configured_without_user_profile_binding(self, monkeypatch, tmp_path):
        from bago_core.agent_kit import catalog
        configured = tmp_path / "external-agents"
        monkeypatch.setenv("BAGO_AGENT_CATALOG", str(configured))
        assert catalog.default_catalog_path() == configured

    def test_catalog_default_uses_profile_relative_lab_path(self, monkeypatch):
        from bago_core.agent_kit import catalog
        monkeypatch.delenv("BAGO_AGENT_CATALOG", raising=False)
        assert catalog.default_catalog_path() == Path.home() / "BAGO_AGENTIC_DATA_LAB" / "agents"

    def test_agent_json_definitions_are_discovered_and_normalized(self, tmp_path):
        definition = {
            "agent": "temporary_guardian",
            "mission": "Inspect state isolation.",
            "reads": ["tests/"],
            "writes": ["reports/"],
            "gate": "report unexpected state changes",
        }
        path = tmp_path / "temporary_guardian.agent.json"
        path.write_text(json.dumps(definition), encoding="utf-8")
        agent = load_agent(tmp_path, "temporary_guardian")
        assert agent.id == "temporary_guardian"
        assert agent.description == definition["mission"]
        assert agent.sandbox_mode == "workspace-write"
        assert "report unexpected state changes" in agent.prompt_template
        assert [item.id for item in list_agents(tmp_path)] == ["temporary_guardian"]

    def test_agent_definition_has_required_fields(self):
        agent = load_agent(CATALOG, "bago_assistant")
        assert agent.id == "bago_assistant"
        assert agent.name
        assert agent.description
        assert agent.source_path
        assert agent.source_path.exists()

    def test_architecture_auditor_is_read_only(self):
        agent = load_agent(CATALOG, "bago_architecture_auditor")
        assert agent.is_read_only
        assert agent.category == "audit"

    def test_backend_auditor_has_model(self):
        agent = load_agent(CATALOG, "bago_backend_auditor")
        assert agent.model
        assert agent.sandbox_mode == "read-only"
        assert agent.category == "audit"

    def test_toml_agent_includes_its_declared_instructions(self):
        agent = load_agent(CATALOG, "bago_backend_auditor")
        assert agent.prompt_template
        assert "Traza endpoints" in agent.prompt_template

    def test_frontend_auditor_description_is_string(self):
        agent = load_agent(CATALOG, "bago_frontend_auditor")
        assert isinstance(agent.description, str)
        assert len(agent.description) > 0

    def test_final_verifier_is_read_only_with_model(self):
        agent = load_agent(CATALOG, "bago_final_verifier")
        assert agent.is_read_only
        assert agent.model
        assert agent.category == "verify"

    def test_load_unknown_agent_raises(self):
        with pytest.raises(AgentNotFound):
            load_agent(CATALOG, "nonexistent_agent_xyz")

    def test_list_agents_against_bad_path_raises(self):
        with pytest.raises(CatalogNotFound):
            list_agents(Path("/nonexistent/catalog/path"))


class TestRegistry:
    def test_registry_all_returns_sorted_agents(self):
        reg = AgentRegistry(CATALOG)
        agents = reg.all()
        assert agents
        assert [a.id for a in agents] == sorted(a.id for a in agents)

    def test_registry_get_existing(self):
        reg = AgentRegistry(CATALOG)
        agent = reg.get("bago_assistant")
        assert isinstance(agent, AgentDefinition)

    def test_registry_get_unknown_raises(self):
        reg = AgentRegistry(CATALOG)
        with pytest.raises(AgentNotFound):
            reg.get("not_an_agent")

    def test_registry_categories(self):
        reg = AgentRegistry(CATALOG)
        categories = reg.categories()
        assert "audit" in categories


class TestRunner:
    def test_runner_describe_mode(self):
        result = run_agent("bago_assistant", mode="describe")
        assert result.success
        assert result.agent_id == "bago_assistant"
        assert "bago_assistant" in result.output

    def test_runner_run_mode_without_llm_echoes_prompt(self):
        result = run_agent("bago_architecture_auditor", task="audit backend", mode="run")
        assert result.success
        assert "bago_architecture_auditor" in result.output
        assert "Task: audit backend" in result.output

    def test_assistant_definition_does_not_trigger_hidden_orchestration(self):
        result = run_agent("bago_assistant", task="audit backend", mode="run")
        assert result.success
        assert "Task: audit backend" in result.output
        assert "BAGO Assistant Result" not in result.output


class TestLLMAdapter:
    def test_default_base_url_for_ollama(self):
        from bago_core.agent_kit.llm_adapter import _default_base_url
        assert _default_base_url("ollama") == "http://localhost:11434"
        assert _default_base_url("ollama-local") == "http://localhost:11434"

    def test_default_base_url_for_openai(self):
        from bago_core.agent_kit.llm_adapter import _default_base_url
        assert _default_base_url("openai") == "https://api.openai.com/v1"

    def test_provider_protocol(self):
        from bago_core.agent_kit.llm_adapter import _provider_protocol
        assert _provider_protocol("ollama") == "ollama"
        assert _provider_protocol("anthropic") == "anthropic"
        assert _provider_protocol("openai") == "openai-compatible"
        assert _provider_protocol("copilot") == "openai-compatible"

    def test_resolve_api_key_from_env(self, monkeypatch):
        from bago_core.agent_kit.llm_adapter import _resolve_api_key
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert _resolve_api_key("openai") == "sk-test"

    def test_call_llm_requires_provider_and_model(self):
        from bago_core.agent_kit.llm_adapter import LLMAdapterError, call_llm
        with pytest.raises(LLMAdapterError, match="provider is required"):
            call_llm("", "gpt-4", messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(LLMAdapterError, match="model is required"):
            call_llm("openai", "", messages=[{"role": "user", "content": "hi"}])

    def test_http_post_uses_the_shared_gateway_transport(self, monkeypatch):
        from bago_core.agent_kit import llm_adapter

        captured = {}

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"choices":[]}'

        def fake_gateway_urlopen(request, *, timeout, network_class):
            captured.update({
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "body": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
                "network_class": network_class,
            })
            return _Response()

        monkeypatch.setattr(llm_adapter, "gateway_urlopen", fake_gateway_urlopen)

        result = llm_adapter._http_post(
            "https://provider.example/v1/chat",
            {"Authorization": "Bearer test"},
            {"model": "fixture", "messages": []},
            timeout=12.0,
        )

        assert result == {"choices": []}
        assert captured["method"] == "POST"
        assert captured["body"] == {"model": "fixture", "messages": []}
        assert captured["timeout"] == 12.0
        assert captured["network_class"] == "provider_transport"

    def test_call_agent_prompt_dry_run_returns_prompt(self):
        from bago_core.agent_kit.llm_adapter import call_agent_prompt
        from bago_core.agent_kit.models import AgentDefinition, AgentRequest

        agent = AgentDefinition(
            id="test_agent",
            name="Test Agent",
            description="A test agent.",
            category="test",
            prompt_template="Be helpful.",
        )
        request = AgentRequest(agent_id="test_agent", task="say hello")
        result = call_agent_prompt(agent, request, dry_run=True)
        assert result["dry_run"] is True
        assert "You are Test Agent" in result["output"]
        assert "Task: say hello" in result["output"]
        assert result["llm_response"] is None

    def test_runner_dry_run_by_default(self):
        result = run_agent("bago_assistant", task="hi", mode="chat")
        assert result.success
        assert "[DRY RUN]" in result.output

    def test_runner_no_dry_run_without_provider_fails(self):
        result = run_agent("bago_assistant", task="hi", mode="chat", dry_run=False)
        assert not result.success
        assert "provider is required" in result.error

    def test_runner_rejects_unknown_agent(self):
        result = run_agent("nonexistent_xyz", task="hi", mode="describe")
        assert not result.success
        assert "nonexistent_xyz" in result.error



class TestOrchestratorJSONPlan:
    def test_parse_agent_plan_extracts_json_from_markdown(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        raw = "```json\n{\n  \"reasoning\": \"backend task\",\n  \"audit\": [\"bago_assistant\", \"bago_backend_auditor\"],\n  \"execute\": [],\n  \"verify\": \"bago_final_verifier\"\n}\n```"
        fallback = {"audit": ["bago_assistant"], "execute": [], "verify": "bago_final_verifier"}
        known = {"bago_assistant", "bago_backend_auditor", "bago_final_verifier"}
        plan = orch._parse_agent_plan(raw, fallback, known)
        assert plan["reasoning"] == "backend task"
        assert plan["audit"] == ["bago_backend_auditor"]
        assert plan["verify"] == "bago_final_verifier"

    def test_parse_agent_plan_filters_unknown_ids(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        raw = '{"reasoning": "x", "audit": ["bago_backend_auditor", "unknown_agent"], "execute": [], "verify": "bago_final_verifier"}'
        fallback = {"audit": ["bago_backend_auditor"], "execute": [], "verify": "bago_final_verifier"}
        known = {"bago_backend_auditor", "bago_final_verifier"}
        plan = orch._parse_agent_plan(raw, fallback, known)
        assert "unknown_agent" not in plan["audit"]
        assert plan["audit"] == ["bago_backend_auditor"]

    def test_parse_agent_plan_falls_back_on_invalid_json(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        fallback = {"reasoning": "fallback", "audit": ["bago_assistant"], "execute": [], "verify": "bago_final_verifier"}
        known = {"bago_assistant", "bago_final_verifier"}
        plan = orch._parse_agent_plan("not json", fallback, known)
        assert plan["audit"] == fallback["audit"]
        assert plan["reasoning"] == "fallback"

    def test_select_agents_by_task_backend(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        plan = orch._select_agents_by_task("audit backend routes")
        assert "bago_backend_auditor" in plan["audit"]
        assert "bago_frontend_auditor" not in plan["audit"]

    def test_select_agents_by_task_frontend(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        plan = orch._select_agents_by_task("review react components")
        assert "bago_frontend_auditor" in plan["audit"]

    def test_dry_run_returns_structured_plan(self):
        from bago_core.agent_kit.orchestrator import orchestrate_task
        result = orchestrate_task("audit backend")
        assert result.success
        assert result.plan["reasoning"]
        assert "bago_backend_auditor" in result.plan["audit"]



class TestOrchestratorValidationAndPersistence:
    def test_manual_schema_validation_works_without_jsonschema(self, monkeypatch):
        from bago_core.agent_kit import orchestrator
        orch = orchestrator.AgentOrchestrator()
        monkeypatch.setattr(orchestrator, "validate", None)
        fallback = {"reasoning": "fallback", "audit": [], "execute": [], "verify": ""}
        raw = '{"reasoning": "", "audit": [7], "execute": [], "verify": "", "extra": true}'
        assert orch._parse_agent_plan(raw, fallback, set()) == fallback

    def test_parse_agent_plan_rejects_schema_violation(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        raw = '{"reasoning": "x", "audit": "not-a-list", "execute": [], "verify": "bago_final_verifier"}'
        fallback = {"reasoning": "fallback", "audit": ["bago_assistant"], "execute": [], "verify": "bago_final_verifier"}
        known = {"bago_assistant", "bago_final_verifier"}
        plan = orch._parse_agent_plan(raw, fallback, known)
        # audit is wrong type -> fallback
        assert plan["audit"] == fallback["audit"]
        assert plan["reasoning"] == "fallback"

    def test_parse_agent_plan_accepts_valid_schema(self):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        raw = '{"reasoning": "backend task", "audit": ["bago_backend_auditor"], "execute": [], "verify": "bago_final_verifier"}'
        fallback = {"reasoning": "fallback", "audit": ["x"], "execute": [], "verify": "x"}
        known = {"bago_backend_auditor", "bago_final_verifier"}
        plan = orch._parse_agent_plan(raw, fallback, known)
        assert plan["reasoning"] == "backend task"
        assert plan["audit"] == ["bago_backend_auditor"]
        assert plan["verify"] == "bago_final_verifier"

    def test_save_orchestrator_plan_appends_jsonl(self, tmp_path):
        from bago_core.agent_kit.orchestrator import save_orchestrator_plan
        state_root = tmp_path / "state"
        plan = {"reasoning": "test", "audit": ["bago_assistant"], "execute": [], "verify": "bago_final_verifier"}
        path = save_orchestrator_plan(
            plan,
            task="test task",
            context={"root": str(tmp_path)},
            provider="ollama",
            model="llama3.2:3b",
            dry_run=True,
            state_root=state_root,
        )
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["task"] == "test task"
        assert record["provider"] == "ollama"
        assert record["model"] == "llama3.2:3b"
        assert record["dry_run"] is True
        assert record["plan"] == plan
        assert "timestamp" in record

    def test_save_orchestrator_plan_uses_registered_state_writer(self, tmp_path, monkeypatch):
        from bago_core import atomic_json
        from bago_core.agent_kit.orchestrator import save_orchestrator_plan

        calls = []
        original = atomic_json.append_text_durable

        def capture(path, content):
            assert not path.parent.exists()
            calls.append((path, content))
            return original(path, content)

        monkeypatch.setattr(atomic_json, "append_text_durable", capture)
        state_root = tmp_path / "not-created-yet"
        path = save_orchestrator_plan(
            {"reasoning": "test", "audit": [], "execute": [], "verify": ""},
            state_root=state_root,
        )

        assert len(calls) == 1
        assert calls[0][0] == path
        assert state_root.exists()
        assert len(json.loads(calls[0][1])) > 0
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1

    def test_dry_run_persists_plan(self, tmp_path):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator, _plan_store_path
        state_root = tmp_path / "state"
        orch = AgentOrchestrator(state_root=state_root)
        result = orch.run("audit backend", dry_run=True)
        assert result.success
        store = _plan_store_path(state_root)
        assert store.exists()
        lines = store.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["dry_run"] is True
        assert record["plan"]["audit"] == result.plan["audit"]

    def test_explicit_plan_persists_dynamic_selection_without_assistant_dispatch(self, tmp_path):
        from bago_core.agent_kit.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(state_root=tmp_path / ".bago" / "state")
        result = orch.plan("audit backend routes", context={"root": str(tmp_path)}, dry_run=True)
        assert result.success
        assert "bago_assistant" not in result.plan["audit"]
        assert "bago_backend_auditor" in result.plan["audit"]
        payload = json.loads(result.output)
        assert payload["plan"] == result.plan
        saved = Path(payload["saved_to"])
        record = json.loads(saved.read_text(encoding="utf-8").splitlines()[-1])
        assert record["task"] == "audit backend routes"
        assert record["dry_run"] is True
