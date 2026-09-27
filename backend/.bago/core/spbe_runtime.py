#!/usr/bin/env python3
"""BAGO host adapter for the frozen SPBE behavior-engine implementation.

The decision core is reused from the previously materialized bago_spbe
package. This adapter only translates BAGO session/reflexive state into that
core and translates the result back into host metadata.

SPBE never issues authorization and never executes material effects.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from bago_spbe import (
    BoundedCycleContract,
    BoundResource,
    CapabilityCandidate,
    CapabilityRef,
    DependencyCycle,
    DependencyEdge,
    Eligibility,
    IntentRoot,
    ProceduralStepCandidate,
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
    SemanticTerminalResult,
    Terminal,
    UncertaintyAssessment,
    UncertaintyDisposition,
    UncertaintyState,
)

SPBE_CONTRACT_VERSION = "v0.5-FIX5"
SPBE_CONTRACT_SHA256 = "2e342c242c8f77600cfe3dd6a7b1a1818fb35cbf64105aa32b5a578709fe703a"
SPBE_SOURCE_PACK = "BAGO_SPBE_BEHAVIOR_ENGINE_PACK_v0.1.zip"
SPBE_SOURCE_PACK_SHA256 = "f553175deb048855b34342ca1f5d9f114f88d79f30a00a4648b89c5cb7b49340"
SPBE_RUNTIME_SCHEMA = "bago.spbe.runtime.v1"


@dataclass(frozen=True)
class SPBERuntimeDecision:
    result: ProposalReady | Terminal
    allowed_tool_names: tuple[str, ...]
    proposed_pec_envelope: Mapping[str, Any] | None
    workspace_transport_requested: bool = False
    runtime_owner: str = "SessionTurnMixin→ReflexiveInterpreter→bago_spbe"
    contract_version: str = SPBE_CONTRACT_VERSION
    contract_sha256: str = SPBE_CONTRACT_SHA256
    source_pack_sha256: str = SPBE_SOURCE_PACK_SHA256

    @property
    def is_terminal(self) -> bool:
        return isinstance(self.result, Terminal)

    @property
    def allow_model_tools(self) -> bool:
        return isinstance(self.result, ProposalReady) and bool(self.allowed_tool_names)

    def prompt_block(self) -> str:
        if isinstance(self.result, ProposalReady):
            return (
                "BAGO SPBE DECISION\n"
                "kind=PROPOSAL_READY; semantic proposal exists. "
                "SPBE does not authorize or execute effects. "
                "Any runtime effect still requires the authority owned outside SPBE."
            )
        return (
            "BAGO SPBE DECISION\n"
            f"kind=TERMINAL; outcome={self.result.terminal_result.outcome.value}. "
            "This is a hard semantic stop: do not dispatch provider workspace tools, "
            "model tools, PEC normal handoff, or material effects."
        )

    def terminal_response(self) -> str:
        if not isinstance(self.result, Terminal):
            raise ValueError("terminal_response requires a Terminal SPBE result")
        outcome = self.result.terminal_result.outcome
        if outcome is SemanticTerminalOutcome.AMBIGUOUS_INTENT:
            return "Necesito aclarar la intención antes de continuar con herramientas o cambios."
        if outcome is SemanticTerminalOutcome.INSUFFICIENT_INFORMATION:
            return "Falta información necesaria para continuar de forma gobernada."
        if outcome is SemanticTerminalOutcome.UNRESOLVED_CONFLICT:
            return "Hay un conflicto semántico sin resolver; no continuaré con herramientas o cambios."
        if outcome is SemanticTerminalOutcome.NO_ELIGIBLE_SOLUTION:
            return "No hay una capacidad elegible para continuar con esta solicitud."
        return "La solicitud no puede compilarse de forma semánticamente válida."

    def to_metadata(self) -> dict[str, Any]:
        if isinstance(self.result, ProposalReady):
            payload: dict[str, Any] = {
                "kind": self.result.kind.value,
                "proposal_ref": self.result.proposal.proposal_id,
                "intent_root_ref": self.result.proposal.intent_root_ref,
                "selected_capabilities": [
                    ref.stable_key for ref in self.result.proposal.capability_refs
                ],
                "resolution_policy_ref": self.result.proposal.resolution_decision.policy_ref,
                "authorization_requirements": list(self.result.proposal.authorization_requirements),
            }
        else:
            payload = {
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
            "source_pack": SPBE_SOURCE_PACK,
            "source_pack_sha256": self.source_pack_sha256,
            "runtime_owner": self.runtime_owner,
            "workspace_transport_requested": self.workspace_transport_requested,
            "result": payload,
            "allowed_tool_names": list(self.allowed_tool_names),
            "proposed_pec_envelope": dict(self.proposed_pec_envelope or {}),
        }


class BagoSPBEAdapter:
    """Translate BAGO turn state into the full behavior-pack SPBE core."""

    def __init__(self, tool_registry: Any) -> None:
        self.tool_registry = tool_registry
        self.engine = SemanticProceduralBehaviorEngine(
            resolution_policy=ResolutionPolicy(),
        )

    def compile_turn(
        self,
        *,
        user_message: str,
        reflexive_analysis: Mapping[str, Any],
        intent: str,
        tool_requested: bool,
        workspace_transport_requested: bool = False,
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
        ambiguity = self._float(
            metrics.get("ambiguity") if isinstance(metrics, Mapping) else 0.0,
            default=0.0,
        )
        if confidence < 0.45 and ambiguity >= 0.50:
            terminal = self._terminal(
                root,
                task_id,
                SemanticTerminalOutcome.AMBIGUOUS_INTENT,
                evidence=(f"confidence={confidence:.2f}", f"ambiguity={ambiguity:.2f}"),
                unresolved=("reflexive_interpretation_requires_clarification",),
            )
            return SPBERuntimeDecision(
                terminal,
                (),
                None,
                workspace_transport_requested=workspace_transport_requested,
            )

        tool_names = self._model_tool_names()
        provides = {"dialogue.respond"}
        requirements: list[Requirement] = [
            Requirement(
                "REQ-RESPOND",
                "provides",
                {"capability": "dialogue.respond"},
                semantic_basis=(SemanticBasisRef("INTENT_OBJECTIVE_REF", root.intent_id, "SATISFIES"),),
            )
        ]
        steps: list[ProceduralStepCandidate] = [
            ProceduralStepCandidate(
                step_id="turn.respond",
                operation_class="dialogue.respond",
                semantic_basis=(SemanticBasisRef("INTENT_OBJECTIVE_REF", root.intent_id, "SATISFIES"),),
            )
        ]
        semantic_artifact_ids = {root.intent_id, "REQ-RESPOND"}

        if tool_requested:
            requirements.append(
                Requirement(
                    "REQ-CONTEXT-INSPECT",
                    "provides",
                    {"capability": "context.inspect"},
                    semantic_basis=(SemanticBasisRef("INTENT_OBJECTIVE_REF", root.intent_id, "SUPPORTS"),),
                )
            )
            semantic_artifact_ids.add("REQ-CONTEXT-INSPECT")
            if tool_names:
                provides.add("context.inspect")
                steps.append(
                    ProceduralStepCandidate(
                        step_id="turn.inspect-context",
                        operation_class="filesystem.read",
                        evidence_obligations=("tool_receipt",),
                        semantic_basis=(
                            SemanticBasisRef("REQUIREMENT_REF", "REQ-CONTEXT-INSPECT", "SATISFIES"),
                        ),
                    )
                )

        if workspace_transport_requested:
            requirements.append(
                Requirement(
                    "REQ-WORKSPACE-TRANSPORT",
                    "provides",
                    {"capability": "provider.workspace"},
                    semantic_basis=(SemanticBasisRef("INTENT_OBJECTIVE_REF", root.intent_id, "SUPPORTS"),),
                )
            )
            semantic_artifact_ids.add("REQ-WORKSPACE-TRANSPORT")
            provides.add("provider.workspace")
            steps.append(
                ProceduralStepCandidate(
                    step_id="turn.provider-workspace",
                    operation_class="provider.workspace",
                    evidence_obligations=("provider_transport_receipt",),
                    authorization_requirement="RUNTIME_AUTHORITY_EXTERNAL_TO_SPBE",
                    semantic_basis=(
                        SemanticBasisRef("REQUIREMENT_REF", "REQ-WORKSPACE-TRANSPORT", "SATISFIES"),
                    ),
                )
            )

        snapshot = json.dumps(
            {
                "tools": tool_names,
                "workspace_transport": workspace_transport_requested,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        candidate = CapabilityCandidate(
            ref=CapabilityRef(
                capability_id="bago.session.turn",
                capability_version="1",
                provider_id="bago-core",
                contract_fingerprint=hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
            ),
            mode=ResolutionMode.REUSE,
            provides=frozenset(provides),
            evidence_capabilities=frozenset({"tool_receipt", "provider_transport_receipt"}),
            authorization_requirement=(
                "RUNTIME_AUTHORITY_EXTERNAL_TO_SPBE" if workspace_transport_requested else None
            ),
            proposed_steps=tuple(steps),
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
            evidence_requirements=("workspace-dependent claims require evidence receipts",),
            semantic_artifact_ids=frozenset(semantic_artifact_ids),
        )
        result = self.engine.compile(task)
        if isinstance(result, ProposalReady):
            envelope = dict(self.engine.to_pec_envelope(result))
            envelope.update({
                "schema": "bago.spbe.to-pec.v1",
                "dispatch_state": "NOT_DISPATCHED_PEC_RUNTIME_NOT_BOUND",
            })
            return SPBERuntimeDecision(
                result,
                tool_names if tool_requested else (),
                envelope,
                workspace_transport_requested=workspace_transport_requested,
            )
        return SPBERuntimeDecision(
            result,
            (),
            None,
            workspace_transport_requested=workspace_transport_requested,
        )

    @classmethod
    def fail_closed(
        cls,
        *,
        user_message: str,
        reflexive_analysis: Mapping[str, Any],
        error: Exception | str,
        workspace_transport_requested: bool = False,
    ) -> SPBERuntimeDecision:
        intent_id = str(reflexive_analysis.get("question_id") or "").strip()
        if not intent_id:
            intent_id = "intent-" + hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:16]
        root = IntentRoot.create(intent_id, user_message)
        task_id = "task-" + hashlib.sha256(
            (root.intent_id + "|fail-closed").encode("utf-8")
        ).hexdigest()[:16]
        terminal = cls._terminal(
            root,
            task_id,
            SemanticTerminalOutcome.INSUFFICIENT_INFORMATION,
            evidence=("spbe_runtime_error", type(error).__name__ if isinstance(error, Exception) else "error"),
            unresolved=(str(error)[:300],),
        )
        return SPBERuntimeDecision(
            terminal,
            (),
            None,
            workspace_transport_requested=workspace_transport_requested,
        )

    @staticmethod
    def _terminal(
        root: IntentRoot,
        task_id: str,
        outcome: SemanticTerminalOutcome,
        *,
        evidence: tuple[str, ...] = (),
        unresolved: tuple[str, ...] = (),
    ) -> Terminal:
        terminal_id = "terminal-" + hashlib.sha256(
            (task_id + "|" + outcome.value + "|" + "|".join(unresolved)).encode("utf-8")
        ).hexdigest()[:16]
        return Terminal(
            kind=SemanticCompilationKind.TERMINAL,
            terminal_result=SemanticTerminalResult(
                terminal_result_id=terminal_id,
                intent_root_ref=root.intent_id,
                outcome=outcome,
                semantic_basis=(
                    SemanticBasisRef(
                        "INTENT_OBJECTIVE_REF",
                        root.intent_id,
                        "TERMINATES",
                        root.original_request_fingerprint,
                    ),
                ),
                evidence=evidence,
                unresolved_conditions=unresolved,
            ),
            evidence=evidence,
        )

    def _model_tool_names(self) -> tuple[str, ...]:
        """Return only tools canonically normalized as read-only model effects.

        Compatibility registries may expose to_openai/execute_model_call
        without iteration or model_effect_id. In that case, intersect their
        advertised names with BAGO's canonical MODEL_TOOL_EFFECTS map instead
        of treating the whole turn as having no eligible read capability.
        """
        names: set[str] = set()
        try:
            for name, entry in iter(self.tool_registry):
                if bool(getattr(entry, "deprecated", False)):
                    continue
                try:
                    effect_id = self.tool_registry.model_effect_id(name)
                except Exception:
                    effect_id = None
                if effect_id == "filesystem.read":
                    names.add(str(name))
        except Exception:
            pass

        if not names:
            try:
                from tool_registry import MODEL_TOOL_EFFECTS
                advertised = self.tool_registry.to_openai()
                for item in advertised or []:
                    function = item.get("function") if isinstance(item, dict) else None
                    name = str((function or {}).get("name") or "")
                    if MODEL_TOOL_EFFECTS.get(name) == "filesystem.read":
                        names.add(name)
            except Exception:
                pass
        return tuple(sorted(names))

    @staticmethod
    def _float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


__all__ = [
    "BagoSPBEAdapter",
    "SPBERuntimeDecision",
    "SPBE_CONTRACT_VERSION",
    "SPBE_CONTRACT_SHA256",
    "SPBE_SOURCE_PACK_SHA256",
    "Eligibility",
    "ResolutionMode",
    "SemanticCompilationKind",
    "SemanticTerminalOutcome",
    "IntentRoot",
    "SemanticBasisRef",
    "Requirement",
    "SemanticEntity",
    "ResourceBindingAttempt",
    "BoundResource",
    "UncertaintyAssessment",
    "UncertaintyDisposition",
    "UncertaintyState",
    "SemanticConflict",
    "DependencyEdge",
    "DependencyCycle",
    "BoundedCycleContract",
    "CapabilityRef",
    "CapabilityCandidate",
    "ProceduralStepCandidate",
    "ResolutionPolicy",
    "SemanticTask",
    "SemanticTerminalResult",
    "ProposalReady",
    "Terminal",
    "SemanticProceduralBehaviorEngine",
]
