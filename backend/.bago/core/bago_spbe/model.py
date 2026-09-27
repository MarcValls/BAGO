from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping, Sequence


class Eligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNKNOWN = "UNKNOWN"


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class AuthorizationState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED_NOT_YET_GRANTED = "REQUIRED_NOT_YET_GRANTED"
    EXTERNALLY_VALIDATED = "EXTERNALLY_VALIDATED"
    UNKNOWN = "UNKNOWN"


class ExecutionReadiness(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class ResolutionMode(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    NEW = "NEW"


class BindingDecision(str, Enum):
    BOUND = "BOUND"
    UNBOUND = "UNBOUND"
    AMBIGUOUS = "AMBIGUOUS"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"


class UncertaintyState(str, Enum):
    CERTAIN = "CERTAIN"
    ACCEPTABLE = "ACCEPTABLE"
    REQUIRES_EVIDENCE = "REQUIRES_EVIDENCE"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    UNKNOWN = "UNKNOWN"
    BLOCKING = "BLOCKING"


class UncertaintyDisposition(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    REQUIRE_EVIDENCE = "REQUIRE_EVIDENCE"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    SET_ELIGIBILITY_UNKNOWN = "SET_ELIGIBILITY_UNKNOWN"
    BLOCK_SEMANTIC_COMPILATION = "BLOCK_SEMANTIC_COMPILATION"


class CycleClassification(str, Enum):
    INVALID_CYCLE = "INVALID_CYCLE"
    BOUNDED_ITERATIVE_CYCLE = "BOUNDED_ITERATIVE_CYCLE"
    BENIGN_REFERENCE_CYCLE = "BENIGN_REFERENCE_CYCLE"


class SemanticTerminalOutcome(str, Enum):
    NO_ELIGIBLE_SOLUTION = "NO_ELIGIBLE_SOLUTION"
    AMBIGUOUS_INTENT = "AMBIGUOUS_INTENT"
    UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    SEMANTICALLY_UNSATISFIABLE = "SEMANTICALLY_UNSATISFIABLE"


class SemanticCompilationKind(str, Enum):
    PROPOSAL_READY = "PROPOSAL_READY"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True)
class IntentRoot:
    intent_id: str
    original_request: str
    original_request_fingerprint: str
    authority: str = "USER"

    @classmethod
    def create(cls, intent_id: str, original_request: str) -> "IntentRoot":
        fp = sha256(original_request.encode("utf-8")).hexdigest()
        return cls(intent_id=intent_id, original_request=original_request, original_request_fingerprint=fp)


@dataclass(frozen=True)
class SemanticBasisRef:
    basis_type: str
    source_id: str
    relation: str
    source_fingerprint: str | None = None


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    predicate: str
    args: Mapping[str, Any] = field(default_factory=dict)
    hard: bool = True
    semantic_basis: tuple[SemanticBasisRef, ...] = ()


@dataclass(frozen=True)
class SemanticConflict:
    conflict_id: str
    conflict_type: str
    resolved: bool
    claim_a: str = ""
    claim_b: str = ""


@dataclass(frozen=True)
class SemanticEntity:
    semantic_entity_id: str
    semantic_type: str
    descriptors: tuple[str, ...] = ()
    binding_required: bool = False


@dataclass(frozen=True)
class ResourceBindingAttempt:
    binding_attempt_id: str
    semantic_entity_ref: str
    decision: BindingDecision
    candidate_resources: tuple[str, ...] = ()
    binding_evidence: tuple[str, ...] = ()
    observed_at: str | None = None


@dataclass(frozen=True)
class BoundResource:
    bound_resource_id: str
    semantic_entity_ref: str
    resource_kind: str
    resource_identity: str
    provider_or_owner_ref: str
    binding_attempt_ref: str
    binding_evidence: tuple[str, ...]
    resource_fingerprint: str | None = None


@dataclass(frozen=True)
class UncertaintyAssessment:
    assessment_id: str
    target_ref: str
    resulting_state: UncertaintyState
    disposition: UncertaintyDisposition
    source_uncertainties: tuple[str, ...] = ()
    resolving_evidence: tuple[str, ...] = ()
    explanation: str = ""


@dataclass(frozen=True)
class CapabilityRef:
    capability_id: str
    capability_version: str
    provider_id: str
    contract_fingerprint: str

    @property
    def stable_key(self) -> str:
        return f"{self.capability_id}@{self.capability_version}:{self.provider_id}:{self.contract_fingerprint}"


@dataclass(frozen=True)
class CapabilityCandidate:
    ref: CapabilityRef
    mode: ResolutionMode
    provides: frozenset[str] = frozenset()
    attributes: Mapping[str, Any] = field(default_factory=dict)
    evidence_capabilities: frozenset[str] = frozenset()
    semantic_loss: int = 0
    adaptation_cost: int = 0
    procedural_complexity: int = 0
    evidence_burden: int = 0
    authorization_requirement: str | None = None
    proposed_steps: tuple["ProceduralStepCandidate", ...] = ()


@dataclass(frozen=True)
class EligibilityDecision:
    candidate_ref: CapabilityRef
    decision: Eligibility
    requirements_satisfied: tuple[str, ...] = ()
    requirements_failed: tuple[str, ...] = ()
    unknown_requirements: tuple[str, ...] = ()
    decision_basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionPolicy:
    policy_id: str = "bago.spbe.default-resolution"
    policy_version: str = "1"
    reuse_preference: tuple[ResolutionMode, ...] = (
        ResolutionMode.REUSE,
        ResolutionMode.EXTEND,
        ResolutionMode.NEW,
    )
    semantic_loss_override_threshold: int = 2
    adaptation_cost_override_threshold: int = 4
    complexity_override_threshold: int = 4
    evidence_burden_override_threshold: int = 4


@dataclass(frozen=True)
class ResolutionDecision:
    policy_ref: str
    selected_capability_refs: tuple[CapabilityRef, ...]
    eligible_candidates: tuple[str, ...]
    rejected_candidates: tuple[str, ...]
    selected_mode: ResolutionMode
    override_of_default_preference: bool
    override_basis: tuple[str, ...] = ()
    explanation: str = ""


@dataclass(frozen=True)
class DependencyEdge:
    source_id: str
    target_id: str
    relation: str = "DEPENDS_ON"


@dataclass(frozen=True)
class BoundedCycleContract:
    nodes: frozenset[str]
    entry_condition: str
    progress_measure: str
    max_iterations: int
    exit_condition: str
    no_progress_outcome: str


@dataclass(frozen=True)
class DependencyCycle:
    node_refs: tuple[str, ...]
    classification: CycleClassification
    relation_types: tuple[str, ...]
    detection_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ProceduralStepCandidate:
    step_id: str
    operation_class: str
    capability_ref: CapabilityRef | None = None
    dependencies: tuple[str, ...] = ()
    evidence_obligations: tuple[str, ...] = ()
    authorization_requirement: str | None = None
    semantic_basis: tuple[SemanticBasisRef, ...] = ()


@dataclass(frozen=True)
class ProceduralProposal:
    proposal_id: str
    intent_root_ref: str
    objective: str
    capability_refs: tuple[CapabilityRef, ...]
    candidate_steps: tuple[ProceduralStepCandidate, ...]
    completion_conditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    authorization_requirements: tuple[str, ...]
    resolution_decision: ResolutionDecision


@dataclass(frozen=True)
class SemanticTerminalResult:
    terminal_result_id: str
    intent_root_ref: str
    outcome: SemanticTerminalOutcome
    semantic_basis: tuple[SemanticBasisRef, ...] = ()
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
    entities: tuple[SemanticEntity, ...] = ()
    binding_attempts: tuple[ResourceBindingAttempt, ...] = ()
    bound_resources: tuple[BoundResource, ...] = ()
    uncertainties: tuple[UncertaintyAssessment, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    dependency_edges: tuple[DependencyEdge, ...] = ()
    bounded_cycles: tuple[BoundedCycleContract, ...] = ()
    benign_cycles: tuple[frozenset[str], ...] = ()
    semantic_artifact_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SemanticInterpretation:
    """Host-produced semantic interpretation bound to exactly one IntentRoot."""
    intent_root: IntentRoot
    objective: str
    requirements: tuple[Requirement, ...]
    completion_conditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...] = ()
    entities: tuple[SemanticEntity, ...] = ()
    uncertainties: tuple[UncertaintyAssessment, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    dependency_edges: tuple[DependencyEdge, ...] = ()
    bounded_cycles: tuple[BoundedCycleContract, ...] = ()
    benign_cycles: tuple[frozenset[str], ...] = ()
    semantic_artifact_ids: frozenset[str] = frozenset()
