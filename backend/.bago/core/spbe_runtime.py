#!/usr/bin/env python3
"""SPBE runtime adapter for BAGO session turns.

Runtime projection of SEMANTIC_PROCEDURAL_BEHAVIOR_ENGINE_CONTRACT v0.5-FIX5.
This module is semantic/procedural only: it does not issue permits, validate
runtime authorization, call ExecutionGateway, or materialize effects.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

SPBE_CONTRACT_VERSION = "v0.5-FIX5"
SPBE_CONTRACT_SHA256 = "2e342c242c8f77600cfe3dd6a7b1a1818fb35cbf64105aa32b5a578709fe703a"
SPBE_RUNTIME_SCHEMA = "bago.spbe.runtime.v1"


class Eligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNKNOWN = "UNKNOWN"


class ResolutionMode(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    NEW = "NEW"


class SemanticCompilationKind(str, Enum):
    PROPOSAL_READY = "PROPOSAL_READY"
    TERMINAL = "TERMINAL"


class SemanticTerminalOutcome(str, Enum):
    NO_ELIGIBLE_SOLUTION = "NO_ELIGIBLE_SOLUTION"
    AMBIGUOUS_INTENT = "AMBIGUOUS_INTENT"
    UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    SEMANTICALLY_UNSATISFIABLE = "SEMANTICALLY_UNSATISFIABLE"


@dataclass(frozen=True)
class IntentRoot:
    intent_id: str
    original_request: str
    original_request_fingerprint: str
    authority: str = "USER"

    @classmethod
    def create(cls, intent_id: str, original_request: str) -> "IntentRoot":
        return cls(
            intent_id=intent_id,
            original_request=original_request,
            original_request_fingerprint=hashlib.sha256(original_request.encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class SemanticBasisRef:
    basis_type: str
    source_id: str
    relation: str


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    capability: str
    hard: bool = True


@dataclass(frozen=True)
class CapabilityRef:
    capability_id: str
    capability_version: str
    provider_id: str
    contract_fingerprint: str

    @property
    def stable_key(self) -> str:
        return (
            f"{self.capability_id}@{self.capability_version}:"
            f"{self.provider_id}:{self.contract_fingerprint}"
        )


@dataclass(frozen=True)
class ProceduralStepCandidate:
    step_id: str
    operation_class: str
    semantic_basis: tuple[SemanticBasisRef, ...]
    authorization_requirement: str | None = None


@dataclass(frozen=True)
class CapabilityCandidate:
    ref: CapabilityRef
    mode: ResolutionMode
    provides: frozenset[str]
    proposed_steps: tuple[ProceduralStepCandidate, ...]
    tool_names: tuple[str, ...] = ()
    semantic_loss: int = 0
    adaptation_cost: int = 0
    procedural_complexity: int = 0
    evidence_burden: int = 0


@dataclass(frozen=True)
class EligibilityDecision:
    candidate_ref: CapabilityRef
    decision: Eligibility
    satisfied: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionDecision:
    policy_ref: str
    selected_capability_refs: tuple[CapabilityRef, ...]
    selected_mode: ResolutionMode
    explanation: str


@dataclass(frozen=True)
class ProceduralProposal:
    proposal_id: str
    intent_root_ref: str
    objective: str
    capability_refs: tuple[CapabilityRef, ...]
    candidate_steps: tuple[ProceduralStepCandidate, ...]
    completion_conditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    resolution_decision: ResolutionDecision


@dataclass(frozen=True)
class SemanticTerminalResult:
    terminal_result_id: str
    intent_root_ref: str
    outcome: SemanticTerminalOutcome
    evidence: tuple[str, ...] = ()
    unresolved_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProposalReady:
    kind: SemanticCompilationKind
    proposal: ProceduralProposal
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is not SemanticCompilationKind.PROPOSAL_READY:
            raise ValueError("ProposalReady.kind must be PROPOSAL_READY")


@dataclass(frozen=True)
class Terminal:
    kind: SemanticCompilationKind
    terminal_result: SemanticTerminalResult
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is not SemanticCompilationKind.TERMINAL:
            raise ValueError("Terminal.kind must be TERMINAL")


SemanticCompilationResult = ProposalReady | Terminal


@dataclass(frozen=True)
class SemanticTask:
    task_id: str
    intent_root: IntentRoot
    objective: str
    requirements: tuple[Requirement, ...]
    candidates: tuple[CapabilityCandidate, ...]
    completion_conditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...] = ()


class SemanticProceduralBehaviorEngine:
    """Deterministic semantic gate; never executes effects."""

    def compile(self, task: SemanticTask) -> SemanticCompilationResult:
        decisions = tuple(self._eligibility(candidate, task.requirements) for candidate in task.candidates)
        eligible = [
            candidate
            for candidate, decision in zip(task.candidates, decisions, strict=True)
            if decision.decision is Eligibility.ELIGIBLE
        ]
        if not eligible:
            unknown_or_failed = tuple(
                f"{decision.candidate_ref.stable_key}:{decision.decision.value}"
                for decision in decisions
            )
            return self._terminal(
                task,
                SemanticTerminalOutcome.NO_ELIGIBLE_SOLUTION,
                evidence=unknown_or_failed,
                unresolved=unknown_or_failed,
            )

        mode_rank = {ResolutionMode.REUSE: 0, ResolutionMode.EXTEND: 1, ResolutionMode.NEW: 2}
        selected = min(
            eligible,
            key=lambda candidate: (
                mode_rank[candidate.mode],
                candidate.semantic_loss,
                candidate.adaptation_cost,
                candidate.procedural_complexity,
                candidate.evidence_burden,
                candidate.ref.stable_key,
            ),
        )
        resolution = ResolutionDecision(
            policy_ref="bago.spbe.default-resolution@1",
            selected_capability_refs=(selected.ref,),
            selected_mode=selected.mode,
            explanation="selected by governed REUSE→EXTEND→NEW preference after hard eligibility",
        )
        proposal_id = "proposal-" + hashlib.sha256(
            (task.task_id + selected.ref.stable_key).encode("utf-8")
        ).hexdigest()[:16]
        proposal = ProceduralProposal(
            proposal_id=proposal_id,
            intent_root_ref=task.intent_root.intent_id,
            objective=task.objective,
            capability_refs=(selected.ref,),
            candidate_steps=selected.proposed_steps,
            completion_conditions=task.completion_conditions,
            evidence_requirements=task.evidence_requirements,
            resolution_decision=resolution,
        )
        return ProposalReady(
            kind=SemanticCompilationKind.PROPOSAL_READY,
            proposal=proposal,
            evidence=tuple(
                f"{decision.candidate_ref.stable_key}:{decision.decision.value}"
                for decision in decisions
            ),
        )

    @staticmethod
    def _eligibility(candidate: CapabilityCandidate, requirements: tuple[Requirement, ...]) -> EligibilityDecision:
        satisfied: list[str] = []
        failed: list[str] = []
        for requirement in requirements:
            if requirement.capability in candidate.provides:
                satisfied.append(requirement.requirement_id)
            elif requirement.hard:
                failed.append(requirement.requirement_id)
        return EligibilityDecision(
            candidate_ref=candidate.ref,
            decision=Eligibility.NOT_ELIGIBLE if failed else Eligibility.ELIGIBLE,
            satisfied=tuple(satisfied),
            failed=tuple(failed),
        )

    @staticmethod
    def _terminal(
        task: SemanticTask,
        outcome: SemanticTerminalOutcome,
        *,
        evidence: tuple[str, ...] = (),
        unresolved: tuple[str, ...] = (),
    ) -> Terminal:
        terminal_id = "terminal-" + hashlib.sha256(
            (task.task_id + outcome.value + "|".join(unresolved)).encode("utf-8")
        ).hexdigest()[:16]
        return Terminal(
            kind=SemanticCompilationKind.TERMINAL,
            terminal_result=SemanticTerminalResult(
                terminal_result_id=terminal_id,
                intent_root_ref=task.intent_root.intent_id,
                outcome=outcome,
                evidence=evidence,
                unresolved_conditions=unresolved,
            ),
            evidence=evidence,
        )

    @staticmethod
    def terminal(
        intent_root: IntentRoot,
        task_id: str,
        outcome: SemanticTerminalOutcome,
        *,
        evidence: tuple[str, ...] = (),
        unresolved: tuple[str, ...] = (),
    ) -> Terminal:
        return SemanticProceduralBehaviorEngine._terminal(
            SemanticTask(
                task_id=task_id,
                intent_root=intent_root,
                objective="",
                requirements=(),
                candidates=(),
                completion_conditions=(),
            ),
            outcome,
            evidence=evidence,
            unresolved=unresolved,
        )

    @staticmethod
    def to_pec_envelope(result: SemanticCompilationResult) -> dict[str, Any]:
        if not isinstance(result, ProposalReady):
            raise ValueError("Terminal semantic results MUST NOT enter normal PEC handoff")
        proposal = result.proposal
        return {
            "schema": "bago.spbe.to-pec.v1",
            "dispatch_state": "NOT_DISPATCHED_PEC_RUNTIME_NOT_BOUND",
            "proposal_ref": proposal.proposal_id,
            "intent_root_ref": proposal.intent_root_ref,
            "capability_refs": [ref.stable_key for ref in proposal.capability_refs],
            "candidate_steps": [step.step_id for step in proposal.candidate_steps],
            "completion_conditions": list(proposal.completion_conditions),
            "evidence_requirements": list(proposal.evidence_requirements),
        }


@dataclass(frozen=True)
class SPBERuntimeDecision:
    result: SemanticCompilationResult
    allowed_tool_names: tuple[str, ...]
    proposed_pec_envelope: Mapping[str, Any] | None
    runtime_owner: str = "SessionTurnMixin→ReflexiveInterpreter→SPBE"
    contract_version: str = SPBE_CONTRACT_VERSION
    contract_sha256: str = SPBE_CONTRACT_SHA256

    @property
    def allow_model_tools(self) -> bool:
        return isinstance(self.result, ProposalReady) and bool(self.allowed_tool_names)

    def prompt_block(self) -> str:
        if isinstance(self.result, ProposalReady):
            return (
                "BAGO SPBE DECISION\n"
                "kind=PROPOSAL_READY; semantic proposal exists. "
                "SPBE does not authorize or execute effects. "
                "Only the listed read-only model tools may be exposed by this turn."
            )
        return (
            "BAGO SPBE DECISION\n"
            f"kind=TERMINAL; outcome={self.result.terminal_result.outcome.value}. "
            "Do not call model tools. Do not treat this semantic terminal as authorization. "
            "Respond without effects or request clarification when appropriate."
        )

    def to_metadata(self) -> dict[str, Any]:
        if isinstance(self.result, ProposalReady):
            result_payload: dict[str, Any] = {
                "kind": self.result.kind.value,
                "proposal_ref": self.result.proposal.proposal_id,
                "intent_root_ref": self.result.proposal.intent_root_ref,
                "selected_capabilities": [
                    ref.stable_key for ref in self.result.proposal.capability_refs
                ],
            }
        else:
            result_payload = {
                "kind": self.result.kind.value,
                "terminal_result_id": self.result.terminal_result.terminal_result_id,
                "intent_root_ref": self.result.terminal_result.intent_root_ref,
                "outcome": self.result.terminal_result.outcome.value,
                "unresolved_conditions": list(self.result.terminal_result.unresolved_conditions),
            }
        return {
            "schema": SPBE_RUNTIME_SCHEMA,
            "contract_version": self.contract_version,
            "contract_sha256": self.contract_sha256,
            "runtime_owner": self.runtime_owner,
            "result": result_payload,
            "allowed_tool_names": list(self.allowed_tool_names),
            "proposed_pec_envelope": dict(self.proposed_pec_envelope or {}),
        }


class BagoSPBEAdapter:
    """Bind Reflexive Interpreter output and ToolRegistry state into SPBE."""

    def __init__(self, tool_registry: Any) -> None:
        self.tool_registry = tool_registry
        self.engine = SemanticProceduralBehaviorEngine()

    def compile_turn(
        self,
        *,
        user_message: str,
        reflexive_analysis: Mapping[str, Any],
        intent: str,
        tool_requested: bool,
    ) -> SPBERuntimeDecision:
        intent_id = str(reflexive_analysis.get("question_id") or "").strip()
        if not intent_id:
            intent_id = "intent-" + hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:16]
        root = IntentRoot.create(intent_id, user_message)
        task_id = "task-" + hashlib.sha256(
            (root.intent_id + "|" + intent).encode("utf-8")
        ).hexdigest()[:16]

        confidence = self._float(reflexive_analysis.get("confidence"), default=0.0)
        metrics = reflexive_analysis.get("metrics")
        ambiguity = self._float(metrics.get("ambiguity") if isinstance(metrics, Mapping) else 0.0, default=0.0)
        if confidence < 0.45 and ambiguity >= 0.50:
            terminal = self.engine.terminal(
                root,
                task_id,
                SemanticTerminalOutcome.AMBIGUOUS_INTENT,
                evidence=(f"confidence={confidence:.2f}", f"ambiguity={ambiguity:.2f}"),
                unresolved=("reflexive_interpretation_requires_clarification",),
            )
            return SPBERuntimeDecision(terminal, (), None)

        tool_names = self._model_tool_names()
        provides = {"dialogue.respond"}
        requirements = [Requirement("REQ-RESPOND", "dialogue.respond")]
        steps = [
            ProceduralStepCandidate(
                step_id="turn.respond",
                operation_class="dialogue.respond",
                semantic_basis=(SemanticBasisRef("INTENT_OBJECTIVE_REF", root.intent_id, "SATISFIES"),),
            )
        ]
        if tool_requested:
            requirements.append(Requirement("REQ-CONTEXT-INSPECT", "context.inspect"))
            if tool_names:
                provides.add("context.inspect")
                steps.append(
                    ProceduralStepCandidate(
                        step_id="turn.inspect-context",
                        operation_class="filesystem.read",
                        semantic_basis=(SemanticBasisRef("INTENT_OBJECTIVE_REF", root.intent_id, "SUPPORTS"),),
                    )
                )

        snapshot = json.dumps(tool_names, ensure_ascii=False, separators=(",", ":"))
        candidate = CapabilityCandidate(
            ref=CapabilityRef(
                capability_id="bago.session.turn",
                capability_version="1",
                provider_id="bago-core",
                contract_fingerprint=hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
            ),
            mode=ResolutionMode.REUSE,
            provides=frozenset(provides),
            proposed_steps=tuple(steps),
            tool_names=tool_names,
        )
        formalization = reflexive_analysis.get("formalization")
        objective = ""
        if isinstance(formalization, Mapping):
            objective = str(formalization.get("objective") or "")
        objective = objective or str(reflexive_analysis.get("intent") or intent or "respond")
        task = SemanticTask(
            task_id=task_id,
            intent_root=root,
            objective=objective,
            requirements=tuple(requirements),
            candidates=(candidate,),
            completion_conditions=("response addresses the bound user objective",),
            evidence_requirements=("workspace-dependent claims require tool/evidence receipts",),
        )
        result = self.engine.compile(task)
        if isinstance(result, ProposalReady):
            envelope = self.engine.to_pec_envelope(result)
            return SPBERuntimeDecision(result, tool_names if tool_requested else (), envelope)
        return SPBERuntimeDecision(result, (), None)

    def _model_tool_names(self) -> tuple[str, ...]:
        names: list[str] = []
        try:
            iterator = iter(self.tool_registry)
        except Exception:
            return ()
        for name, entry in iterator:
            if bool(getattr(entry, "deprecated", False)):
                continue
            try:
                effect_id = self.tool_registry.model_effect_id(name)
            except Exception:
                effect_id = None
            if effect_id == "filesystem.read":
                names.append(str(name))
        return tuple(sorted(set(names)))

    @staticmethod
    def _float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
