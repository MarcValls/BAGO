from __future__ import annotations

import ast
import hashlib
import json
import tempfile
from pathlib import Path

import bago_spbe
import session_manager
from bago_spbe import (
    BindingDecision,
    BoundedCycleContract,
    BoundResource,
    CapabilityCandidate,
    CapabilityRef,
    DependencyCycle,
    DependencyEdge,
    ProposalReady,
    Requirement,
    ResolutionMode,
    ResolutionPolicy,
    ResourceBindingAttempt,
    SemanticBasisRef,
    SemanticCompilationKind,
    SemanticConflict,
    SemanticEntity,
    SemanticProceduralBehaviorEngine,
    SemanticTask,
    SemanticTerminalOutcome,
    Terminal,
    UncertaintyAssessment,
    UncertaintyDisposition,
    UncertaintyState,
)
from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage
from reflexive_interpreter import analyze_question
from session_turn_mixin import SessionTurnMixin
from spbe_runtime import (
    BagoSPBEAdapter,
    SPBE_CONTRACT_SHA256,
    SPBE_SOURCE_PACK_SHA256,
)
from tool_registry import ToolRegistry


EXPECTED_CONTRACT_SHA = "2e342c242c8f77600cfe3dd6a7b1a1818fb35cbf64105aa32b5a578709fe703a"
EXPECTED_PACK_SHA = "f553175deb048855b34342ca1f5d9f114f88d79f30a00a4648b89c5cb7b49340"


def _cref(name: str) -> CapabilityRef:
    return CapabilityRef(name, "1", "test", f"fp-{name}")


