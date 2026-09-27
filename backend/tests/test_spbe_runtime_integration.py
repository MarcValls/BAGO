from __future__ import annotations

import ast
import inspect
from pathlib import Path

from reflexive_interpreter import analyze_question
from session_turn_mixin import SessionTurnMixin
from spbe_runtime import (
    BagoSPBEAdapter,
    ProposalReady,
    SemanticCompilationKind,
    SemanticProceduralBehaviorEngine,
    SemanticTerminalOutcome,
    Terminal,
)
from tool_registry import ToolRegistry


def test_spbe_adapter_reuses_bago_readonly_tool_registry_bundle():
    registry = ToolRegistry()
    analysis = analyze_question(
        "Analiza este proyecto y dime qué piezas intervienen",
        {"domain": "bago-session", "conversation_history": ["user: proyecto BAGO"]},
    ).to_dict()

    decision = BagoSPBEAdapter(registry).compile_turn(
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


def test_spbe_ambiguous_terminal_blocks_tools_and_pec_handoff():
    registry = ToolRegistry()
    analysis = {
        "question_id": "Q-AMBIGUOUS",
        "intent": "implementar",
        "confidence": 0.20,
        "metrics": {"ambiguity": 0.75},
        "formalization": {"objective": "implementar"},
    }

    decision = BagoSPBEAdapter(registry).compile_turn(
        user_message="Haz eso",
        reflexive_analysis=analysis,
        intent="execute",
        tool_requested=True,
    )

    assert isinstance(decision.result, Terminal)
    assert decision.result.kind is SemanticCompilationKind.TERMINAL
    assert decision.result.terminal_result.outcome is SemanticTerminalOutcome.AMBIGUOUS_INTENT
    assert decision.allow_model_tools is False
    assert decision.allowed_tool_names == ()
    assert decision.proposed_pec_envelope is None

    try:
        SemanticProceduralBehaviorEngine.to_pec_envelope(decision.result)
    except ValueError as exc:
        assert "MUST NOT enter normal PEC handoff" in str(exc)
    else:
        raise AssertionError("Terminal SPBE result reached PEC handoff")


def test_session_turn_mixin_owns_spbe_binding_and_fails_closed(monkeypatch):
    registry = ToolRegistry()
    mixin = SessionTurnMixin()
    mixin.tool_registry = registry
    analysis = analyze_question(
        "Revisa el proyecto",
        {"domain": "bago-session", "conversation_history": ["user: BAGO"]},
    ).to_dict()

    decision = mixin._compile_spbe_turn(
        "Revisa el proyecto",
        analysis,
        "work",
        tool_requested=True,
    )
    assert isinstance(decision.result, ProposalReady)
    assert decision.allowed_tool_names

    def boom(*args, **kwargs):
        raise RuntimeError("forced-spbe-failure")

    monkeypatch.setattr(BagoSPBEAdapter, "compile_turn", boom)
    failed = mixin._compile_spbe_turn(
        "Revisa el proyecto",
        analysis,
        "work",
        tool_requested=True,
    )
    assert isinstance(failed.result, Terminal)
    assert failed.allow_model_tools is False
    assert failed.result.terminal_result.outcome is SemanticTerminalOutcome.INSUFFICIENT_INFORMATION


def test_session_turn_source_gates_tools_and_records_spbe_receipt_metadata():
    source = inspect.getsource(SessionTurnMixin.send)
    assert "spbe_decision.allow_model_tools" in source
    assert "allowed_tool_names = set(spbe_decision.allowed_tool_names)" in source
    assert '"spbe_runtime": spbe_metadata' in source


def test_spbe_runtime_module_contains_no_material_effect_sinks():
    import spbe_runtime

    path = Path(spbe_runtime.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_imports = {"subprocess", "socket", "shutil", "pathlib"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & banned_imports)

    source = path.read_text(encoding="utf-8")
    for sink in ("ExecutionGateway(", "AuthorizationBoundary(", "subprocess.", "os.system(", "Path.write_text("):
        assert sink not in source
