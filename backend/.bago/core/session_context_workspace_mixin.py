#!/usr/bin/env python3
"""Workspace and prompt helpers for SessionManager context construction."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_envelope import SystemPromptCapsule
from intent_engine import classify_intent
from session_utils import format_rag_context
from version import CURRENT as BAGO_VERSION


def _BAGO_MODES_REF() -> dict[str, str]:
    from session_utils import BAGO_MODES
    return BAGO_MODES


class SessionContextWorkspaceMixin:
    def _tool_names(self) -> list[str]:
        try:
            registry = getattr(self, "tool_registry", None)
            if registry is None:
                return []
            tools = registry.to_openai()
            return [
                str((tool.get("function") or {}).get("name", ""))
                for tool in tools
                if str((tool.get("function") or {}).get("name", "")).strip()
            ]
        except Exception:
            return []

    def _workspace_authority_block(self) -> str:
        project_root = str(getattr(self, "project_root", getattr(self, "base_path", "")))
        workspace_state_root = str(getattr(self, "workspace_state_root", ""))
        workspace_scope_root = str(getattr(self, "workspace_scope_root", project_root))
        workspace_mirror_root = str(getattr(self, "workspace_mirror_root", getattr(self, "base_path", "")))
        workspace_id = str(getattr(self, "workspace_id", ""))
        lines = [
            "AUTORIDADES DE RUTA",
            f"framework_root={getattr(self, 'framework_root', '')}",
            f"project_root={project_root}",
            f"workspace_state_root={workspace_state_root}",
            f"workspace_scope_root={workspace_scope_root}",
            f"workspace_mirror_root={workspace_mirror_root}",
            f"workspace_id={workspace_id}",
            "REGLA DE CONTEXTO",
            "Si el usuario pregunta desde qué directorio trabajas, qué proyecto está activo, cuál es el workspace, o dónde operas, responde con project_root y workspace_state_root de esta sesión.",
            "No contestes con respuestas genéricas sobre no tener directorio si la sesión ya tiene project_root y workspace_state_root.",
            "project_root es el checkout del proyecto; workspace_mirror_root es el worktree operativo; workspace_state_root es el estado portable de la sesión.",
        ]
        project_block = self._active_project_summary_block()
        if project_block:
            lines.extend(["", project_block])
        return "\n".join(lines)

    def _workspace_fallback_reply(self) -> str:
        state = self.workspace_state() if hasattr(self, "workspace_state") else {}
        project_root = str(state.get("project_root") or getattr(self, "project_root", getattr(self, "base_path", "")))
        return f"El proyecto activo es {project_root}."

    def _active_project_summary_block(self) -> str:
        try:
            meta = getattr(self, "store", None).get_meta()
        except Exception:
            meta = {}
        data = dict(meta.get("active_project_analysis") or {})
        root = str(data.get("root") or getattr(self, "project_root", getattr(self, "base_path", "")))
        if not root:
            return ""
        stack = ", ".join(data.get("stack") or []) or "unknown"
        configured = data.get("configured")
        linked = data.get("linked")
        issues = "; ".join(str(item) for item in (data.get("issues") or [])[:3]) or "none"
        suggestions = "; ".join(str(item) for item in (data.get("suggestions") or [])[:4]) or "none"
        return "\n".join([
            "PROYECTO ACTIVO AUDITADO",
            f"root={root}",
            f"configured={configured}",
            f"linked={linked}",
            f"stack={stack}",
            f"issues={issues}",
            f"suggested_checks={suggestions}",
        ])

    def _workspace_question_block(self, user_message: str) -> str:
        state = self.workspace_state() if hasattr(self, "workspace_state") else {}
        project_root = str(state.get("project_root") or getattr(self, "project_root", getattr(self, "base_path", "")))
        workspace_state_root = str(state.get("workspace_state_root") or getattr(self, "workspace_state_root", ""))
        return "\n".join([
            "PREGUNTA SOBRE EL PROYECTO ACTIVO",
            f"user_question={user_message}",
            f"answer_project_root={project_root}",
            f"answer_workspace_state_root={workspace_state_root}",
            "Responde como el modelo de chat, en una frase natural y breve, usando esos valores exactos.",
        ])

    def _workspace_answer_mentions_active_project(self, response: str) -> bool:
        text = (response or "").lower()
        state = self.workspace_state() if hasattr(self, "workspace_state") else {}
        project_root = str(state.get("project_root") or getattr(self, "project_root", getattr(self, "base_path", "")))
        if not project_root:
            return False
        normalized = project_root.lower()
        slash_alt = normalized.replace("\\", "/")
        return normalized in text or slash_alt in text

    def effective_system_prompt(self) -> str:
        adapter_obj = getattr(self, "_adapter", None)
        adapter_name = adapter_obj.__class__.__name__ if adapter_obj is not None else self.provider
        runtime_name = getattr(adapter_obj, "runtime_name", "") or getattr(adapter_obj, "runtime", "") or "unknown"
        bago_mode_block = ""
        mode_desc = ""
        if self.bago_mode and self.bago_mode in _BAGO_MODES_REF():
            mode_desc = _BAGO_MODES_REF()[self.bago_mode]
            bago_mode_block = f"MODO BAGO ACTIVO [{self.bago_mode}]\n{mode_desc}"

        active_agent_block = ""
        agent = getattr(self, "agent_gateway", None)
        if agent and agent.active:
            active_agent = agent.active
            active_agent_block = f"AGENTE ACTIVO [{active_agent.name}]"
            if hasattr(active_agent, "system_prompt") and active_agent.system_prompt:
                active_agent_block += f"\n{active_agent.system_prompt}"

        goal_block = ""
        if self.persistent_goal.strip():
            goal_block = f"OBJETIVO PERSISTENTE\n{self.persistent_goal.strip()}"

        capsule = SystemPromptCapsule(
            base=self.system_prompt.strip(),
            bago_mode_block=bago_mode_block,
            active_agent_block=active_agent_block,
            goal_block=goal_block,
            workspace_block=self._workspace_authority_block() if getattr(self, "base_path", None) else "",
            tool_block="\n".join([
                "HERRAMIENTAS AUTORIZADAS",
                ", ".join(self._tool_names()) if self._tool_names() else "ninguna",
            ]) if self._tool_names() else "",
            session_block="\n".join([
                "SESION ACTIVA",
                f"provider={getattr(self, 'provider', '')}",
                f"adapter={adapter_name}",
                f"runtime={runtime_name}",
                f"model={getattr(self, 'model', '')}",
                f"session_id={getattr(self, 'session_id', '')}",
            ]),
            version=BAGO_VERSION,
        )
        return capsule.render()

    def _gabo_block(self) -> str:
        try:
            return self._gabo.get_prompt_block(max_chars=1200)
        except Exception:
            return ""

    def _get_model_context_tokens(self) -> int:
        try:
            catalog = self.list_model_catalog(self.provider)
            for entry in catalog:
                if entry["id"] == self.model:
                    return entry.get("context_tokens", 4096)
        except Exception:
            pass
        return 4096

    def _workspace_context_pack(self, user_message: str, code_task: Any | None = None, limit: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        classifier = getattr(self, "context_classifier", None)
        planner = getattr(self, "context_planner", None)
        ranker = getattr(self, "context_ranker", None)
        contradiction_detector = getattr(self, "context_contradictions", None)
        classification = classifier.classify(
            user_message,
            intent=classify_intent(user_message),
            workspace_root=str(getattr(self, "base_path", "")),
            risk_hint="high" if code_task is not None else "",
        ) if classifier else None
        available_sources = [
            "canonical_cache",
            "dynamic_retrieval",
            "session_memory",
            "persistent_memory",
            "realtime_tools",
        ]
        plan = planner.plan(
            classification,
            available_sources=available_sources,
            model_context_tokens=self._get_model_context_tokens(),
        ) if planner and classification else {"sources_required": ["dynamic_retrieval", "session_memory"], "order": ["dynamic_retrieval", "session_memory"], "budget_by_source": {}, "cache_policy": {}, "global_review_required": False, "review_reasons": [], "justification": "fallback"}
        plan_data = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
        route_state = self.context_router.route(classification, plan) if getattr(self, "context_router", None) and classification else {"classification": {}, "plan": plan_data, "decisions": []}
        self.last_context_classification = classification.to_dict() if classification else {}
        self.last_context_plan = plan_data
        self.last_context_route = route_state

        fragments: list[dict[str, Any]] = []
        timings: dict[str, float] = {}
        import time

        start = time.perf_counter()
        if "canonical_cache" in plan_data.get("sources_required", []):
            try:
                canon_fragments = self.canon_cache.retrieve(user_message, limit=limit)
                fragments.extend(canon_fragments)
            except Exception:
                canon_fragments = []
            timings["canonical_cache"] = (time.perf_counter() - start) * 1000.0
        start = time.perf_counter()
        if "dynamic_retrieval" in plan_data.get("sources_required", []) or "realtime_tools" in plan_data.get("sources_required", []):
            directory_fragments = self._directory_context_retrieve(user_message, limit=max(limit, 3))
            fragments.extend(directory_fragments)
        else:
            directory_fragments = []
        timings["dynamic_retrieval"] = (time.perf_counter() - start) * 1000.0
        start = time.perf_counter()
        rag_fragments = self._rag_retrieve(user_message, limit=limit, plan=plan)
        fragments.extend(rag_fragments)
        timings["memory_retrieval"] = (time.perf_counter() - start) * 1000.0

        code_context = None
        if code_task is not None and getattr(code_task, "is_code_request", False):
            try:
                from bago_core.codegen.context_builder import build_code_context

                code_context = build_code_context(code_task, workspace_root=self.base_path)
                code_dict = code_context.to_dict()
                code_fragments: list[dict[str, Any]] = []
                for section in ("target_summaries", "related_tests", "similar_files"):
                    for item in code_dict.get(section, []):
                        code_fragments.append({
                            "content": item.get("body", ""),
                            "summary": item.get("body", "")[:240],
                            "source": section,
                            "source_type": "generated inference",
                            "source_uri": item.get("path", ""),
                            "scope": "Project",
                            "authority_level": "medium",
                            "score": 1.0,
                            "path": item.get("path", ""),
                            "exists": item.get("exists", False),
                            "token_count": max(len(item.get("body", "")) // 4, 1),
                            "sensitivity_level": "low",
                            "cache_policy": "session",
                            "reason_for_inclusion": f"code_context:{section}",
                        })
                fragments = (fragments + code_fragments)[: max(limit, 1) * 2]
            except Exception:
                code_context = None

        if ranker is not None:
            ranked = ranker.rank(
                fragments,
                classification=classification,
                objective=user_message,
            )
            fragments = list(ranked["accepted"])[: max(limit, 1) * 4]
            contradictions = contradiction_detector.detect(fragments) if contradiction_detector else {"contradictions": [], "fragments": fragments}
            self.last_context_retrieval = {
                "classification": self.last_context_classification,
                "plan": self.last_context_plan,
                "route": route_state,
                "timings_ms": timings,
                "considered_fragments": ranked["accepted"] + ranked["rejected"] + ranked["deduplicated"],
                "accepted_fragments": ranked["accepted"],
                "rejected_fragments": ranked["rejected"],
                "deduplicated_fragments": ranked["deduplicated"],
                "compressed_fragments": ranked.get("compressed", []),
                "retrieval_queries": [item for item in [
                    {"source": "canonical_cache", "query": user_message} if "canonical_cache" in plan_data.get("sources_required", []) else None,
                    {"source": "dynamic_retrieval", "query": user_message} if directory_fragments else None,
                    {"source": "memory_retrieval", "query": user_message} if rag_fragments else None,
                ] if item is not None],
                "retrieval_results": fragments,
                "cache_hits": [],
                "cache_misses": [],
                "invalidation_causes": [],
                "latency_by_source_ms": timings,
                "tokens_by_source": {
                    item.get("source", item.get("source_type", "")): int(item.get("token_count", 0) or 0)
                    for item in fragments
                },
                "cost_by_source": {
                    item.get("source", item.get("source_type", "")): float(item.get("estimated_cost", 0.0) or 0.0)
                    for item in fragments
                },
                "contradictions": contradictions.get("contradictions", []),
                "assumptions_used": [],
                "assertions": [],
                "evidence_by_assertion": [],
                "tools_executed": [],
                "changes_made": [],
                "tests_executed": [],
                "result": {},
                "verification_state": "pending",
                "errors": [],
                "limitations": [],
            }
        else:
            self.last_context_retrieval = {
                "classification": self.last_context_classification,
                "plan": self.last_context_plan,
                "route": route_state,
                "timings_ms": timings,
                "considered_fragments": list(fragments),
                "accepted_fragments": list(fragments),
                "rejected_fragments": [],
                "deduplicated_fragments": [],
                "compressed_fragments": [],
                "retrieval_queries": [],
                "retrieval_results": list(fragments),
                "cache_hits": [],
                "cache_misses": [],
                "invalidation_causes": [],
                "latency_by_source_ms": timings,
                "tokens_by_source": {
                    item.get("source", item.get("source_type", "")): int(item.get("token_count", 0) or 0)
                    for item in fragments
                },
                "cost_by_source": {
                    item.get("source", item.get("source_type", "")): float(item.get("estimated_cost", 0.0) or 0.0)
                    for item in fragments
                },
                "contradictions": contradiction_detector.detect(fragments).get("contradictions", []) if contradiction_detector else [],
                "assumptions_used": [],
                "assertions": [],
                "evidence_by_assertion": [],
                "tools_executed": [],
                "changes_made": [],
                "tests_executed": [],
                "result": {},
                "verification_state": "pending",
                "errors": [],
                "limitations": [],
            }
        self.last_global_review = getattr(self, "_global_review_state", lambda: {"required": False, "reasons": [], "triggers": []})()
        return fragments, code_context

    def _directory_context_retrieve(self, user_message: str, limit: int = 6) -> list[dict[str, Any]]:
        if not self.config.get("features.workspace_retrieval", True):
            return []
        if not self.config.get("features.directory_context", True):
            return []
        try:
            from directory_context import DirectoryContextEngine
        except Exception:
            return []
        try:
            engine = getattr(self, "directory_context", None)
            if engine is None:
                engine = DirectoryContextEngine(self.base_path)
                self.directory_context = engine
            fragments, _ = engine.retrieve(user_message, limit_files=limit, limit_symbols=limit)
            return list(fragments)
        except Exception:
            return []

    def _workspace_file_retrieve(self, user_message: str, limit: int = 3) -> list[dict[str, Any]]:
        if not self.config.get("features.workspace_retrieval", True):
            return []
        try:
            from directory_context import DirectoryContextEngine
        except Exception:
            return []
        try:
            cached = getattr(self, "last_context_retrieval", {}) or {}
            cached_fragments = cached.get("retrieval_results", []) or []
            if cached_fragments:
                return [frag for frag in cached_fragments if frag.get("source") == "workspace_file"][:limit]
            engine = getattr(self, "directory_context", None)
            if engine is None:
                engine = DirectoryContextEngine(self.base_path)
                self.directory_context = engine
            fragments, _ = engine.retrieve(user_message, limit_files=limit, limit_symbols=limit)
            return [frag for frag in fragments if frag.get("source") == "workspace_file"]
        except Exception:
            return []
