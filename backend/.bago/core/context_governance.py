#!/usr/bin/env python3
"""context_governance.py — source routing, ranking, claims and canon cache.

This module extends the existing BAGO context pipeline without replacing the
current SessionManager orchestration. It provides typed helpers for
classification, source planning, fragment ranking, contradiction detection,
claim verification, and a small canonical cache.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from context_envelope import ContextFragment

try:
    from intent_engine import classify_intent
except Exception:  # pragma: no cover - keeps the module usable in isolation.
    classify_intent = None  # type: ignore[assignment]


def _stable_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:16]


def _estimate_tokens(text: str) -> int:
    text = text or ""
    return max(len(text) // 4, 1) if text.strip() else 0


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass(slots=True)
class ContextClassification:
    intent: str
    domain: str
    risk: str
    required_context_scopes: list[str] = field(default_factory=list)
    required_verification_level: str = "standard"
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "domain": self.domain,
            "risk": self.risk,
            "required_context_scopes": list(self.required_context_scopes),
            "required_verification_level": self.required_verification_level,
            "signals": dict(self.signals),
        }


@dataclass(slots=True)
class ContextPlan:
    sources_required: list[str] = field(default_factory=list)
    order: list[str] = field(default_factory=list)
    budget_by_source: dict[str, int] = field(default_factory=dict)
    cache_policy: dict[str, str] = field(default_factory=dict)
    global_review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    justification: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources_required": list(self.sources_required),
            "order": list(self.order),
            "budget_by_source": dict(self.budget_by_source),
            "cache_policy": dict(self.cache_policy),
            "global_review_required": self.global_review_required,
            "review_reasons": list(self.review_reasons),
            "justification": self.justification,
        }


class ContextClassifier:
    """Classify request intent, domain and risk."""

    _CANON_TERMS = {"canon", "canonico", "contract", "contrato", "política", "politica", "schema", "esquema", "regla"}
    _MEMORY_TERMS = {"memoria", "record", "recuerdo", "sesion", "session", "decisión", "decision", "episodio", "historial", "anterior"}
    _RUNTIME_TERMS = {"git", "branch", "rama", "status", "diff", "cambio", "modificado", "fs", "filesystem", "archivo", "process", "servicio", "tool"}

    def classify(
        self,
        user_message: str,
        *,
        intent: str | None = None,
        workspace_root: str = "",
        risk_hint: str = "",
    ) -> ContextClassification:
        text = (user_message or "").strip()
        lowered = text.lower()
        base_intent = (intent or "").strip() or self._classify_intent(text)
        domain = "bago-session"
        scopes = {"Session"}
        risk = risk_hint.strip() or "normal"
        verification = "standard"

        if any(term in lowered for term in self._CANON_TERMS):
            scopes.add("Canonical")
            domain = "canon"
            risk = "high" if risk == "normal" else risk
            verification = "strict"
        if any(term in lowered for term in self._RUNTIME_TERMS):
            scopes.update({"Project", "Realtime", "Local"})
            domain = "runtime"
            risk = "high"
            verification = "strict"
        if any(term in lowered for term in self._MEMORY_TERMS):
            scopes.update({"Session", "Project"})
            domain = "memory"
        if any(term in lowered for term in ("external", "internet", "web", "docs", "documentación", "documentacion")):
            scopes.add("External")
            risk = "high"
            verification = "strict"
        if workspace_root:
            scopes.add("Project")

        return ContextClassification(
            intent=base_intent,
            domain=domain,
            risk=risk,
            required_context_scopes=sorted(scopes),
            required_verification_level=verification,
            signals={
                "workspace_root": workspace_root,
                "user_message_length": len(text),
            },
        )

    def _classify_intent(self, text: str) -> str:
        if classify_intent is None:
            return "chat"
        try:
            return str(classify_intent(text) or "chat")
        except Exception:
            return "chat"


class ContextPlanner:
    """Decide which sources to consult and in what order."""

    def plan(
        self,
        classification: ContextClassification,
        *,
        available_sources: Iterable[str] | None = None,
        model_context_tokens: int = 4096,
        current_output_reserve: int = 1024,
    ) -> ContextPlan:
        available = list(dict.fromkeys(str(item) for item in (available_sources or [])))
        intent = classification.intent
        source_order: list[str] = []
        sources_required: list[str] = []
        cache_policy: dict[str, str] = {}
        budget_by_source: dict[str, int] = {}
        review_reasons: list[str] = []

        def require(source: str, *, policy: str = "revalidate", weight: float = 1.0) -> None:
            if source not in sources_required and (not available or source in available):
                sources_required.append(source)
            if source not in source_order:
                source_order.append(source)
            cache_policy[source] = policy
            budget_by_source[source] = max(int((model_context_tokens - current_output_reserve) * weight), 64)

        if intent in {"work", "review", "execute"} or classification.domain in {"runtime", "canon"} or classification.risk == "high":
            require("dynamic_retrieval", policy="hash", weight=0.30)
        if intent in {"work", "review", "execute"}:
            require("realtime_tools", policy="no_cache", weight=0.20)
        if classification.domain in {"canon", "memory"} or classification.required_verification_level == "strict":
            require("canonical_cache", policy="hash+version", weight=0.20)
        if classification.domain in {"memory", "runtime"} or intent in {"chat", "review"}:
            require("session_memory", policy="session", weight=0.15)
            require("persistent_memory", policy="hash", weight=0.10)
        if "External" in classification.required_context_scopes:
            require("external_docs", policy="revalidate", weight=0.05)

        if classification.risk == "high":
            review_reasons.append("high_risk")
        if classification.required_verification_level == "strict":
            review_reasons.append("strict_verification")
        if "Canonical" in classification.required_context_scopes and "dynamic_retrieval" in sources_required:
            review_reasons.append("canonical_dynamic_mix")

        if not source_order:
            source_order = ["session_memory"]

        justification = ", ".join([
            f"intent={intent}",
            f"domain={classification.domain}",
            f"risk={classification.risk}",
        ])
        return ContextPlan(
            sources_required=sources_required,
            order=source_order,
            budget_by_source=budget_by_source,
            cache_policy=cache_policy,
            global_review_required=bool(review_reasons),
            review_reasons=review_reasons,
            justification=justification,
        )


class ContextSourceRouter:
    """Justify source selection for a context plan."""

    def route(self, classification: ContextClassification, plan: ContextPlan) -> dict[str, Any]:
        request_id = f"req-{_stable_hash('|'.join([
            classification.intent,
            classification.domain,
            classification.risk,
            plan.justification,
            ','.join(plan.sources_required),
        ]))}"
        decisions: list[dict[str, Any]] = []
        for source in plan.order:
            if source == "canonical_cache":
                reason = "stable canon and contracts"
            elif source == "dynamic_retrieval":
                reason = "mutable workspace state and diffs"
            elif source == "session_memory":
                reason = "current session state"
            elif source == "persistent_memory":
                reason = "persisted memories and episodes"
            elif source == "realtime_tools":
                reason = "live filesystem/git/tool state"
            else:
                reason = "requested by planner"
            decisions.append({
                "source": source,
                "reason": reason,
                "budget_tokens": plan.budget_by_source.get(source, 0),
                "cache_policy": plan.cache_policy.get(source, ""),
            })
        return {
            "request_id": request_id,
            "classification": classification.to_dict(),
            "plan": plan.to_dict(),
            "decisions": decisions,
        }


class TokenBudgeter:
    """Allocate measured tokens across context sections."""

    def allocate(
        self,
        *,
        model_context_tokens: int,
        output_reserve: int,
        instruction_tokens: int = 0,
        objective_tokens: int = 0,
        local_context_tokens: int = 0,
        global_context_tokens: int = 0,
        tool_tokens: int = 0,
        verification_tokens: int = 0,
    ) -> dict[str, Any]:
        input_budget = max(model_context_tokens - output_reserve, 512)
        reserved = {
            "instructions": max(instruction_tokens, 64),
            "objective": max(objective_tokens, 32),
            "local_context": max(local_context_tokens, 96),
            "global_context": max(global_context_tokens, 64),
            "tools": max(tool_tokens, 64),
            "verification": max(verification_tokens, 64),
        }
        used = sum(reserved.values())
        overflow = max(used - input_budget, 0)
        return {
            "model_context_tokens": model_context_tokens,
            "output_reserve": output_reserve,
            "input_budget": input_budget,
            "reserved": reserved,
            "estimated_reserved_total": used,
            "overflow": overflow,
            "available_tokens": max(input_budget - used, 0),
        }


class ContextRanker:
    """Score and deduplicate fragments without allowing low-authority overrides."""

    _MIN_AUTHORITY = {
        "Canonical": 0.85,
        "Project": 0.50,
        "Session": 0.25,
        "Realtime": 0.70,
        "External": 0.75,
    }

    def rank(
        self,
        fragments: Iterable[Any],
        *,
        classification: ContextClassification | None = None,
        objective: str = "",
    ) -> dict[str, Any]:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        deduplicated: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        seen_uri: set[str] = set()
        objective_terms = {item.lower() for item in re.findall(r"[A-Za-z_][\w./:-]*", objective or "")}
        for raw in fragments:
            fragment = ContextFragment.from_any(raw)
            score = self._score(fragment, objective_terms)
            authority_floor = self._MIN_AUTHORITY.get(fragment.scope or fragment.source_type, 0.40)
            if fragment.authority_score and fragment.authority_score < authority_floor:
                fragment.status = "rejected"
                rejected.append(fragment.to_dict())
                continue
            if fragment.content_hash in seen_hashes or (fragment.source_uri and fragment.source_uri in seen_uri):
                fragment.status = "deduplicated"
                deduplicated.append(fragment.to_dict())
                continue
            fragment.relevance_score = max(fragment.relevance_score, score)
            fragment.authority_score = fragment.authority_score or self._authority_score(fragment)
            fragment.freshness_score = fragment.freshness_score or self._freshness_score(fragment)
            fragment.estimated_cost = fragment.estimated_cost or round(fragment.token_count * 0.00001, 6)
            fragment.status = "accepted"
            accepted.append(fragment.to_dict())
            seen_hashes.add(fragment.content_hash)
            if fragment.source_uri:
                seen_uri.add(fragment.source_uri)

        accepted.sort(key=lambda item: (
            -(item.get("authority_score", 0.0) or 0.0),
            -(item.get("freshness_score", 0.0) or 0.0),
            -(item.get("relevance_score", 0.0) or 0.0),
            item.get("source_uri", ""),
        ))
        return {
            "accepted": accepted,
            "rejected": rejected,
            "deduplicated": deduplicated,
            "compressed": [],
        }

    def _score(self, fragment: ContextFragment, objective_terms: set[str]) -> float:
        text = " ".join([fragment.summary, fragment.content[:1000], fragment.reason_for_inclusion]).lower()
        matches = sum(1 for term in objective_terms if term and term in text)
        source_bonus = {
            "Canonical": 0.25,
            "Project": 0.18,
            "Session": 0.10,
            "Realtime": 0.22,
            "External": 0.16,
        }.get(fragment.scope or fragment.source_type, 0.08)
        return min(1.0, matches * 0.12 + source_bonus + (fragment.relevance_score or 0.0))

    def _authority_score(self, fragment: ContextFragment) -> float:
        base = {
            "Canonical": 0.95,
            "Project": 0.75,
            "Session": 0.55,
            "Realtime": 0.85,
            "External": 0.60,
        }.get(fragment.scope or fragment.source_type, 0.50)
        if fragment.sensitivity_level in {"high", "secret"}:
            base -= 0.10
        return max(min(base, 1.0), 0.0)

    def _freshness_score(self, fragment: ContextFragment) -> float:
        if fragment.retrieved_at:
            return 1.0
        if fragment.created_at:
            return 0.75
        return 0.50


class ContradictionDetector:
    """Detect obvious duplicates and source conflicts."""

    def detect(self, fragments: Iterable[Any]) -> dict[str, Any]:
        by_hash: dict[str, list[dict[str, Any]]] = {}
        by_uri: dict[str, list[dict[str, Any]]] = {}
        contradictions: list[dict[str, Any]] = []
        normalized: list[dict[str, Any]] = []
        for raw in fragments:
            fragment = ContextFragment.from_any(raw).to_dict()
            normalized.append(fragment)
            by_hash.setdefault(fragment["content_hash"], []).append(fragment)
            if fragment.get("source_uri"):
                by_uri.setdefault(fragment["source_uri"], []).append(fragment)

        for content_hash, items in by_hash.items():
            if len(items) > 1:
                contradictions.append({
                    "kind": "duplicate",
                    "content_hash": content_hash,
                    "count": len(items),
                    "fragment_ids": [item.get("fragment_id", "") for item in items],
                })

        for source_uri, items in by_uri.items():
            if len(items) <= 1:
                continue
            hashes = {item.get("content_hash", "") for item in items}
            if len(hashes) > 1:
                contradictions.append({
                    "kind": "source_conflict",
                    "source_uri": source_uri,
                    "count": len(items),
                    "content_hashes": sorted(hashes),
                })

        return {
            "contradictions": contradictions,
            "fragments": normalized,
            "has_contradictions": bool(contradictions),
        }


class ClaimVerifier:
    """Verify claims only when evidence exists."""

    def verify(
        self,
        claims: Iterable[Any] | None,
        *,
        evidence: Iterable[Any] | None = None,
        response_text: str = "",
    ) -> dict[str, Any]:
        evidence_items = [ContextFragment.from_any(item).to_dict() for item in (evidence or [])]
        evidence_hashes = {item.get("content_hash", "") for item in evidence_items if item.get("content_hash")}
        verified: list[dict[str, Any]] = []
        inferred: list[dict[str, Any]] = []
        assumed: list[dict[str, Any]] = []
        unverified: list[dict[str, Any]] = []
        contradicted: list[dict[str, Any]] = []
        disputed: list[dict[str, Any]] = []
        obsolete: list[dict[str, Any]] = []
        undetermined: list[dict[str, Any]] = []

        claim_items: list[dict[str, Any]] = []
        for item in claims or []:
            if isinstance(item, dict):
                claim_items.append(dict(item))
            else:
                claim_items.append({"claim": str(item)})

        for claim in claim_items:
            text = str(claim.get("claim") or claim.get("text") or claim.get("fact") or "").strip()
            claim_evidence = [ref for ref in _as_list(claim.get("evidence_refs")) if isinstance(ref, dict)]
            if not claim_evidence and claim.get("evidence"):
                for ref in _as_list(claim.get("evidence")):
                    if isinstance(ref, dict):
                        claim_evidence.append(ref)
            evidence_hit = bool(claim_evidence) or bool(evidence_items)
            status = str(claim.get("status") or "").strip().lower()
            if status in {"contradicted", "disputed", "obsolete"}:
                target = {"contradicted": contradicted, "disputed": disputed, "obsolete": obsolete}[status]
                target.append({**claim, "status": status, "evidence_refs": claim_evidence})
                continue
            if status == "assumed":
                assumed.append({**claim, "status": "assumed", "evidence_refs": claim_evidence})
                continue
            if status == "inferred":
                inferred.append({**claim, "status": "inferred", "evidence_refs": claim_evidence})
                continue
            if evidence_hit:
                verified.append({
                    **claim,
                    "claim": text,
                    "status": "verified",
                    "evidence_refs": claim_evidence or evidence_items,
                    "verified": True,
                })
            else:
                unverified.append({
                    **claim,
                    "claim": text,
                    "status": "unverified",
                    "verified": False,
                    "evidence_refs": [],
                })

        if not claim_items and response_text.strip():
            undetermined.append({
                "claim": response_text.strip()[:240],
                "status": "undetermined",
                "verified": False,
                "evidence_refs": [],
            })

        return {
            "claims": verified + inferred + assumed + unverified + contradicted + disputed + obsolete + undetermined,
            "verified": verified,
            "inferred": inferred,
            "assumed": assumed,
            "unverified": unverified,
            "contradicted": contradicted,
            "disputed": disputed,
            "obsolete": obsolete,
            "undetermined": undetermined,
            "evidence_items": evidence_items,
            "verified_without_evidence_blocked": [item for item in verified if not item.get("evidence_refs")],
        }


class CanonCache:
    """Hash-checked cache for stable canonical knowledge."""

    DEFAULT_SOURCES = (
        "CANON.MD",
        ".bago/core/task_response_contract.py",
        ".bago/core/workspace_binding.py",
        ".bago/core/context_patterns.py",
    )

    def __init__(self, workspace_root: str | Path, cache_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.cache_root = Path(cache_root).resolve() if cache_root else self.workspace_root / ".gabo" / "context"
        self.cache_path = self.cache_root / "canon_cache.json"

    def retrieve(self, query: str, *, limit: int = 4) -> list[dict[str, Any]]:
        query_terms = [token.lower() for token in re.findall(r"[A-Za-z_][\w./:-]*", query or "") if len(token) >= 3]
        cache = _load_json(self.cache_path, default={"sources": {}, "queries": {}})
        cache_sources = cache.setdefault("sources", {})
        cache_queries = cache.setdefault("queries", {})
        query_key = _stable_hash(query.lower())

        if query_key in cache_queries:
            cached_entry = cache_queries[query_key]
            current_hashes = {}
            for rel_path in self.DEFAULT_SOURCES:
                path = self.workspace_root / rel_path
                if path.exists() and path.is_file():
                    try:
                        current_hashes[rel_path.replace("\\", "/")] = _stable_hash(path.read_text(encoding="utf-8", errors="replace"))
                    except Exception:
                        current_hashes[rel_path.replace("\\", "/")] = ""
            if cached_entry.get("source_hashes", {}) == current_hashes:
                cached_fragments = cached_entry.get("fragments", [])
                if cached_fragments:
                    return [ContextFragment.from_any(item).to_dict() for item in cached_fragments[:limit]]

        fragments: list[ContextFragment] = []
        for rel_path in self.DEFAULT_SOURCES:
            path = self.workspace_root / rel_path
            if not path.exists() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            file_hash = _stable_hash(text)
            source_key = rel_path.replace("\\", "/")
            snippets = self._extract_snippets(path, text, query_terms, limit=limit)
            cache_sources[source_key] = {
                "hash": file_hash,
                "updated_at": time.time(),
            }
            fragments.extend(snippets)

        cache_queries[query_key] = {
            "query": query,
            "fragments": [fragment.to_dict() for fragment in fragments[:limit]],
            "source_hashes": {
                rel_path.replace("\\", "/"): cache_sources.get(rel_path.replace("\\", "/"), {}).get("hash", "")
                for rel_path in self.DEFAULT_SOURCES
            },
            "updated_at": time.time(),
        }
        _write_json(self.cache_path, cache)
        return [fragment.to_dict() for fragment in fragments[:limit]]

    def _extract_snippets(self, path: Path, text: str, query_terms: list[str], *, limit: int = 4) -> list[ContextFragment]:
        lines = text.splitlines()
        matches: list[int] = []
        lowered_lines = [line.lower() for line in lines]
        for index, line in enumerate(lowered_lines, start=1):
            if query_terms and any(term in line for term in query_terms):
                matches.append(index)
        if not matches:
            matches = [1]
        snippets: list[ContextFragment] = []
        for start_line in matches[:limit]:
            start = max(start_line - 2, 1)
            end = min(start_line + 6, len(lines) or 1)
            snippet = "\n".join(lines[start - 1:end])
            snippets.append(ContextFragment(
                content=snippet,
                summary=(lines[start_line - 1].strip() if 0 <= start_line - 1 < len(lines) else path.name)[:240],
                source_type="project canon",
                source_uri=str(path),
                scope="Canonical",
                authority_level="high",
                created_at="",
                retrieved_at=str(time.time()),
                expires_at="",
                revision=_stable_hash(text),
                token_count=_estimate_tokens(snippet),
                sensitivity_level="low",
                cache_policy="hash+version",
                invalidation_causes=["content_hash", "version", "policy", "contract"],
                relevance_score=0.9,
                authority_score=0.98,
                freshness_score=0.9,
                estimated_cost=round(_estimate_tokens(snippet) * 0.00001, 6),
                evidence_refs=[{"type": "source_file", "path": str(path)}],
                reason_for_inclusion=f"canonical source: {path.name}",
                status="selected",
                metadata={"query_terms": list(query_terms)},
            ))
        return snippets
