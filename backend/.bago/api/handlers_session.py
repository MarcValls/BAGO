"""handlers_session.py \u2014 GET /session for the BAGO HTTP bridge.

Returns the current SessionManager's identity (session_id, provider, model,
active agent, tool calling flag, model catalog mode). 503 if no
SessionManager is wired in.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    status = mgr.status()
    workspace_state = status.get("workspace_state") or getattr(mgr, "workspace_state", lambda: {})()
    welcome_state = status.get("welcome_state") or getattr(mgr, "welcome_state", lambda: {})()
    menu_state = status.get("menu_state") or getattr(mgr, "menu_state", lambda: {})()
    cfg = getattr(mgr, "config", None)
    tool_calling = cfg.get("features.tool_calling", False) if cfg else False
    catalog_mode = cfg.get("model_catalog.mode", "all") if cfg else "all"
    send_json(handler, 200, {
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
    })
