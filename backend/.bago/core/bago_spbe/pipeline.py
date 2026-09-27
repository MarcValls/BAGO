from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .engine import SemanticProceduralBehaviorEngine
from .model import IntentRoot, SemanticTask
from .ports import CapabilityDiscoveryPort, ResourceBindingPort, SemanticInterpreterPort, SemanticNormalizerPort


@dataclass
class SPBEPipeline:
    """Host-facing SPBE pipeline.

    Ports perform interpretation/discovery/binding. The deterministic decision
    engine remains effect-free and never validates authorization.
    """
    interpreter: SemanticInterpreterPort
    normalizer: SemanticNormalizerPort
    capabilities: CapabilityDiscoveryPort
    resource_binder: ResourceBindingPort
    decision_engine: SemanticProceduralBehaviorEngine

    def compile_request(self, original_request: str, *, intent_id: str | None = None, task_id: str | None = None):
        intent = IntentRoot.create(intent_id or f"intent-{uuid4().hex}", original_request)
        interpreted = self.interpreter.interpret(intent)
        if interpreted.intent_root.intent_id != intent.intent_id:
            raise ValueError("Interpreter changed IntentRoot identity")
        normalized = self.normalizer.normalize(interpreted)
        if normalized.intent_root.original_request_fingerprint != intent.original_request_fingerprint:
            raise ValueError("Normalizer changed IntentRoot authority/fingerprint")
        candidates = self.capabilities.discover(normalized)
        attempts, bound = self.resource_binder.bind(normalized)
        task = SemanticTask(
            task_id=task_id or f"task-{uuid4().hex}",
            intent_root=intent,
            objective=normalized.objective,
            requirements=normalized.requirements,
            candidates=candidates,
            completion_conditions=normalized.completion_conditions,
            evidence_requirements=normalized.evidence_requirements,
            entities=normalized.entities,
            binding_attempts=attempts,
            bound_resources=bound,
            uncertainties=normalized.uncertainties,
            conflicts=normalized.conflicts,
            dependency_edges=normalized.dependency_edges,
            bounded_cycles=normalized.bounded_cycles,
            benign_cycles=normalized.benign_cycles,
            semantic_artifact_ids=normalized.semantic_artifact_ids,
        )
        return self.decision_engine.compile(task)
