"""context_envelope.py — ContextFragment, ContextEnvelope, ContextReceipt, SystemPromptCapsule.

F2: Estructura el contexto que se envía al LLM en un envelope inmutable,
genera un receipt con los metadatos de la llamada, y encapsula el system
prompt en secciones versionadas.

ContextFragment:
    - fragment_id: str
    - content: str
    - summary: str
    - source_type: str
    - source_uri: str
    - scope: str
    - authority_level: str
    - created_at: str
    - retrieved_at: str
    - expires_at: str
    - content_hash: str
    - revision: str
    - token_count: int
    - sensitivity_level: str
    - cache_policy: str
    - invalidation_causes: list[str]
    - relevance_score: float
    - authority_score: float
    - freshness_score: float
    - estimated_cost: float
    - evidence_refs: list[dict]
    - reason_for_inclusion: str
    - status: str
    - metadata: dict

ContextEnvelope:
    - system_prompt: str (capsule renderizada)
    - messages: list[dict] (historial normalizado + mensaje actual)
    - tools: list[dict] | None
    - metadata: dict (intent, bago_mode, goal, model, provider)
    - fragments: list[ContextFragment]
    - retrieved_fragments: legacy alias compatible

ContextReceipt:
    - envelope_id: str (hash del envelope)
    - response_content: str
    - model_used: str
    - finish_reason: str
    - usage: dict (input_tokens, output_tokens, total_tokens)
    - latency_ms: float
    - timestamp: str (ISO)

SystemPromptCapsule:
    - sections: dict[str, str] (base, bootstrap, agent_start, bago_mode, active_agent, goal)
    - version: str (BAGO version)
    - render() -> str
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SystemPromptCapsule:
    """Encapsula el system prompt en secciones estructuradas e inmutables.

    Cada sección es independiente y se renderiza en orden fijo.
    La versión permite detectar drift entre sesiones.
    """
    base: str = ""
    bootstrap: str = ""
    agent_start: str = ""
    bago_mode_block: str = ""
    active_agent_block: str = ""
    goal_block: str = ""
    workspace_block: str = ""
    tool_block: str = ""
    session_block: str = ""
    version: str = ""

    def render(self) -> str:
        """Renderiza todas las secciones no vacías separadas por doble newline."""
        parts = [
            self.base,
            self.bootstrap,
            self.agent_start,
            self.bago_mode_block,
            self.active_agent_block,
            self.goal_block,
            self.workspace_block,
            self.tool_block,
            self.session_block,
        ]
        return "\n\n".join(p for p in parts if p and p.strip())


def _stable_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:16]


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _estimate_tokens(text: str) -> int:
    text = text or ""
    return max(len(text) // 4, 1) if text.strip() else 0


@dataclass
class ContextFragment:
    """Unidad atómica de contexto con procedencia y autoridad explícitas."""

    fragment_id: str = ""
    content: str = ""
    summary: str = ""
    source_type: str = ""
    source_uri: str = ""
    scope: str = ""
    authority_level: str = ""
    created_at: str = ""
    retrieved_at: str = ""
    expires_at: str = ""
    content_hash: str = ""
    revision: str = ""
    token_count: int = 0
    sensitivity_level: str = ""
    cache_policy: str = ""
    invalidation_causes: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    authority_score: float = 0.0
    freshness_score: float = 0.0
    estimated_cost: float = 0.0
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    reason_for_inclusion: str = ""
    status: str = "selected"
    metadata: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = str(self.content or "")
        self.summary = str(self.summary or self.content[:240]).strip()
        self.source_type = str(self.source_type or "").strip()
        self.source_uri = str(self.source_uri or "").strip()
        self.scope = str(self.scope or "").strip()
        self.authority_level = str(self.authority_level or "").strip()
        self.created_at = str(self.created_at or "").strip()
        self.retrieved_at = str(self.retrieved_at or "").strip()
        self.expires_at = str(self.expires_at or "").strip()
        self.revision = str(self.revision or "").strip()
        self.sensitivity_level = str(self.sensitivity_level or "").strip()
        self.cache_policy = str(self.cache_policy or "").strip()
        self.reason_for_inclusion = str(self.reason_for_inclusion or "").strip()
        self.status = str(self.status or "selected").strip()
        self.content_hash = str(self.content_hash or _stable_hash(self.content)).strip()
        if not self.fragment_id:
            basis = "|".join([
                self.source_type,
                self.source_uri,
                self.revision,
                self.content_hash,
                self.summary[:80],
            ])
            self.fragment_id = f"frag-{_stable_hash(basis)}"
        if not self.token_count:
            self.token_count = _estimate_tokens(self.content)
        if not self.estimated_cost:
            self.estimated_cost = round(self.token_count * 0.00001, 6)
        self.invalidation_causes = [str(item).strip() for item in _as_list(self.invalidation_causes) if str(item).strip()]
        self.evidence_refs = [dict(item) for item in _as_list(self.evidence_refs) if isinstance(item, dict)]
        self.metadata = dict(self.metadata or {})
        self.extra = dict(self.extra or {})

    @classmethod
    def from_any(
        cls,
        value: Any,
        *,
        source_type: str = "",
        source_uri: str = "",
        scope: str = "",
        authority_level: str = "",
        sensitivity_level: str = "",
        cache_policy: str = "",
        status: str = "selected",
    ) -> "ContextFragment":
        if isinstance(value, cls):
            return value
        data = dict(value or {}) if isinstance(value, dict) else {}
        known_keys = {
            "fragment_id",
            "content",
            "summary",
            "source_type",
            "source_uri",
            "scope",
            "authority_level",
            "created_at",
            "retrieved_at",
            "expires_at",
            "content_hash",
            "revision",
            "token_count",
            "sensitivity_level",
            "cache_policy",
            "invalidation_causes",
            "relevance_score",
            "authority_score",
            "freshness_score",
            "estimated_cost",
            "evidence_refs",
            "reason_for_inclusion",
            "status",
            "metadata",
            "extra",
        }
        extra = {key: value for key, value in data.items() if key not in known_keys}
        content = str(data.get("content", "") or "")
        reason = data.get("reason_for_inclusion", data.get("reason", ""))
        fragment = cls(
            fragment_id=str(data.get("fragment_id") or data.get("id") or ""),
            content=content,
            summary=str(data.get("summary") or content[:240]),
            source_type=str(data.get("source_type") or data.get("source") or source_type or "generated inference"),
            source_uri=str(data.get("source_uri") or data.get("path") or source_uri or ""),
            scope=str(data.get("scope") or scope or ""),
            authority_level=str(data.get("authority_level") or authority_level or ""),
            created_at=str(data.get("created_at") or ""),
            retrieved_at=str(data.get("retrieved_at") or ""),
            expires_at=str(data.get("expires_at") or ""),
            content_hash=str(data.get("content_hash") or ""),
            revision=str(data.get("revision") or data.get("sha256") or data.get("mtime") or ""),
            token_count=int(data.get("token_count") or 0),
            sensitivity_level=str(data.get("sensitivity_level") or sensitivity_level or ""),
            cache_policy=str(data.get("cache_policy") or cache_policy or ""),
            invalidation_causes=list(data.get("invalidation_causes") or []),
            relevance_score=float(data.get("relevance_score", data.get("score", 0.0)) or 0.0),
            authority_score=float(data.get("authority_score", 0.0) or 0.0),
            freshness_score=float(data.get("freshness_score", 0.0) or 0.0),
            estimated_cost=float(data.get("estimated_cost", 0.0) or 0.0),
            evidence_refs=[dict(item) for item in _as_list(data.get("evidence_refs")) if isinstance(item, dict)],
            reason_for_inclusion=str(reason or ""),
            status=str(data.get("status") or status or "selected"),
            metadata=dict(data.get("metadata") or {}),
            extra=extra,
        )
        return fragment

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "fragment_id": self.fragment_id,
            "content": self.content,
            "summary": self.summary,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "scope": self.scope,
            "authority_level": self.authority_level,
            "created_at": self.created_at,
            "retrieved_at": self.retrieved_at,
            "expires_at": self.expires_at,
            "content_hash": self.content_hash,
            "revision": self.revision,
            "token_count": self.token_count,
            "sensitivity_level": self.sensitivity_level,
            "cache_policy": self.cache_policy,
            "invalidation_causes": list(self.invalidation_causes),
            "relevance_score": self.relevance_score,
            "authority_score": self.authority_score,
            "freshness_score": self.freshness_score,
            "estimated_cost": self.estimated_cost,
            "evidence_refs": list(self.evidence_refs),
            "reason_for_inclusion": self.reason_for_inclusion,
            "status": self.status,
            "metadata": dict(self.metadata),
        }
        payload.update(dict(self.extra))
        return payload


@dataclass
class ContextEnvelope:
    """Estructura inmutable del contexto enviado al adapter de provider.

    Reemplaza la concatenación ad-hoc de system_prompt + messages + tools
    que vivía dentro de SessionManager.send().
    """
    # CANON[CTX-001]: every model call must carry the active workspace and session authorities.
    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    framework_root: str = ""
    project_root: str = ""
    workspace_id: str = ""
    workspace_state_root: str = ""
    workspace_scope_root: str = ""
    source_of_truth_version: str = "gabo-workspace-v1"  # CANON[CTX-002]
    context_revision: str = ""
    authorized_root: str = ""
    objective: str = ""
    decisions: list[dict[str, Any]] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    provider: str = ""
    adapter: str = ""
    runtime: str = ""
    model: str = ""
    mode: str = ""
    request_id: str = ""
    workspace: str = ""
    repository: str = ""
    branch: str = ""
    revision: str = ""
    interpreted_intent: str = ""
    risk_level: str = ""
    reserved_output_tokens: int = 0
    fragments: list[ContextFragment] = field(default_factory=list)
    selected_file: str = ""
    open_files: list[str] = field(default_factory=list)
    retrieved_fragments: list[dict[str, Any]] = field(default_factory=list)
    files_represented: list[str] = field(default_factory=list)
    tools_available: list[str] = field(default_factory=list)
    tools_authorized: list[str] = field(default_factory=list)
    security_constraints: list[str] = field(default_factory=list)
    detected_contradictions: list[dict[str, Any]] = field(default_factory=list)
    unresolved_assumptions: list[str] = field(default_factory=list)
    assembly_strategy: dict[str, Any] = field(default_factory=dict)
    creation_timestamp: str = ""
    model_provider: str = ""
    model_name: str = ""
    token_budget: dict[str, Any] = field(default_factory=dict)
    session_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        fragments = [ContextFragment.from_any(fragment) for fragment in self.fragments]
        if not fragments and self.retrieved_fragments:
            fragments = [ContextFragment.from_any(fragment) for fragment in self.retrieved_fragments]
        self.fragments = fragments
        self.retrieved_fragments = [fragment.to_dict() for fragment in fragments]
        self.open_files = list(dict.fromkeys(str(item) for item in self.open_files if str(item).strip()))
        self.files_represented = list(dict.fromkeys(str(item) for item in self.files_represented if str(item).strip()))
        self.tools_available = list(dict.fromkeys(str(item) for item in self.tools_available if str(item).strip()))
        self.tools_authorized = list(dict.fromkeys(str(item) for item in self.tools_authorized if str(item).strip()))
        self.security_constraints = [str(item).strip() for item in _as_list(self.security_constraints) if str(item).strip()]
        self.unresolved_assumptions = [str(item).strip() for item in _as_list(self.unresolved_assumptions) if str(item).strip()]
        self.detected_contradictions = [dict(item) for item in _as_list(self.detected_contradictions) if isinstance(item, dict)]
        self.assembly_strategy = dict(self.assembly_strategy or {})
        self.token_budget = dict(self.token_budget or {})
        self.session_summary = dict(self.session_summary or {})
        self.creation_timestamp = str(self.creation_timestamp or "").strip()
        if not self.reserved_output_tokens:
            self.reserved_output_tokens = int(self.token_budget.get("tokens_reserved", 0) or 0)
        if self.request_id and not self.metadata.get("request_id"):
            self.metadata["request_id"] = self.request_id
        if self.creation_timestamp and not self.metadata.get("creation_timestamp"):
            self.metadata["creation_timestamp"] = self.creation_timestamp

    def _hash_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fragments"] = [fragment.to_dict() for fragment in self.fragments]
        payload["retrieved_fragments"] = [fragment.to_dict() for fragment in self.fragments]
        return payload

    def envelope_id(self) -> str:
        """Hash determinista del envelope para trazabilidad."""
        payload = json.dumps(self._hash_payload(), sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        payload = self._hash_payload()
        payload["envelope_id"] = self.envelope_id()
        return payload


@dataclass
class ContextReceipt:
    """Recibo de la ejecución de un ContextEnvelope contra un provider.

    Captura qué salió, cuánto costó (tokens), cuánto tardó, y por qué terminó.
    """
    envelope_id: str
    response_content: str
    model_used: str
    finish_reason: str
    usage: dict[str, int]
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    session_id: str = ""
    framework_root: str = ""
    project_root: str = ""
    workspace_id: str = ""
    workspace_used: str = ""
    workspace_state_root: str = ""
    workspace_scope_root: str = ""
    context_revision: str = ""
    provider_used: str = ""
    adapter_used: str = ""
    runtime_used: str = ""
    tokens_sent: int = 0
    tokens_reserved: int = 0
    considered_fragments: list[dict[str, Any]] = field(default_factory=list)
    accepted_fragments: list[dict[str, Any]] = field(default_factory=list)
    rejected_fragments: list[dict[str, Any]] = field(default_factory=list)
    deduplicated_fragments: list[dict[str, Any]] = field(default_factory=list)
    compressed_fragments: list[dict[str, Any]] = field(default_factory=list)
    files_represented: list[str] = field(default_factory=list)
    fragments_recovered: list[dict[str, Any]] = field(default_factory=list)
    retrieval_queries: list[dict[str, Any]] = field(default_factory=list)
    retrieval_results: list[dict[str, Any]] = field(default_factory=list)
    cache_hits: list[dict[str, Any]] = field(default_factory=list)
    cache_misses: list[dict[str, Any]] = field(default_factory=list)
    invalidation_causes: list[str] = field(default_factory=list)
    latency_by_source_ms: dict[str, float] = field(default_factory=dict)
    tokens_by_source: dict[str, int] = field(default_factory=dict)
    cost_by_source: dict[str, float] = field(default_factory=dict)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    assumptions_used: list[str] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    evidence_by_assertion: list[dict[str, Any]] = field(default_factory=list)
    tools_executed: list[dict[str, Any]] = field(default_factory=list)
    changes_made: list[dict[str, Any]] = field(default_factory=list)
    tests_executed: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    verification_state: str = ""
    errors: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    session_summary_loaded: dict[str, Any] = field(default_factory=dict)
    tools_available: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limiting_factor: str = ""

    @classmethod
    def from_response(
        cls,
        envelope: ContextEnvelope,
        response_content: str,
        model_used: str,
        finish_reason: str,
        usage_input: int,
        usage_output: int,
        usage_total: int,
        latency_ms: float,
        extra_metadata: dict[str, Any] | None = None,
        context_details: dict[str, Any] | None = None,
    ) -> "ContextReceipt":
        meta = dict(extra_metadata or {})
        meta["envelope_system_length"] = len(envelope.system_prompt)
        meta["envelope_messages_count"] = len(envelope.messages)
        details = dict(context_details or {})
        fragments = list(details.get("fragments") or envelope.fragments or [])
        files_represented = list(details.get("files_represented") or envelope.files_represented)
        fragments_recovered = list(details.get("fragments_recovered") or envelope.retrieved_fragments or fragments)
        session_summary = dict(details.get("session_summary_loaded") or envelope.session_summary)
        tools_available = list(details.get("tools_available") or envelope.tools_available)
        warnings = list(details.get("warnings") or [])
        result = dict(details.get("result") or {})
        # CANON[CTX-003]: receipts must store effective values, not just requested ones.
        return cls(
            envelope_id=envelope.envelope_id(),
            response_content=response_content,
            model_used=model_used,
            finish_reason=finish_reason,
            usage={
                "input_tokens": usage_input,
                "output_tokens": usage_output,
                "total_tokens": usage_total,
            },
            latency_ms=latency_ms,
            metadata=meta,
            request_id=str(details.get("request_id", envelope.request_id) or envelope.metadata.get("request_id", "") or ""),
            session_id=str(details.get("session_id", envelope.session_id) or ""),
            framework_root=str(details.get("framework_root", envelope.framework_root) or ""),
            project_root=str(details.get("project_root", envelope.project_root) or ""),
            workspace_id=str(details.get("workspace_id", envelope.workspace_id) or ""),
            workspace_used=details.get("workspace_used", envelope.project_root or envelope.workspace_state_root),
            workspace_state_root=str(details.get("workspace_state_root", envelope.workspace_state_root) or ""),
            workspace_scope_root=str(details.get("workspace_scope_root", envelope.workspace_scope_root) or ""),
            context_revision=str(details.get("context_revision", envelope.context_revision or envelope.metadata.get("context_revision", "")) or ""),
            provider_used=str(details.get("provider_used", envelope.provider) or envelope.model_provider),
            adapter_used=str(details.get("adapter_used", envelope.adapter) or ""),
            runtime_used=str(details.get("runtime_used", envelope.runtime) or ""),
            tokens_sent=int(details.get("tokens_sent", usage_total) or usage_total),
            tokens_reserved=int(details.get("tokens_reserved", envelope.token_budget.get("tokens_reserved", 0)) or envelope.token_budget.get("tokens_reserved", 0) or 0),
            considered_fragments=list(details.get("considered_fragments") or fragments_recovered or fragments),
            accepted_fragments=list(details.get("accepted_fragments") or fragments),
            rejected_fragments=list(details.get("rejected_fragments") or []),
            deduplicated_fragments=list(details.get("deduplicated_fragments") or []),
            compressed_fragments=list(details.get("compressed_fragments") or []),
            files_represented=files_represented,
            fragments_recovered=fragments_recovered,
            retrieval_queries=list(details.get("retrieval_queries") or []),
            retrieval_results=list(details.get("retrieval_results") or []),
            cache_hits=list(details.get("cache_hits") or []),
            cache_misses=list(details.get("cache_misses") or []),
            invalidation_causes=list(details.get("invalidation_causes") or []),
            latency_by_source_ms=dict(details.get("latency_by_source_ms") or {}),
            tokens_by_source=dict(details.get("tokens_by_source") or {}),
            cost_by_source=dict(details.get("cost_by_source") or {}),
            contradictions=list(details.get("contradictions") or envelope.detected_contradictions or []),
            assumptions_used=list(details.get("assumptions_used") or envelope.unresolved_assumptions or []),
            assertions=list(details.get("assertions") or []),
            evidence_by_assertion=list(details.get("evidence_by_assertion") or []),
            tools_executed=list(details.get("tools_executed") or []),
            changes_made=list(details.get("changes_made") or []),
            tests_executed=list(details.get("tests_executed") or []),
            result=result,
            verification_state=str(details.get("verification_state", "") or ""),
            errors=list(details.get("errors") or []),
            limitations=list(details.get("limitations") or []),
            session_summary_loaded=session_summary,
            tools_available=tools_available,
            warnings=warnings,
            limiting_factor=str(details.get("limiting_factor", envelope.token_budget.get("limiting_factor", "")) or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "response_content": self.response_content,
            "model_used": self.model_used,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "framework_root": self.framework_root,
            "project_root": self.project_root,
            "workspace_id": self.workspace_id,
            "workspace_used": self.workspace_used,
            "workspace_state_root": self.workspace_state_root,
            "workspace_scope_root": self.workspace_scope_root,
            "context_revision": self.context_revision,
            "provider_used": self.provider_used,
            "adapter_used": self.adapter_used,
            "runtime_used": self.runtime_used,
            "tokens_sent": self.tokens_sent,
            "tokens_reserved": self.tokens_reserved,
            "considered_fragments": self.considered_fragments,
            "accepted_fragments": self.accepted_fragments,
            "rejected_fragments": self.rejected_fragments,
            "deduplicated_fragments": self.deduplicated_fragments,
            "compressed_fragments": self.compressed_fragments,
            "files_represented": self.files_represented,
            "fragments_recovered": self.fragments_recovered,
            "retrieval_queries": self.retrieval_queries,
            "retrieval_results": self.retrieval_results,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "invalidation_causes": self.invalidation_causes,
            "latency_by_source_ms": self.latency_by_source_ms,
            "tokens_by_source": self.tokens_by_source,
            "cost_by_source": self.cost_by_source,
            "contradictions": self.contradictions,
            "assumptions_used": self.assumptions_used,
            "assertions": self.assertions,
            "evidence_by_assertion": self.evidence_by_assertion,
            "tools_executed": self.tools_executed,
            "changes_made": self.changes_made,
            "tests_executed": self.tests_executed,
            "result": self.result,
            "verification_state": self.verification_state,
            "errors": self.errors,
            "limitations": self.limitations,
            "session_summary_loaded": self.session_summary_loaded,
            "tools_available": self.tools_available,
            "warnings": self.warnings,
            "limiting_factor": self.limiting_factor,
        }
