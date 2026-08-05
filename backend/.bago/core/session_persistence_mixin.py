#!/usr/bin/env python3
"""session_persistence_mixin.py — Persistence and status mixin for SessionManager.

Extracted from session_manager.py during modularization.
Contains save/load, status, bago_mode/goal setters, agent activation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import state_read_roots

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_utils import ADAPTER_REGISTRY, BAGO_MODES, normalize_bago_mode, normalize_bridges
from state_paths import resolve_state_root
from context_store import ContextStore
from config_manager import ConfigManager
from contract_state import CONTRACT_VERSION, build_menu_state, build_model_catalog_state, build_roadmap_state, build_welcome_state, build_workspace_state
from workspace_binding import resolve_workspace_binding, resolve_framework_root


class SessionPersistenceMixin:
    """Mixin: save/load, status, bago_mode, goal, agent activation."""

    @staticmethod
    def _envelope_payload(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "to_dict"):
            try:
                return dict(value.to_dict())
            except Exception:
                return {}
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _record_backend_activity(self, kind: str, title: str, detail: str = "", *, reset_clock: bool = True) -> dict[str, Any]:
        store = getattr(self, "store", None)
        if store is None or not hasattr(store, "record_backend_event"):
            return {}
        try:
            return store.record_backend_event(kind, title, detail, reset_clock=reset_clock)
        except Exception:
            return {}

    def _git_info(self) -> tuple[str, str]:
        """Return (repo_root, branch) for the current workspace if available."""
        root = str(getattr(self, "project_root", self.base_path))
        try:
            repo_root = subprocess.run(
                ["git", "-C", root, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if repo_root.returncode != 0:
                return "", ""
            branch = subprocess.run(
                ["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return repo_root.stdout.strip(), branch.stdout.strip() if branch.returncode == 0 else ""
        except Exception:
            return "", ""

    def _binding_state(self) -> dict[str, Any]:
        """Return a compact binding verdict for workspace/repo coherence."""
        binding = resolve_workspace_binding(getattr(self, "project_root", self.base_path))
        workspace = Path(binding.project_root).resolve()
        workspace_state_root = Path(binding.workspace_state_root).resolve()
        repo_root, repo_branch = self._git_info()
        repo_path = Path(repo_root).resolve() if repo_root else None
        expected_repo_root = str(getattr(self, "repo_root", "") or "").strip()
        expected_repo_branch = str(getattr(self, "repo_branch", "") or "").strip()
        workspace_exists = workspace.exists()
        framework_root = resolve_framework_root()
        framework_exists = framework_root.exists()
        manifest_exists = bool(binding.manifest_exists)
        repo_exists = repo_path.exists() if repo_path else False
        # CANON[SP-002]: a project is not required to be a git repo. If there is
        # no git repo we treat repo_matches_workspace as True (vacuously) so
        # the binding can confirm. Only when a git repo exists AND it does not
        # point at the workspace do we record a `repo_root mismatch`.
        repo_matches_workspace = bool((not repo_path) or repo_path == workspace)
        expected_root_matches = not expected_repo_root or expected_repo_root == repo_root
        expected_branch_matches = not expected_repo_branch or expected_repo_branch == repo_branch
        workspace_root_ok = workspace_state_root.name == ".gabo"
        scope_ok = Path(getattr(self, "workspace_scope_root", workspace)).resolve() == workspace
        reasons: list[str] = []
        if not workspace_exists:
            reasons.append("workspace missing")
        if not framework_exists:
            reasons.append("framework missing")
        if not manifest_exists:
            reasons.append("manifest missing")
        if not workspace_root_ok:
            reasons.append("workspace root mismatch")
        if not scope_ok:
            reasons.append("scope mismatch")
        if expected_repo_root and not expected_root_matches:
            reasons.append("persisted repo_root mismatch")
        if expected_repo_branch and not expected_branch_matches:
            reasons.append("persisted repo_branch mismatch")
        if repo_path and not repo_matches_workspace:
            reasons.append("repo_root mismatch")
        # CANON[SP-001]: binding is only confirmed when framework, workspace,
        # scope, manifest, and persisted expectations all agree.
        confirmed = bool(
            workspace_exists
            and framework_exists
            and workspace_root_ok
            and scope_ok
            and manifest_exists
            and expected_root_matches
            and expected_branch_matches
            and repo_matches_workspace
            and not reasons
        )
        reason = "ok" if confirmed else "; ".join(reasons) if reasons else "binding unavailable"
        return {
            "framework_root": str(framework_root),
            "project_root": str(workspace),
            "workspace_state_root": str(workspace_state_root),
            "workspace_scope_root": str(Path(getattr(self, "workspace_scope_root", workspace)).resolve()),
            "workspace_id": str(getattr(self, "workspace_id", binding.workspace_id) or binding.workspace_id),
            "workspace_manifest": str(getattr(self, "workspace_manifest", workspace_state_root / "workspace.json")),
            "workspace_exists": workspace_exists,
            "framework_exists": framework_exists,
            "repo_exists": repo_exists,
            "repo_matches_workspace": repo_matches_workspace,
            "expected_repo_root": expected_repo_root,
            "expected_repo_branch": expected_repo_branch,
            "binding_confirmed": confirmed,
            "binding_reason": reason,
        }

    def _global_review_state(self) -> dict[str, Any]:
        """Return the current review-gating state derived from live context signals."""
        binding = self._binding_state()
        workspace_state = self.workspace_state()
        classification = dict(getattr(self, "last_context_classification", {}) or {})
        plan = dict(getattr(self, "last_context_plan", {}) or {})
        route = dict(getattr(self, "last_context_route", {}) or {})
        retrieval = dict(getattr(self, "last_context_retrieval", {}) or {})
        last_receipt = getattr(self, "last_receipt", None)
        receipt_payload = last_receipt.to_dict() if last_receipt and hasattr(last_receipt, "to_dict") else {}

        reasons: list[str] = []
        triggers: list[dict[str, Any]] = []

        def _add(reason: str, *, source: str, detail: str = "") -> None:
            if reason in reasons:
                return
            reasons.append(reason)
            triggers.append({
                "reason": reason,
                "source": source,
                "detail": detail,
            })

        if not binding.get("binding_confirmed", False):
            _add("binding_unconfirmed", source="binding", detail=str(binding.get("binding_reason", "")))
        if workspace_state.get("workspace_state") != "linked_confirmed":
            _add("workspace_not_linked", source="workspace_state", detail=str(workspace_state.get("workspace_state", "")))
        if plan.get("global_review_required"):
            for item in plan.get("review_reasons", []) or []:
                _add(f"planner:{item}", source="plan", detail=str(plan.get("justification", "")))
        if classification.get("risk") == "high":
            _add("high_risk", source="classification", detail=str(classification.get("intent", "")))
        if classification.get("required_verification_level") == "strict":
            _add("strict_verification", source="classification", detail=str(classification.get("domain", "")))
        if retrieval.get("contradictions"):
            _add("contradictions_detected", source="retrieval", detail=str(len(retrieval.get("contradictions", []))))
        if receipt_payload:
            verification_state = str(receipt_payload.get("verification_state", "")).strip().lower()
            if verification_state in {"unverified", "contradicted", "disputed", "obsolete"}:
                _add("receipt_requires_review", source="receipt", detail=verification_state)
            if receipt_payload.get("errors"):
                _add("receipt_errors", source="receipt", detail=str(len(receipt_payload.get("errors", []))))
            if receipt_payload.get("limitations"):
                _add("receipt_limitations", source="receipt", detail=str(len(receipt_payload.get("limitations", []))))
        if route.get("request_id"):
            route_plan = route.get("plan", {}) if isinstance(route.get("plan", {}), dict) else {}
            if route_plan.get("global_review_required"):
                _add("route_global_review", source="route", detail=str(route.get("request_id", "")))

        return {
            "required": bool(reasons),
            "reasons": reasons,
            "triggers": triggers,
            "binding": binding,
            "workspace_state": workspace_state,
            "classification": classification,
            "plan": plan,
            "route": route,
            "retrieval": retrieval,
            "receipt": receipt_payload,
        }

    def workspace_state(self) -> dict[str, Any]:
        """Return the canonical workspace state DTO."""
        session_workspace_id = str(getattr(self, "workspace_id", "") or "")
        return build_workspace_state(
            getattr(self, "project_root", self.base_path),
            session_id=getattr(self, "session_id", ""),
            workspace_id=session_workspace_id,
            context_revision=getattr(self, "context_revision", ""),
            session_workspace_id=session_workspace_id,
        )

    def welcome_state(self) -> dict[str, Any]:
        """Return the canonical welcome-state DTO."""
        state = self.workspace_state()
        if state["workspace_state"] == "linked_confirmed":
            summary = "Workspace y sesión confirmados"
        elif state["workspace_state"] == "detected_unlinked":
            summary = "Workspace detectado, sesión no vinculada"
        elif state["workspace_state"] == "invalid":
            summary = "Workspace inválido"
        elif state["workspace_state"] == "legacy_only":
            summary = "Workspace legacy detectado"
        elif state["workspace_state"] == "absent":
            summary = "Workspace ausente"
        else:
            summary = "Estado bloqueado"
        return build_welcome_state(state, summary=summary)

    def menu_state(self) -> dict[str, Any]:
        """Return the canonical menu-state DTO."""
        sections = []
        try:
            from commands import MENU_SECTIONS
            sections = list(MENU_SECTIONS)
        except Exception:
            sections = []
        workspace_state = self.workspace_state()
        active_center = "workspace" if workspace_state["workspace_state"] != "linked_confirmed" else "session"
        return build_menu_state(
            workspace_state,
            sections,
            active_center=active_center,
            selected_item="",
        )

    def roadmap_state(self) -> dict[str, Any]:
        """Return the canonical roadmap DTO."""
        return build_roadmap_state()

    def model_catalog_state(self, provider: str | None = None) -> dict[str, Any]:
        """Return the canonical model-catalog DTO."""
        target_provider = provider or self.provider
        catalog = self.list_model_catalog(target_provider)
        return build_model_catalog_state(
            target_provider,
            catalog,
            selected_model=self.model if target_provider == self.provider else "",
            effective_model=self.model if target_provider == self.provider else "",
        )

    def set_bago_mode(self, mode: str) -> dict:
        """Cambia el modo BAGO activo."""
        previous = self.bago_mode
        self.bago_mode = normalize_bago_mode(mode)
        self._record_backend_activity(
            "mode_change",
            f"Cambio de modo: {previous} → {self.bago_mode}",
            detail=BAGO_MODES[self.bago_mode],
        )
        return {
            "ok": True,
            "previous_mode": previous,
            "mode": self.bago_mode,
            "description": BAGO_MODES[self.bago_mode],
        }

    def set_goal(self, goal: str) -> dict:
        """Establece un objetivo persistente para la sesión."""
        previous = self.persistent_goal
        self.persistent_goal = goal.strip()
        return {"ok": True, "goal": self.persistent_goal, "previous_goal": previous}

    def clear_goal(self) -> dict:
        """Limpia el objetivo persistente."""
        previous = self.persistent_goal
        self.persistent_goal = ""
        return {"ok": True, "goal": "", "previous_goal": previous}

    def set_active_bridges(self, providers: list[str]) -> dict:
        """Establece la lista de bridges activos."""
        self.active_bridges = normalize_bridges(providers, primary=self.provider)
        return {"ok": True, "bridges": list(self.active_bridges)}

    def status(self) -> dict:
        """Estado actual de la sesión."""
        adapter = self._ensure_adapter()
        health = adapter.health_check()
        repo_root, repo_branch = self._git_info()
        meta = self.store.get_meta()
        context_revision = getattr(self, "context_revision", "") or meta.get("context_revision", "")
        last_receipt = getattr(self, "last_receipt", None)
        last_envelope = getattr(self, "last_context_envelope", None)
        binding = self._binding_state()
        context_measure = {}
        try:
            context_measure = self.measure_context()
        except Exception:
            context_measure = {
                "ok": False,
                "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
                "provider": self.provider,
                "model": self.model,
            }
        context_benchmark = getattr(self, "last_context_benchmark", None)
        cognitive_benchmark = getattr(self, "last_cognitive_benchmark", None)
        context_certification = getattr(self, "last_context_certification", None)
        global_review = getattr(self, "last_global_review", None) or self._global_review_state()
        self.last_global_review = global_review
        workspace_state = self.workspace_state()
        return {
            "contract_version": CONTRACT_VERSION,
            "session_id": self.session_id,
            "active_conversation_id": self.store.active_conversation_id,
            "conversation_count": len(self.store.list_conversations()),
            "provider": self.provider,
            "model": self.model,
            "default_provider": getattr(getattr(self, "config", None), "default_provider", "ollama-cloud"),
            "tool_approval_policy": str(getattr(self, "tool_approval_policy", lambda: "ask")()),
            "auto_allow_tools": bool(self.config.get("features.auto_allow_tools", False)),
            "framework_root": str(getattr(self, "framework_root", resolve_framework_root())),
            "project_root": str(getattr(self, "project_root", self.base_path)),
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "workspace_scope_root": str(getattr(self, "workspace_scope_root", self.base_path)),
            "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
            "workspace_context_root": str(getattr(self, "workspace_context_root", Path(self.base_path) / ".gabo" / "context")),
            "workspace_mirror_ready": bool(getattr(self, "workspace_mirror_ready", False)),
            "workspace_mirror_error": str(getattr(self, "workspace_mirror_error", "")),
            "workspace_mirror_required_bytes": int(getattr(self, "workspace_mirror_required_bytes", 0) or 0),
            "workspace_mirror_free_bytes": int(getattr(self, "workspace_mirror_free_bytes", 0) or 0),
            "workspace_work_root": str(getattr(self, "workspace_work_root", self.base_path)),
            "workspace_id": str(getattr(self, "workspace_id", "")),
            "workspace_manifest": str(getattr(self, "workspace_manifest", Path(self.base_path) / ".gabo" / "workspace.json")),
            "workspace_manifest_exists": Path(getattr(self, "workspace_manifest", Path(self.base_path) / ".gabo" / "workspace.json")).exists(),
            "authorized_root": str(self.base_path),
            "repo_root": repo_root,
            "repo_branch": repo_branch,
            "bago_mode": self.bago_mode,
            "objective": self.persistent_goal,
            "context_revision": context_revision,
            "binding_confirmed": binding["binding_confirmed"],
            "binding_reason": binding["binding_reason"],
            "active_agent": self.agent_gateway.active.name,
            "active_bridges": list(self.active_bridges),
            "workspace_state": workspace_state,
            "welcome_state": self.welcome_state(),
            "menu_state": self.menu_state(),
            "roadmap": self.roadmap_state(),
            "health": {
                "ok": health.ok,
                "detail": health.detail,
                "latency_ms": health.latency_ms,
            },
            "messages": len(self.store.get_history()),
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "created_at": self.created_at,
            "last_switch_at": self.last_switch_at,
            "switches": len(self.switch_log),
            "backend_clock": {
                "started_at": meta.get("backend_clock_started_at", ""),
                "last_reset_at": meta.get("backend_clock_last_reset_at", ""),
                "last_reason": meta.get("backend_clock_last_reason", ""),
                "last_message": meta.get("backend_clock_last_message", ""),
                "ticks": meta.get("backend_clock_ticks", 0),
            },
            "last_receipt": last_receipt.to_dict() if last_receipt else meta.get("last_receipt", {}),
            "last_envelope": self._envelope_payload(last_envelope),
            "context_measure": context_measure,
            "context_benchmark": context_benchmark,
            "cognitive_benchmark": cognitive_benchmark,
            "context_certification": context_certification,
            "context_classification": getattr(self, "last_context_classification", {}),
            "context_plan": getattr(self, "last_context_plan", {}),
            "code_task": getattr(self, "last_code_task", {}) or {},
            "code_task_contract": getattr(self, "last_code_task_contract", {}) or {},
            "context_route": getattr(self, "last_context_route", {}),
            "context_retrieval": getattr(self, "last_context_retrieval", {}),
            "global_review": global_review,
            "review_required": bool(global_review.get("required")),
            "review_reasons": list(global_review.get("reasons", []) or []),
        }

    def inspect_context(self) -> dict[str, Any]:
        """Devuelve el estado real del contexto con trazabilidad ampliada."""
        snapshot = self.status()
        snapshot["last_envelope"] = self._envelope_payload(getattr(self, "last_context_envelope", None))
        snapshot["last_receipt"] = getattr(self, "last_receipt", None).to_dict() if getattr(self, "last_receipt", None) else snapshot.get("last_receipt", {})
        snapshot["timeline"] = self.store.get_timeline(limit=10)
        snapshot["history"] = self.store.get_history()[-10:]
        snapshot["context_history_count"] = len(self.store.get_history())
        return snapshot

    def context_history(self, limit: int = 10) -> dict[str, Any]:
        """Historial de contexto y timeline para inspeccion/debug."""
        limit = max(1, min(int(limit or 0), 50))
        return {
            "ok": True,
            "session_id": self.session_id,
            "active_conversation_id": self.store.active_conversation_id,
            "conversation_count": len(self.store.list_conversations()),
            "framework_root": str(getattr(self, "framework_root", resolve_framework_root())),
            "project_root": str(getattr(self, "project_root", self.base_path)),
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "workspace_scope_root": str(getattr(self, "workspace_scope_root", self.base_path)),
            "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
            "workspace_id": str(getattr(self, "workspace_id", "")),
            "workspace_state": self.workspace_state(),
            "context_revision": getattr(self, "context_revision", ""),
            "history": self.store.get_history()[-limit:],
            "timeline": self.store.get_timeline(limit=limit),
            "last_receipt": getattr(self, "last_receipt", None).to_dict() if getattr(self, "last_receipt", None) else {},
            "last_envelope": self._envelope_payload(getattr(self, "last_context_envelope", None)),
            "cognitive_benchmark": getattr(self, "last_cognitive_benchmark", None),
        }

    def invalidate_context(self, reason: str = "") -> dict[str, Any]:
        """Invalida la certificación activa sin tocar el historial de chat."""
        previous = getattr(self, "context_revision", "")
        self.context_revision = ""
        self.last_receipt = None
        self.last_context_envelope = None
        patch = {
            "context_revision": "",
            "last_receipt": {},
            "context_invalidated_at": time.time(),
            "context_invalidated_reason": reason,
        }
        self.store.update_meta(patch)
        return {
            "ok": True,
            "context_revision": "",
            "previous_context_revision": previous,
            "reason": reason,
        }

    def calibrate_context(self, iterations: int = 3) -> dict[str, Any]:
        """Recalibra el contexto con benchmark y medida reales."""
        benchmark = self.benchmark_context(iterations=iterations)
        measure = self.measure_context()
        return {
            "ok": True,
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "provider": self.provider,
            "model": self.model,
            "measure": measure,
            "benchmark": benchmark,
        }

    def benchmark_cognitive(self, iterations: int = 1) -> dict[str, Any]:
        """Ejecuta la batería adversarial cognitiva."""
        return self._benchmark_cognitive(iterations=iterations)

    def tune_context(self, *, authorized: bool = False, patch: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ajuste explícito, bloqueado por defecto."""
        if not authorized:
            return {
                "ok": False,
                "blocked": True,
                "reason": "tune requiere autorización explícita",
                "applied": False,
            }
        patch = patch or {}
        if patch:
            self.store.add_timeline_event(
                TimelineEvent("context", "tune", f"Patch autorizado: {sorted(patch)}")
            )
        return {
            "ok": True,
            "blocked": False,
            "applied": False,
            "message": "tune auditado sin mutación automática",
            "patch": patch,
        }

    def activate_agent(self, name: str) -> dict:
        """Activa un agente especializado.

        Retorna dict con: ok, agent, previous_agent, warnings.
        """
        try:
            previous = self.agent_gateway.active.name
            agent = self.agent_gateway.activate(name)
            warnings: list[str] = []

            if agent.preferred_provider and agent.preferred_provider != self.provider:
                warnings.append(f"Agente '{name}' prefiere provider: {agent.preferred_provider}")
            if agent.preferred_model and agent.preferred_model != self.model:
                warnings.append(f"Agente '{name}' prefiere modelo: {agent.preferred_model}")

            self._record_backend_activity(
                "agent_change",
                f"Agente activado: {previous} → {agent.name}",
                detail="; ".join(warnings) if warnings else "agent change applied",
            )

            return {
                "ok": True,
                "agent": agent.name,
                "previous_agent": previous,
                "warnings": warnings,
            }
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def save(self) -> None:
        """Persiste metadata de sesión en disco y actualiza índice SQLite."""
        meta = self.store.get_meta()
        context_revision = getattr(self, "context_revision", "") or meta.get("context_revision", "")
        repo_root, repo_branch = self._git_info()
        last_receipt = getattr(self, "last_receipt", None)
        last_envelope = getattr(self, "last_context_envelope", None)
        context_benchmark = getattr(self, "last_context_benchmark", None)
        cognitive_benchmark = getattr(self, "last_cognitive_benchmark", None)
        context_certification = getattr(self, "last_context_certification", None)
        context_classification = getattr(self, "last_context_classification", {})
        context_plan = getattr(self, "last_context_plan", {})
        context_route = getattr(self, "last_context_route", {})
        context_retrieval = getattr(self, "last_context_retrieval", {})
        global_review = getattr(self, "last_global_review", {})
        binding = self._binding_state()
        self.store.update_meta({
            "last_provider": self.provider,
            "last_model": self.model,
            "bago_mode": self.bago_mode,
            "active_agent": self.agent_gateway.active.name,
            "active_bridges": list(self.active_bridges),
            "switch_count": self.store.get_meta().get("switch_count", 0),
            "last_switch_at": self.last_switch_at,
            "persistent_goal": self.persistent_goal,
            "context_revision": context_revision,
            "last_receipt": last_receipt.to_dict() if last_receipt else meta.get("last_receipt", {}),
            "last_envelope": self._envelope_payload(last_envelope) or meta.get("last_envelope", {}),
            "context_benchmark": context_benchmark,
            "cognitive_benchmark": cognitive_benchmark,
            "context_certification": context_certification,
            "context_classification": context_classification,
            "context_plan": context_plan,
            "context_route": context_route,
            "context_retrieval": context_retrieval,
            "last_global_review": global_review,
            "binding_confirmed": binding["binding_confirmed"],
            "binding_reason": binding["binding_reason"],
            "framework_root": str(getattr(self, "framework_root", resolve_framework_root())),
            "project_root": str(getattr(self, "project_root", self.base_path)),
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "workspace_scope_root": str(getattr(self, "workspace_scope_root", self.base_path)),
            "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
            "workspace_id": str(getattr(self, "workspace_id", "")),
            "repo_root": repo_root,
            "repo_branch": repo_branch,
        })
        path = self.state_dir / "sessions" / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "active_conversation_id": self.store.active_conversation_id,
            "conversation_count": len(self.store.list_conversations()),
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "bago_mode": self.bago_mode,
            "active_agent": self.agent_gateway.active.name,
            "active_bridges": list(self.active_bridges),
            "created_at": self.created_at,
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "last_switch_at": self.last_switch_at,
            "switch_log": self.switch_log,
            "framework_root": str(getattr(self, "framework_root", resolve_framework_root())),
            "project_root": str(getattr(self, "project_root", self.base_path)),
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "workspace_scope_root": str(getattr(self, "workspace_scope_root", self.base_path)),
            "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
            "workspace_id": str(getattr(self, "workspace_id", "")),
            "authorized_root": str(self.base_path),
            "repo_root": repo_root,
            "repo_branch": repo_branch,
            "persistent_goal": self.persistent_goal,
            "context_revision": context_revision,
            "last_receipt": last_receipt.to_dict() if last_receipt else meta.get("last_receipt", {}),
            "last_envelope": self._envelope_payload(last_envelope) or meta.get("last_envelope", {}),
            "context_benchmark": context_benchmark,
            "cognitive_benchmark": cognitive_benchmark,
            "context_certification": context_certification,
            "context_classification": context_classification,
            "context_plan": context_plan,
            "context_route": context_route,
            "context_retrieval": context_retrieval,
            "binding_confirmed": binding["binding_confirmed"],
            "binding_reason": binding["binding_reason"],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        try:
            from session_db import get_session_db
            db = get_session_db(str(self.state_dir))
            db.upsert(
                self.session_id,
                created_at=datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat(),
                last_provider=self.provider,
                last_model=self.model,
                switch_count=len(self.switch_log),
                bago_mode=self.bago_mode,
                active_agent=self.agent_gateway.active.name,
                total_tokens=self.total_tokens,
                total_calls=self.total_calls,
                last_switch_at=self.last_switch_at.isoformat() if isinstance(self.last_switch_at, float) else self.last_switch_at,
                authorized_root=str(getattr(self, "project_root", self.base_path)),
                context_revision=context_revision,
                context_benchmark=context_benchmark,
                cognitive_benchmark=cognitive_benchmark,
                context_certification=context_certification,
                context_classification=context_classification,
                context_plan=context_plan,
                context_route=context_route,
                context_retrieval=context_retrieval,
                last_global_review=global_review,
                binding_confirmed=binding["binding_confirmed"],
                project_root=str(getattr(self, "project_root", self.base_path)),
                framework_root=str(getattr(self, "framework_root", resolve_framework_root())),
                workspace_state_root=str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
                workspace_scope_root=str(getattr(self, "workspace_scope_root", self.base_path)),
                workspace_mirror_root=str(getattr(self, "workspace_mirror_root", self.base_path)),
                workspace_id=str(getattr(self, "workspace_id", "")),
                repo_root=repo_root,
                repo_branch=repo_branch,
            )
        except Exception:
            pass

    @classmethod
    def load(cls, session_id: str, base_path: str | None = None, state_root: str | None = None) -> "SessionPersistenceMixin":
        """Carga una sesión desde disco."""
        bp = Path(base_path or os.getcwd())
        sr = resolve_state_root(state_root)
        # LEGACY[SP-L001]: legacy roots are discovery-only; loaded sessions
        # continue writing through the canonical state root ``sr``.
        read_roots = [sr]
        if state_root is None or (isinstance(state_root, str) and not state_root.strip()):
            read_roots.extend(state_read_roots())
        read_roots.append(bp / ".bago" / "state")
        read_roots = list(dict.fromkeys(read_roots))
        relative_session = Path("sessions") / f"{session_id}.json"
        path = next(
            (root / relative_session for root in read_roots if (root / relative_session).exists()),
            sr / relative_session,
        )
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            saved_project = data.get("project_root") or data.get("workspace_state_root")
            bp = Path(saved_project) if saved_project and Path(saved_project).exists() else Path(base_path or os.getcwd())
            mgr = cls(
                session_id=data["session_id"],
                provider=data["provider"],
                model=data["model"],
                base_path=str(bp),
                state_root=str(sr),
                system_prompt=data.get("system_prompt", ""),
                bago_mode=data.get("bago_mode", "B"),
                active_agent=data.get("active_agent", "default"),
                active_bridges=data.get("active_bridges"),
            )
            mgr.total_tokens = data.get("total_tokens", 0)
            mgr.total_calls = data.get("total_calls", 0)
            mgr.last_switch_at = data.get("last_switch_at")
            mgr.switch_log = data.get("switch_log", [])
            mgr.persistent_goal = data.get("persistent_goal", "")
            mgr.context_revision = data.get("context_revision", "")
            mgr.last_context_envelope = data.get("last_envelope", {})
            mgr.last_context_benchmark = data.get("context_benchmark")
            mgr.last_cognitive_benchmark = data.get("cognitive_benchmark")
            mgr.last_context_certification = data.get("context_certification")
            mgr.last_context_classification = data.get("context_classification", {})
            mgr.last_context_plan = data.get("context_plan", {})
            mgr.last_context_route = data.get("context_route", {})
            mgr.last_context_retrieval = data.get("context_retrieval", {})
            mgr.last_global_review = data.get("last_global_review", {})
            # CANON[WS-005]: framework_root belongs to the runtime that is
            # loading the session. A persisted value is historical metadata,
            # never authority after moving between source and an installation.
            mgr.framework_root = resolve_framework_root()
            mgr.project_root = data.get("project_root", str(bp))
            mgr.workspace_state_root = data.get("workspace_state_root", str(Path(bp) / ".gabo"))
            mgr.workspace_scope_root = data.get("workspace_scope_root", str(bp))
            mgr.workspace_mirror_root = data.get("workspace_mirror_root", str(getattr(mgr, "base_path", bp)))
            mgr.workspace_work_root = str(getattr(mgr, "base_path", bp))
            mgr.workspace_id = data.get("workspace_id", "")
            mgr.workspace_manifest = Path(mgr.workspace_state_root) / "workspace.json"
            mgr.workspace_binding = resolve_workspace_binding(mgr.project_root).to_dict()
            mgr.workspace_binding["workspace_id"] = mgr.workspace_id or mgr.workspace_binding.get("workspace_id", "")
            mgr.repo_root = data.get("repo_root", "")
            mgr.repo_branch = data.get("repo_branch", "")
            return mgr

        store_base = next(
            (
                root
                for root in read_roots
                if (root / "sessions" / session_id).is_dir()
            ),
            sr,
        )
        store = ContextStore.load(session_id, base_dir=store_base)
        if store_base.resolve() != sr.resolve():
            # Legacy roots are read-only discovery sources. Hydrate a canonical
            # store before handing it to the manager so future writes stay in sr.
            canonical_store = ContextStore.load(session_id, base_dir=sr)
            if not canonical_store.get_history() and store.get_history():
                canonical_store._messages = store.get_raw_messages()
                canonical_store._timeline = store._timeline
                canonical_store._tokens = store._tokens
                canonical_store._meta = store.get_meta()
                canonical_store._context_path.write_text(
                    "\n".join(json.dumps(item.to_dict(), ensure_ascii=False) for item in canonical_store._messages) + ("\n" if canonical_store._messages else ""),
                    encoding="utf-8",
                )
                canonical_store._timeline_path.write_text(
                    "\n".join(json.dumps(item.to_dict(), ensure_ascii=False) for item in canonical_store._timeline) + ("\n" if canonical_store._timeline else ""),
                    encoding="utf-8",
                )
                canonical_store._save_tokens()
                canonical_store._save_meta()
            store = canonical_store
        meta = store.get_meta()
        saved_project = meta.get("project_root") or meta.get("workspace_state_root")
        bp = Path(saved_project) if saved_project and Path(saved_project).exists() else Path(base_path or os.getcwd())
        defaults = ConfigManager(base_path=str(bp), state_root=str(sr))
        provider = meta.get("last_provider") or defaults.default_provider
        model = meta.get("last_model") or defaults.default_model
        mgr = cls(
            session_id=session_id,
            provider=provider,
            model=model,
            base_path=str(bp),
            state_root=str(sr),
            system_prompt=meta.get("system_prompt", ""),
            bago_mode=meta.get("bago_mode", "B"),
            active_agent=meta.get("active_agent", "default"),
            active_bridges=meta.get("active_bridges"),
        )
        mgr.store = store
        token_summary = store.get_token_summary()
        mgr.total_tokens = sum(
            int(model_data.get("in", 0)) + int(model_data.get("out", 0))
            for provider_data in token_summary.values()
            for model_data in provider_data.values()
        )
        mgr.total_calls = sum(
            int(model_data.get("calls", 0))
            for provider_data in token_summary.values()
            for model_data in provider_data.values()
        )
        mgr.last_switch_at = meta.get("last_switch_at")
        mgr.switch_log = meta.get("switch_log", [])
        mgr.persistent_goal = meta.get("persistent_goal", "")
        mgr.context_revision = meta.get("context_revision", "")
        mgr.last_context_envelope = meta.get("last_envelope", {})
        mgr.last_context_benchmark = meta.get("context_benchmark")
        mgr.last_cognitive_benchmark = meta.get("cognitive_benchmark")
        mgr.last_context_certification = meta.get("context_certification")
        mgr.last_context_classification = meta.get("context_classification", {})
        mgr.last_context_plan = meta.get("context_plan", {})
        mgr.last_context_route = meta.get("context_route", {})
        mgr.last_context_retrieval = meta.get("context_retrieval", {})
        mgr.last_global_review = meta.get("last_global_review", {})
        # CANON[WS-005]: legacy directory sessions follow the same runtime
        # authority rule as JSON sessions.
        mgr.framework_root = resolve_framework_root()
        mgr.project_root = meta.get("project_root", str(bp))
        mgr.workspace_state_root = meta.get("workspace_state_root", str(Path(bp) / ".gabo"))
        mgr.workspace_scope_root = meta.get("workspace_scope_root", str(bp))
        mgr.workspace_mirror_root = meta.get("workspace_mirror_root", str(getattr(mgr, "base_path", bp)))
        mgr.workspace_work_root = str(getattr(mgr, "base_path", bp))
        mgr.workspace_id = meta.get("workspace_id", "")
        mgr.workspace_manifest = Path(mgr.workspace_state_root) / "workspace.json"
        mgr.workspace_binding = resolve_workspace_binding(mgr.project_root).to_dict()
        mgr.workspace_binding["workspace_id"] = mgr.workspace_id or mgr.workspace_binding.get("workspace_id", "")
        mgr.repo_root = meta.get("repo_root", "")
        mgr.repo_branch = meta.get("repo_branch", "")
        return mgr

    def close(self) -> None:
        """Cierra conexiones abiertas (Knowledge Base, etc.)."""
        if hasattr(self, "knowledge") and self.knowledge:
            self.knowledge.close()
        if hasattr(self, "embedding_store") and self.embedding_store:
            self.embedding_store.close()
