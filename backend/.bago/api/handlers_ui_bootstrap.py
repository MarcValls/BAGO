"""handlers_ui_bootstrap.py - GET /api/v1/ui/bootstrap for modern clients."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build"}


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _session_payload(mgr: Any) -> dict[str, Any]:
    status = mgr.status()
    workspace_state = status.get("workspace_state") or getattr(mgr, "workspace_state", lambda: {})()
    welcome_state = status.get("welcome_state") or getattr(mgr, "welcome_state", lambda: {})()
    menu_state = status.get("menu_state") or getattr(mgr, "menu_state", lambda: {})()
    cfg = getattr(mgr, "config", None)
    tool_calling = cfg.get("features.tool_calling", False) if cfg else False
    catalog_mode = cfg.get("model_catalog.mode", "all") if cfg else "all"
    return {
        "contract_version": status.get("contract_version", "bago.contract.ui.v1"),
        "session_id": getattr(mgr, "session_id", "?"),
        "provider": getattr(mgr, "provider", "?"),
        "model": getattr(mgr, "model", "?"),
        "status": status,
        "workspace_state": workspace_state,
        "welcome_state": welcome_state,
        "menu_state": menu_state,
        "binding": {
            "workspace_state_root": workspace_state.get("workspace_state_root", status.get("workspace_state_root", "")),
            "workspace_scope_root": workspace_state.get("workspace_scope_root", status.get("workspace_scope_root", "")),
            "workspace_mirror_root": workspace_state.get("workspace_mirror_root", status.get("workspace_mirror_root", "")),
            "workspace_context_root": status.get("workspace_context_root", ""),
            "workspace_id": workspace_state.get("workspace_id", status.get("workspace_id", "")),
            "authorized_root": status.get("authorized_root", ""),
            "repo_root": status.get("repo_root", ""),
            "repo_branch": status.get("repo_branch", ""),
            "objective": status.get("objective", ""),
            "context_revision": status.get("context_revision", ""),
            "binding_confirmed": workspace_state.get("binding_confirmed", status.get("binding_confirmed", False)),
            "binding_reason": workspace_state.get("binding_reason", status.get("binding_reason", "")),
        },
        "active_agent": status.get("active_agent", "main"),
        "tool_calling": tool_calling,
        "model_catalog_mode": catalog_mode,
    }


def _files_payload(mgr: Any) -> dict[str, Any]:
    from handlers_files import build_files_payload
    return build_files_payload(mgr)


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from api_routes import all_routes
    from handlers_audit import _bago_audit, _project_audit
    from handlers_evidence import _evidence_items
    from handlers_jobs import _job_list, _scheduled_jobs
    from handlers_jobs import _job_summary
    from handlers_router import _policy_payload
    from handlers_workspace import _workspace_payload

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return

    session_payload = _session_payload(mgr)
    status = session_payload.get("status", {})
    evidence_items = _evidence_items(mgr)
    latest_evidence = evidence_items[0] if evidence_items else {}
    jobs = _job_list(mgr)
    schedule = _scheduled_jobs(mgr)
    workspace = _workspace_payload(mgr)
    jobs_summary = _job_summary(mgr)
    router_policy = _policy_payload(handler)
    audit = {"project": _project_audit(), "bago": _bago_audit(mgr)}
    history_messages = list(getattr(getattr(mgr, "store", None), "get_history", lambda: [])() or [])
    cfg = getattr(mgr, "config", None)
    providers = mgr.available_providers()
    providers_mode = cfg.get("model_catalog.mode", "all") if cfg else "all"

    send_json(handler, 200, {
        "status": status,
        "session": session_payload,
        "providers": {"providers": providers, "mode": providers_mode},
        "menu": session_payload.get("menu_state", {}),
        "routes": {"ok": True, "routes": all_routes(), "count": len(all_routes())},
        "history": {"session_id": getattr(mgr, "session_id", "?"), "messages": history_messages, "count": len(history_messages)},
        "files": _files_payload(mgr),
        "evidence": {"ok": True, "latest": latest_evidence, "items": evidence_items[:20], "count": len(evidence_items)},
        "jobs": {"ok": True, "jobs": jobs, "count": len(jobs)},
        "schedule": {"jobs": schedule},
        "workspace": workspace,
        "jobs_summary": jobs_summary,
        "router_policy": router_policy,
        "audit": audit,
    })
