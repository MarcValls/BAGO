from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .cycles import SemanticCycleValidator
from .eligibility import EligibilityEvaluator
from .model import (
    BindingDecision,
    CapabilityCandidate,
    CycleClassification,
    Eligibility,
    ProposalReady,
    ResolutionPolicy,
    SemanticCompilationKind,
    SemanticTask,
    SemanticTerminalOutcome,
    SemanticTerminalResult,
    Terminal,
    UncertaintyDisposition,
)
from .resolution import CapabilityResolver


@dataclass
class SemanticProceduralBehaviorEngine:
    eligibility: EligibilityEvaluator = EligibilityEvaluator()
    resolver: CapabilityResolver = CapabilityResolver()
    cycle_validator: SemanticCycleValidator = SemanticCycleValidator()
    resolution_policy: ResolutionPolicy = ResolutionPolicy()

    def compile(self, task: SemanticTask):
        """Compile structured semantics into ProposalReady or Terminal.

        This method never validates runtime authorization and never executes effects.
        """
        terminal = self._preflight_terminal(task)
        if terminal:
            return terminal

        decisions = tuple(self.eligibility.evaluate(c, task.requirements) for c in task.candidates)
        resolution = self.resolver.resolve(task.candidates, decisions, self.resolution_policy)
        if resolution is None:
            failed = [d.candidate_ref.stable_key for d in decisions if d.decision is Eligibility.NOT_ELIGIBLE]
            unknown = [d.candidate_ref.stable_key for d in decisions if d.decision is Eligibility.UNKNOWN]
            return self._terminal(
                task,
                SemanticTerminalOutcome.NO_ELIGIBLE_SOLUTION,
                evidence=tuple(f"not_eligible:{x}" for x in failed) + tuple(f"unknown:{x}" for x in unknown),
                unresolved=tuple(unknown),
            )

        selected_keys = {x.stable_key for x in resolution.selected_capability_refs}
        selected = tuple(c for c in task.candidates if c.ref.stable_key in selected_keys)
        steps = tuple(step for c in selected for step in c.proposed_steps)

        orphan_reasons = self._validate_steps(task, steps)
        if orphan_reasons:
            return self._terminal(
                task,
                SemanticTerminalOutcome.SEMANTICALLY_UNSATISFIABLE,
                evidence=tuple(orphan_reasons),
                unresolved=tuple(orphan_reasons),
            )

        from .model import ProceduralProposal
        proposal = ProceduralProposal(
            proposal_id=f"proposal-{uuid4().hex}",
            intent_root_ref=task.intent_root.intent_id,
            objective=task.objective,
            capability_refs=resolution.selected_capability_refs,
            candidate_steps=steps,
            completion_conditions=task.completion_conditions,
            evidence_requirements=task.evidence_requirements,
            authorization_requirements=tuple(sorted({c.authorization_requirement for c in selected if c.authorization_requirement})),
            resolution_decision=resolution,
        )
        return ProposalReady(
            kind=SemanticCompilationKind.PROPOSAL_READY,
            proposal=proposal,
            evidence=tuple(d.decision.value + ":" + d.candidate_ref.stable_key for d in decisions),
        )

    def to_pec_envelope(self, result) -> dict:
        """Create a PEC envelope only from ProposalReady; terminal branches are rejected."""
        if not isinstance(result, ProposalReady):
            raise ValueError("Terminal semantic results MUST NOT enter normal PEC handoff")
        p = result.proposal
        return {
            "kind": "SPBEtoPECEnvelope",
            "proposal_ref": p.proposal_id,
            "intent_root_ref": p.intent_root_ref,
            "capability_refs": [r.stable_key for r in p.capability_refs],
            "candidate_steps": [s.step_id for s in p.candidate_steps],
            "completion_conditions": list(p.completion_conditions),
            "evidence_requirements": list(p.evidence_requirements),
            "authorization_requirements": list(p.authorization_requirements),
        }

    def _preflight_terminal(self, task: SemanticTask):
        unresolved_conflicts = [c.conflict_id for c in task.conflicts if not c.resolved]
        if unresolved_conflicts:
            return self._terminal(task, SemanticTerminalOutcome.UNRESOLVED_CONFLICT, unresolved=tuple(unresolved_conflicts))

        attempt_by_entity = {a.semantic_entity_ref: a for a in task.binding_attempts}
        bound_by_entity = {b.semantic_entity_ref: b for b in task.bound_resources}
        binding_issues = []
        binding_conflicts = []
        for entity in task.entities:
            if not entity.binding_required:
                continue
            attempt = attempt_by_entity.get(entity.semantic_entity_id)
            bound = bound_by_entity.get(entity.semantic_entity_id)
            if attempt is None:
                binding_issues.append(f"{entity.semantic_entity_id}:NO_BINDING_ATTEMPT")
                continue
            if attempt.decision is BindingDecision.CONFLICTED:
                binding_conflicts.append(f"{entity.semantic_entity_id}:CONFLICTED")
            elif attempt.decision is not BindingDecision.BOUND or bound is None:
                binding_issues.append(f"{entity.semantic_entity_id}:{attempt.decision.value}")
            else:
                if bound.binding_attempt_ref != attempt.binding_attempt_id:
                    binding_issues.append(f"{entity.semantic_entity_id}:BINDING_ATTEMPT_MISMATCH")
                    continue
                if tuple(bound.binding_evidence) != tuple(attempt.binding_evidence):
                    binding_issues.append(f"{entity.semantic_entity_id}:BINDING_EVIDENCE_MISMATCH")
                    continue
                if attempt.candidate_resources and bound.resource_identity not in attempt.candidate_resources:
                    binding_issues.append(f"{entity.semantic_entity_id}:RESOURCE_NOT_IN_ACCEPTED_CANDIDATES")
                    continue
                if not bound.fingerprint_is_valid():
                    binding_issues.append(f"{entity.semantic_entity_id}:RESOURCE_FINGERPRINT_INVALID")
        if binding_conflicts:
            return self._terminal(task, SemanticTerminalOutcome.UNRESOLVED_CONFLICT, unresolved=tuple(binding_conflicts))
        if binding_issues:
            return self._terminal(task, SemanticTerminalOutcome.INSUFFICIENT_INFORMATION, unresolved=tuple(binding_issues))

        uncertainty_issues = []
        for u in task.uncertainties:
            if u.disposition in {
                UncertaintyDisposition.REQUIRE_EVIDENCE,
                UncertaintyDisposition.REQUIRE_CONFIRMATION,
                UncertaintyDisposition.SET_ELIGIBILITY_UNKNOWN,
                UncertaintyDisposition.BLOCK_SEMANTIC_COMPILATION,
            }:
                uncertainty_issues.append(f"{u.assessment_id}:{u.disposition.value}")
        if uncertainty_issues:
            return self._terminal(task, SemanticTerminalOutcome.INSUFFICIENT_INFORMATION, unresolved=tuple(uncertainty_issues))

        cycles = self.cycle_validator.detect(task.dependency_edges, task.bounded_cycles, task.benign_cycles)
        invalid = [c for c in cycles if c.classification is CycleClassification.INVALID_CYCLE]
        if invalid:
            evidence = tuple(x for c in invalid for x in c.detection_evidence)
            return self._terminal(task, SemanticTerminalOutcome.SEMANTICALLY_UNSATISFIABLE, evidence=evidence)
        return None

    def _validate_steps(self, task: SemanticTask, steps):
        known = set(task.semantic_artifact_ids)
        known.add(task.intent_root.intent_id)
        known.update(r.requirement_id for r in task.requirements)
        known.update(e.semantic_entity_id for e in task.entities)
        problems = []
        for step in steps:
            if not step.semantic_basis:
                problems.append(f"ORPHAN_PROCEDURAL_STEP:{step.step_id}:no-semantic-basis")
                continue
            for b in step.semantic_basis:
                if b.source_id not in known:
                    problems.append(f"ORPHAN_PROCEDURAL_STEP:{step.step_id}:unknown-basis:{b.source_id}")
        return problems

    def _terminal(self, task, outcome, evidence=(), unresolved=()):
        result = SemanticTerminalResult(
            terminal_result_id=f"terminal-{uuid4().hex}",
            intent_root_ref=task.intent_root.intent_id,
            outcome=outcome,
            evidence=tuple(evidence),
            unresolved_conditions=tuple(unresolved),
        )
        return Terminal(kind=SemanticCompilationKind.TERMINAL, terminal_result=result, evidence=tuple(evidence))
