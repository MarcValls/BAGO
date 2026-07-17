#!/usr/bin/env python3
"""Policy, retrieval and classifier helpers for SessionManager context."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_utils import format_rag_context


class SessionContextPolicyMixin:
    def _bc_policy_block(self, user_message: str) -> str:
        try:
            bago_core = self.base_path / "bago_core"
            if str(bago_core) not in sys.path:
                sys.path.insert(0, str(bago_core))
            from rl_policies import BCPolicy, bc_policy_path, numpy_available, message_features, INTENT_ACTIONS
            if not numpy_available():
                return ""
            path = bc_policy_path(self.base_path)
            if not path.exists():
                return ""
            policy = BCPolicy.load(path)
            features = message_features(user_message)
            predicted = policy.predict(features)
            recommended_intent = INTENT_ACTIONS[predicted] if 0 <= predicted < len(INTENT_ACTIONS) else "unknown"
            return (
                f"ORQUESTADOR BC (política entrenada desde historial)\n"
                f"- Acción recomendada: {recommended_intent}\n"
                f"- Esta es una sugerencia de la política shadow; síguela si es coherente."
            )
        except Exception:
            return ""

    def _train_bc_policy(self) -> dict:
        try:
            bago_core = self.base_path / "bago_core"
            if str(bago_core) not in sys.path:
                sys.path.insert(0, str(bago_core))
            from rl_policies import train_bc_policy, numpy_available

            if not numpy_available():
                return {"ok": False, "reason": "numpy no disponible"}
            report = train_bc_policy(self.base_path, n_actions=4, n_features=4)
            return {"ok": report.get("status") == "trained", **report}
        except Exception as exc:
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    def auto_evolve(self) -> dict:
        try:
            import intent_engine

            message = self.tool_registry.retrain_intents()
            counts = intent_engine.reload_examples()
            result = {
                "ok": True,
                "message": message,
                "counts": counts,
                "total": sum(counts.values()),
            }
            result["bc"] = self._train_bc_policy()
            return result
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Autoevolución no completada: {exc}",
                "responsable": "SessionManager.auto_evolve / ToolRegistry.retrain_intents",
                "causa": f"{type(exc).__name__}: {exc}",
                "prevencion": (
                    "Verificar acceso de lectura a la base de sesiones "
                    "(~/.copilot/session-store.db) y permisos de escritura en "
                    "~/.bago/state/intent_examples.json"
                ),
            }

    def _rag_retrieve(self, user_message: str, limit: int = 3, *, plan: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        fragments: list[dict[str, Any]] = []
        plan_data = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan or {})
        sources_required = {str(item) for item in plan_data.get("sources_required", []) or []}
        include_session_memory = not sources_required or "session_memory" in sources_required
        include_persistent_memory = not sources_required or "persistent_memory" in sources_required
        include_dynamic = not sources_required or "dynamic_retrieval" in sources_required
        include_canon = not sources_required or "canonical_cache" in sources_required or "canon_cache" in sources_required

        if include_session_memory:
            try:
                history = list(self.store.get_history(limit=limit * 2) or [])
                for index, item in enumerate(reversed(history[-limit:]), start=1):
                    content = str(item.get("content", "")).strip()
                    if not content:
                        continue
                    fragments.append({
                        "content": content,
                        "summary": content[:240],
                        "source": "session_memory",
                        "source_type": "session memory",
                        "source_uri": f"session://{self.session_id}/history/{index}",
                        "scope": "Session",
                        "authority_level": "medium",
                        "score": 0.75,
                        "created_at": str(item.get("timestamp", "")),
                        "retrieved_at": str(item.get("timestamp", "")),
                        "revision": str(item.get("timestamp", "")),
                        "token_count": max(len(content) // 4, 1),
                        "sensitivity_level": "medium",
                        "cache_policy": "session",
                        "reason_for_inclusion": "current session history",
                        "evidence_refs": [{"type": "session_message", "timestamp": item.get("timestamp", "")}],
                        "metadata": {"role": item.get("role", ""), "provider": item.get("provider", ""), "model": item.get("model", "")},
                    })
            except Exception:
                pass

        if include_persistent_memory:
            try:
                kw_results = self.knowledge.search(user_message, limit=limit)
                for r in kw_results:
                    content = str(r.get("content", "")).strip()
                    if not content:
                        continue
                    fragments.append({
                        "content": content,
                        "summary": content[:240],
                        "source": "persistent_memory",
                        "source_type": "persistent memory",
                        "source_uri": f"memory://{r.get('id', '')}",
                        "scope": "Project",
                        "authority_level": "medium",
                        "score": 1.0,
                        "memory_id": r.get("id"),
                        "created_at": r.get("created_at", ""),
                        "retrieved_at": r.get("created_at", ""),
                        "revision": str(r.get("id", "")),
                        "token_count": max(len(content) // 4, 1),
                        "sensitivity_level": "low",
                        "cache_policy": "hash",
                        "reason_for_inclusion": "persistent memory search",
                        "evidence_refs": [{"type": "knowledge_base", "memory_id": r.get("id")}],
                        "metadata": {"source_session": r.get("source_session", "")},
                    })
            except Exception:
                pass

            adapter = self._ensure_adapter()
            if adapter.supports_embeddings():
                try:
                    query_vector = adapter.embed([user_message], model=self.model)[0]
                    vec_results = self.embedding_store.search(query_vector=query_vector, limit=limit)
                    for r in vec_results:
                        content = str(r.get("content", "")).strip()
                        if not content:
                            continue
                        fragments.append({
                            "content": content,
                            "summary": content[:240],
                            "source": "persistent_memory",
                            "source_type": "persistent memory",
                            "source_uri": f"embedding://{r.get('memory_id', '')}",
                            "scope": "Project",
                            "authority_level": "medium",
                            "score": float(r.get("score", 0.0) or 0.0),
                            "memory_id": r.get("memory_id"),
                            "created_at": r.get("created_at", ""),
                            "retrieved_at": r.get("created_at", ""),
                            "revision": str(r.get("id", "")),
                            "token_count": max(len(content) // 4, 1),
                            "sensitivity_level": "low",
                            "cache_policy": "hash",
                            "reason_for_inclusion": "embedding search",
                            "evidence_refs": [{"type": "embedding", "memory_id": r.get("memory_id")}],
                            "metadata": {"source_session": r.get("source_session", ""), "provider": r.get("provider", ""), "model": r.get("model", "")},
                        })
                except Exception:
                    pass

        if include_canon and hasattr(self, "canon_cache") and self.canon_cache:
            try:
                fragments.extend(self.canon_cache.retrieve(user_message, limit=limit))
            except Exception:
                pass

        seen: dict[str, dict[str, Any]] = {}
        for frag in fragments:
            key = str(frag.get("content_hash") or frag.get("source_uri") or frag.get("content", "")[:200])
            score = float(frag.get("score", frag.get("relevance_score", 0.0)) or 0.0)
            if key not in seen or score > float(seen[key].get("score", seen[key].get("relevance_score", 0.0)) or 0.0):
                seen[key] = frag
        return list(seen.values())[:limit]

    def _classify_code_request(self, user_message: str):
        try:
            from bago_core.codegen.task_classifier import classify_code_request
        except Exception:
            return None
        try:
            result = classify_code_request(user_message, workspace_root=self.base_path)
            if result is not None and not getattr(result, "is_code_request", False) and not getattr(result, "blocked", False):
                return None
            return result
        except Exception:
            return None

    def _compile_code_task_contract(self, code_task: Any | None, *, objective: str) -> dict[str, Any] | None:
        if code_task is None:
            return None
        try:
            from bago_core.codegen.task_compiler import compile_code_task
        except Exception:
            return None
        try:
            contract = compile_code_task(code_task, objective=objective)
        except Exception:
            return None
        return contract.to_dict() if hasattr(contract, "to_dict") else dict(contract)

    def _tool_calling_enabled(self) -> bool:
        return bool(self.config.get("features.tool_calling", False))