def test_spbe_runtime_reuses_behavior_pack_core_and_contract_identity():
    import spbe_runtime

    runtime_engine = spbe_runtime.SemanticProceduralBehaviorEngine
    pack_engine = bago_spbe.SemanticProceduralBehaviorEngine
    assert runtime_engine.__module__ == "bago_spbe.engine"
    assert pack_engine.__module__ == "bago_spbe.engine"
    assert Path(inspect.getfile(runtime_engine)).resolve() == Path(inspect.getfile(pack_engine)).resolve()
    assert SPBE_CONTRACT_SHA256 == EXPECTED_CONTRACT_SHA
    assert SPBE_SOURCE_PACK_SHA256 == EXPECTED_PACK_SHA

    required = (
        SemanticEntity,
        ResourceBindingAttempt,
        BoundResource,
        UncertaintyAssessment,
        UncertaintyDisposition,
        SemanticConflict,
        DependencyEdge,
        DependencyCycle,
        BoundedCycleContract,
        ResolutionPolicy,
    )
    assert all(item is not None for item in required)

    provenance_path = Path(bago_spbe.__file__).with_name("PACK_PROVENANCE.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["source_pack_sha256"] == EXPECTED_PACK_SHA
    assert provenance["frozen_contract_sha256"] == EXPECTED_CONTRACT_SHA

    for module_name, expected_sha256 in provenance["source_module_sha256"].items():
        module_path = Path(bago_spbe.__file__).with_name(module_name)
        assert hashlib.sha256(module_path.read_bytes()).hexdigest() == expected_sha256


def test_full_engine_enforces_binding_uncertainty_cycles_and_resolution_policy():
    engine = SemanticProceduralBehaviorEngine()

    root = bago_spbe.IntentRoot.create("intent-bind", "usa el archivo")
    entity = SemanticEntity("E1", "file", ("config",), True)
    attempt = ResourceBindingAttempt("B1", "E1", BindingDecision.AMBIGUOUS, ("a", "b"))
    terminal = engine.compile(
        SemanticTask(
            task_id="task-bind",
            intent_root=root,
            objective="usar archivo",
            requirements=(),
            candidates=(),
            completion_conditions=("done",),
            entities=(entity,),
            binding_attempts=(attempt,),
        )
    )
    assert isinstance(terminal, Terminal)
    assert terminal.terminal_result.outcome is SemanticTerminalOutcome.INSUFFICIENT_INFORMATION

    uncertainty = UncertaintyAssessment(
        "U1",
        "E1",
        UncertaintyState.BLOCKING,
        UncertaintyDisposition.BLOCK_SEMANTIC_COMPILATION,
    )
    terminal = engine.compile(
        SemanticTask(
            task_id="task-uncertainty",
            intent_root=root,
            objective="usar archivo",
            requirements=(),
            candidates=(),
            completion_conditions=("done",),
            uncertainties=(uncertainty,),
        )
    )
    assert isinstance(terminal, Terminal)

    cycle_terminal = engine.compile(
        SemanticTask(
            task_id="task-cycle",
            intent_root=root,
            objective="resolver",
            requirements=(),
            candidates=(),
            completion_conditions=("done",),
            dependency_edges=(DependencyEdge("A", "B"), DependencyEdge("B", "A")),
        )
    )
    assert isinstance(cycle_terminal, Terminal)
    assert cycle_terminal.terminal_result.outcome is SemanticTerminalOutcome.SEMANTICALLY_UNSATISFIABLE

    req = Requirement("REQ-1", "provides", {"capability": "needed"})
    reuse_ref = _cref("reuse")
    new_ref = _cref("new")
    reuse = CapabilityCandidate(
        reuse_ref,
        ResolutionMode.REUSE,
        frozenset({"needed"}),
        semantic_loss=10,
        proposed_steps=(
            bago_spbe.ProceduralStepCandidate(
                "reuse-step",
                "TEST",
                reuse_ref,
                semantic_basis=(SemanticBasisRef("REQUIREMENT_REF", "REQ-1", "SATISFIES"),),
            ),
        ),
    )
    new = CapabilityCandidate(
        new_ref,
        ResolutionMode.NEW,
        frozenset({"needed"}),
        semantic_loss=0,
        proposed_steps=(
            bago_spbe.ProceduralStepCandidate(
                "new-step",
                "TEST",
                new_ref,
                semantic_basis=(SemanticBasisRef("REQUIREMENT_REF", "REQ-1", "SATISFIES"),),
            ),
        ),
    )
    proposal = engine.compile(
        SemanticTask(
            task_id="task-resolution",
            intent_root=root,
            objective="resolver",
            requirements=(req,),
            candidates=(reuse, new),
            completion_conditions=("done",),
            semantic_artifact_ids=frozenset({"REQ-1"}),
        )
    )
    assert isinstance(proposal, ProposalReady)
    assert proposal.proposal.capability_refs == (new_ref,)
    assert proposal.proposal.resolution_decision.override_of_default_preference is True


def test_spbe_adapter_reuses_bago_readonly_tool_registry_bundle():
    registry = ToolRegistry()
    analysis = analyze_question(
        "Analiza este proyecto y dime qué piezas intervienen",
        {"domain": "bago-session", "conversation_history": ["user: proyecto BAGO"]},
    ).to_dict()

    adapter = BagoSPBEAdapter(registry)
    decision = adapter.compile_turn(
        user_message="Analiza este proyecto y dime qué piezas intervienen",
        reflexive_analysis=analysis,
        intent="work",
        tool_requested=True,
    )

    assert isinstance(decision.result, ProposalReady)
    assert decision.result.kind is SemanticCompilationKind.PROPOSAL_READY
    assert decision.allowed_tool_names
    assert all(registry.model_effect_id(name) == "filesystem.read" for name in decision.allowed_tool_names)
    envelope = decision.proposed_pec_envelope
    assert envelope is not None
    assert envelope["dispatch_state"] == "NOT_DISPATCHED_PEC_RUNTIME_NOT_BOUND"
    assert envelope["intent_root_ref"] == analysis["question_id"]
    assert envelope["kind"] == "SPBEtoPECEnvelope"


def test_spbe_ambiguous_terminal_blocks_tools_and_pec_handoff():
    registry = ToolRegistry()
    analysis = {
        "question_id": "Q-AMBIGUOUS",
        "intent": "implementar",
        "confidence": 0.20,
        "metrics": {"ambiguity": 0.75},
        "formalization": {"objective": "implementar"},
    }

    adapter = BagoSPBEAdapter(registry)
    decision = adapter.compile_turn(
        user_message="Haz eso",
        reflexive_analysis=analysis,
        intent="execute",
        tool_requested=True,
        workspace_transport_requested=True,
    )

    assert isinstance(decision.result, Terminal)
    assert decision.result.kind is SemanticCompilationKind.TERMINAL
    assert decision.result.terminal_result.outcome is SemanticTerminalOutcome.AMBIGUOUS_INTENT
    assert decision.allow_model_tools is False
    assert decision.allowed_tool_names == ()
    assert decision.proposed_pec_envelope is None

    try:
        adapter.engine.to_pec_envelope(decision.result)
    except ValueError as exc:
        assert "MUST NOT enter normal PEC handoff" in str(exc)
    else:
        raise AssertionError("Terminal SPBE result reached PEC handoff")


class _TerminalCodexCLIAdapter(ProviderAdapter):
    chat_calls = 0

    def __init__(self, config=None):
        super().__init__("codex", config)

    def _use_cli(self):
        return True

    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        type(self).chat_calls += 1
        raise AssertionError("workspace-capable Codex CLI must not be dispatched for SPBE Terminal")

    def chat_stream(self, messages, model, *, system="", temperature=0.7, max_tokens=None, tools=None):
        type(self).chat_calls += 1
        raise AssertionError("workspace-capable Codex CLI stream must not be dispatched for SPBE Terminal")
        yield ""

    def list_models(self):
        return [ModelInfo("codex-test", "codex-test", self.provider_name, 4096, 1024, "test", "free")]

    def health_check(self, timeout=5.0):
        return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

    def is_configured(self):
        return True

    def supports_tools(self):
        return False

    def supports_streaming(self):
        return False


def _ambiguous_analysis(_text: str):
    return {
        "question_id": "Q-CLI-TERMINAL",
        "literal_reading": _text,
        "intent": "analizar",
        "operational_intent": "work",
        "formalization": {"objective": "analizar"},
        "restrictions": [],
        "unknowns": [],
        "confidence": 0.20,
        "metrics": {"ambiguity": 0.75},
    }


def test_codex_cli_router_is_never_dispatched_before_spbe(tmp_path):
    previous = session_manager.ADAPTER_REGISTRY.get("codex")
    session_manager.ADAPTER_REGISTRY["codex"] = _TerminalCodexCLIAdapter
    _TerminalCodexCLIAdapter.chat_calls = 0
    with tempfile.TemporaryDirectory() as state_dir:
        mgr = session_manager.SessionManager(
            session_id="spbe-cli-router-test",
            provider="codex",
            model="codex-test",
            base_path=str(tmp_path),
            state_root=state_dir,
        )
        try:
            route = mgr.route_user_message("Revisa el proyecto completo")
            assert route["reason"] == "workspace_cli_router_disabled"
            assert route["source"] == "policy"
            assert _TerminalCodexCLIAdapter.chat_calls == 0
        finally:
            mgr.close()
            if previous is None:
                session_manager.ADAPTER_REGISTRY.pop("codex", None)
            else:
                session_manager.ADAPTER_REGISTRY["codex"] = previous


def test_send_internal_blocks_workspace_cli_before_provider_dispatch(tmp_path):
    previous = session_manager.ADAPTER_REGISTRY.get("codex")
    session_manager.ADAPTER_REGISTRY["codex"] = _TerminalCodexCLIAdapter
    _TerminalCodexCLIAdapter.chat_calls = 0
    with tempfile.TemporaryDirectory() as state_dir:
        mgr = session_manager.SessionManager(
            session_id="spbe-cli-internal-test",
            provider="codex",
            model="codex-test",
            base_path=str(tmp_path),
            state_root=state_dir,
        )
        try:
            try:
                mgr.send_internal("devuelve un JSON")
            except RuntimeError as exc:
                assert "workspace-capable CLI providers" in str(exc)
            else:
                raise AssertionError("send_internal dispatched a workspace-capable CLI provider")
            assert _TerminalCodexCLIAdapter.chat_calls == 0
        finally:
            mgr.close()
            if previous is None:
                session_manager.ADAPTER_REGISTRY.pop("codex", None)
            else:
                session_manager.ADAPTER_REGISTRY["codex"] = previous


def test_codex_cli_terminal_short_circuits_before_provider_dispatch(tmp_path):
    previous = session_manager.ADAPTER_REGISTRY.get("codex")
    session_manager.ADAPTER_REGISTRY["codex"] = _TerminalCodexCLIAdapter
    _TerminalCodexCLIAdapter.chat_calls = 0
    with tempfile.TemporaryDirectory() as state_dir:
        mgr = session_manager.SessionManager(
            session_id="spbe-cli-terminal-test",
            provider="codex",
            model="codex-test",
            base_path=str(tmp_path),
            state_root=state_dir,
        )
        try:
            mgr.analyze_reflexive_turn = _ambiguous_analysis
            response = mgr.send(
                "Revisa ese proyecto antes de continuar",
                route_info={"kind": "chat", "command": "", "args": []},
            )
            assert "aclarar" in response.lower()
            assert mgr.last_response_state == "needs_confirmation"
            assert _TerminalCodexCLIAdapter.chat_calls == 0
        finally:
            mgr.close()
            if previous is None:
                session_manager.ADAPTER_REGISTRY.pop("codex", None)
            else:
                session_manager.ADAPTER_REGISTRY["codex"] = previous


def test_orchestration_terminal_short_circuits_all_provider_dispatch(tmp_path):
    previous = session_manager.ADAPTER_REGISTRY.get("codex")
    session_manager.ADAPTER_REGISTRY["codex"] = _TerminalCodexCLIAdapter
    _TerminalCodexCLIAdapter.chat_calls = 0
    with tempfile.TemporaryDirectory() as state_dir:
        mgr = session_manager.SessionManager(
            session_id="spbe-orchestrate-terminal-test",
            provider="codex",
            model="codex-test",
            base_path=str(tmp_path),
            state_root=state_dir,
        )
        try:
            mgr.analyze_reflexive_turn = _ambiguous_analysis
            result = mgr.orchestrate("Revisa ese proyecto", providers=["codex"])
            assert result["codex"]["spbe_terminal"] is True
            assert _TerminalCodexCLIAdapter.chat_calls == 0
        finally:
            mgr.close()
            if previous is None:
                session_manager.ADAPTER_REGISTRY.pop("codex", None)
            else:
                session_manager.ADAPTER_REGISTRY["codex"] = previous


def test_compact_cli_prompt_preserves_spbe_decision_and_terminal_precedes_chat():
    source = Path(__import__("session_turn_mixin").__file__).read_text(encoding="utf-8")
    compact = source[source.index("compact_blocks = ["):source.index("tools = None", source.index("compact_blocks = ["))]
    assert "spbe_decision.prompt_block()" in compact

    send_source = source[source.index("    def send("):source.index("    def orchestrate(")]
    terminal_gate = send_source.index("if spbe_decision.is_terminal:")
    provider_dispatch = send_source.index("resp = adapter.chat(")
    assert terminal_gate < provider_dispatch


def test_behavior_pack_core_and_runtime_adapter_contain_no_material_effect_sinks():
    import spbe_runtime

    package_root = Path(bago_spbe.__file__).parent
    paths = list(package_root.glob("*.py")) + [Path(spbe_runtime.__file__)]
    banned_imports = {"subprocess", "socket", "shutil"}
    banned_sinks = (
        "ExecutionGateway(",
        "AuthorizationBoundary(",
        "subprocess.",
        "os.system(",
        "Path.write_text(",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned_imports), path.name
        for sink in banned_sinks:
            assert sink not in source, (path.name, sink)


def test_canonical_ci_clean_install_failure_is_fail_closed():
    workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "canonical-ci.yml").read_text(encoding="utf-8")
    command = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_clean_install.ps1"
    index = workflow.index(command)
    following = workflow[index:index + 240]
    assert 'if ($LASTEXITCODE -ne 0) { throw "Clean-install gate failed." }' in following
