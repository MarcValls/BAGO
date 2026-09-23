"""handlers_workspace.py - Workspace authority endpoints for BAGO."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _workspace_payload(mgr: Any, status: dict[str, Any] | None = None) -> dict[str, Any]:
    status = status if status is not None else mgr.status()
    workspace_state = status.get("workspace_state") or getattr(mgr, "workspace_state", lambda: {})()
    welcome_state = status.get("welcome_state") or getattr(mgr, "welcome_state", lambda: {})()
    menu_state = status.get("menu_state") or getattr(mgr, "menu_state", lambda: {})()
    cfg = getattr(mgr, "config", None)
    tool_calling = cfg.get("features.tool_calling", False) if cfg else False
    catalog_mode = cfg.get("model_catalog.mode", "all") if cfg else "all"
    binding_confirmed = bool(workspace_state.get("binding_confirmed", status.get("binding_confirmed", False)))
    workspace_state_name = str(workspace_state.get("workspace_state", status.get("workspace_state", ""))).lower()
    manifest_state = str(workspace_state.get("manifest_status", workspace_state.get("manifest_state", ""))).lower()
    workspace_root = workspace_state.get("workspace_state_root", status.get("workspace_state_root", ""))
    project_root = workspace_state.get("project_root", status.get("project_root", ""))
    workspace_scope_root = workspace_state.get("workspace_scope_root", status.get("workspace_scope_root", ""))
    binding = {
        "framework_root": status.get("framework_root", ""),
        "project_root": project_root,
        "workspace_root": workspace_root,
        "workspace_state_root": workspace_root,
        "workspace_scope_root": workspace_scope_root,
        "workspace_mirror_root": workspace_state.get("workspace_mirror_root", status.get("workspace_mirror_root", "")),
        "workspace_context_root": status.get("workspace_context_root", ""),
        "workspace_id": workspace_state.get("workspace_id", status.get("workspace_id", "")),
        "authorized_root": status.get("authorized_root", ""),
        "repo_root": status.get("repo_root", ""),
        "repo_branch": status.get("repo_branch", ""),
        "objective": status.get("objective", ""),
        "context_revision": status.get("context_revision", ""),
        "binding_confirmed": binding_confirmed,
        "binding_reason": workspace_state.get("binding_reason", status.get("binding_reason", "")),
    }
    context_measure = status.get("context_measure") or {}
    context_certification = status.get("context_certification") or {}
    context_state = str(
        context_measure.get("state")
        or workspace_state.get("context_state")
        or (context_certification.get("status", "") if isinstance(context_certification, dict) else "")
    ).lower()
    if context_measure.get("ok") is True and not context_state:
        context_state = "confirmed"
    needs_seed = (
        not binding_confirmed
        or manifest_state in {"missing", "invalid"}
        or workspace_state_name in {"invalid", "missing", "absent", "legacy_only"}
    )
    can_chat = bool(
        status.get("provider")
        and status.get("model")
        and binding_confirmed
        and workspace_state_name == "linked_confirmed"
        and context_state in {"confirmed", "partial", ""}
    )
    can_initialize = workspace_state_name in {"absent", "missing"}
    can_link = workspace_state_name == "detected_unlinked"
    can_repair = workspace_state_name in {"invalid", "legacy_only"}
    can_seed = workspace_state_name in {"absent", "detected_unlinked", "invalid", "legacy_only"} or bool(workspace_root)
    allowed_actions = list(workspace_state.get("allowed_actions") or workspace_state.get("acciones_permitidas") or [])
    blocked_actions = list(workspace_state.get("blocked_operations") or workspace_state.get("operaciones_bloqueadas") or [])
    recommended_actions = list(welcome_state.get("recommended_actions") or allowed_actions[:4])
    permissions = {
        "canChat": can_chat,
        "canInitializeWorkspace": can_initialize,
        "canLinkWorkspace": can_link,
        "canRepairWorkspace": can_repair,
        "canSeedWorkspace": can_seed,
        "canRunTools": bool(binding_confirmed and tool_calling),
        "canInspectContext": bool(binding_confirmed and (binding["context_revision"] or status.get("last_receipt"))),
        "canViewEvidence": bool(status.get("last_receipt") or status.get("context_revision")),
    }
    return {
        "ok": True,
        "contract_version": status.get("contract_version", "bago.contract.ui.v1"),
        "session_id": getattr(mgr, "session_id", "?"),
        "provider": getattr(mgr, "provider", "?"),
        "model": getattr(mgr, "model", "?"),
        # The interactive client scopes conversations to the user project,
        # never to its internal .gabo state directory.
        "root": project_root,
        "state_root": workspace_root,
        "scope_root": workspace_scope_root,
        "status": status,
        "workspace_state": workspace_state,
        "welcome_state": welcome_state,
        "menu_state": menu_state,
        "binding": binding,
        "permissions": permissions,
        "allowed_actions": allowed_actions,
        "blocked_actions": blocked_actions,
        "recommended_actions": recommended_actions,
        "recommendations": recommended_actions,
        "blocked_operations": blocked_actions,
        "summary": {
            "state": workspace_state_name or "unknown",
            "manifest_exists": bool(workspace_state.get("manifest_exists", False)),
            "binding_confirmed": binding_confirmed,
            "binding_reason": str(binding["binding_reason"] or ""),
        },
        "model_catalog_mode": catalog_mode,
        "tool_calling": tool_calling,
        "seed_suggested": needs_seed,
        "seed_reason": "workspace no validado" if needs_seed else "",
    }


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    send_json(handler, 200, _workspace_payload(mgr))


def handle_persist(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /workspace/persist — challenge/approve/execute ``workspace.bind``.

    The handler only constructs the exact request and delegates the compound
    bind/save/last-workspace effect to the server-owned gateway adapter.
    """
    from api_serializers import send_json
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_gateway import (
        ExecutionContext,
        ExecutionGateway,
        ExecutionGatewayError,
        WorkspaceBindEffectAdapter,
    )
    from execution_request import ExecutionRequestError, build_execution_request

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {
            "ok": False,
            "error_code": "SESSION_MANAGER_MISSING",
            "message": "SessionManager no disponible",
        })
        return

    path = ""
    if isinstance(body, dict):
        path = str(body.get("path", "")).strip()
    if not path:
        # CANON[WS-002]: project_root es el path del workspace del usuario.
        path = str(getattr(mgr, "project_root", "") or "").strip()
    if not path:
        send_json(handler, 400, {
            "ok": False,
            "error_code": "MISSING_WORKSPACE_PATH",
            "message": "No se pudo determinar el workspace activo",
        })
        return

    try:
        # Pure preflight only.  The adapter repeats this check immediately
        # before rebind, after the Permit has been consumed.
        workspace_path = WorkspaceBindEffectAdapter.validate_target(mgr, path)
        binding = WorkspaceBindEffectAdapter.binding_descriptor(workspace_path)
        request = build_execution_request(
            effect_id="workspace.bind",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(mgr, "session_id", "") or ""),
            source_surface="api.workspace.persist",
            target={
                "path": str(workspace_path),
                "resource": "session_workspace",
                "operation": "persist",
                "workspace_id": str(binding["workspace_id"]),
                "workspace_scope_root": str(binding["workspace_scope_root"]),
                "workspace_state_root": str(binding["workspace_state_root"]),
                "binding_digest": WorkspaceBindEffectAdapter.binding_descriptor_digest(binding),
            },
            arguments={},
            scope="workspace",
        )
        boundary = AuthorizationBoundary()
        payload = dict(body or {})
        action = str(payload.get("authorization_action") or "").strip().lower()
        interaction_id = str(payload.get("interaction_id") or "").strip()

        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {
                "ok": True,
                "authorization": {"state": "challenge", "challenge": challenge},
            })
            return

        if action == "approve":
            if str(payload.get("user_decision") or "").strip().lower() != "approve":
                raise AuthorizationError(
                    "La decisión explícita del usuario debe ser approve",
                    code="authorization_user_decision_required",
                )
            headers = getattr(handler, "headers", {}) or {}
            channel = headers.get("X-Bago-Channel", "") if hasattr(headers, "get") else ""
            authorization = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""),
                interaction_id=interaction_id,
                session_id=request.session_id,
                channel=channel,
            )
            send_json(handler, 200, {
                "ok": True,
                "authorization": {"state": "authorized", **authorization},
            })
            return

        if action not in {"", "execute"}:
            raise AuthorizationError(
                "authorization_action must be challenge, approve or execute",
                code="authorization_action_invalid",
            )

        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request,
            context=ExecutionContext(manager=mgr),
        )
        response = dict(result) if isinstance(result, dict) else {"result": result}
        response["authorization"] = {
            "state": "consumed",
            "permit_id": authorization.get("permit_id"),
            "decision_id": authorization.get("decision_id"),
            "proof_id": authorization.get("proof_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 200 if bool(response.get("ok")) else 409, response)
    except AuthorizationError as exc:
        status = 409 if exc.code in {
            "authorization_challenge_not_found",
            "authorization_challenge_not_pending",
            "authorization_challenge_expired",
            "authorization_permit_replay",
            "authorization_permit_expired",
            "authorization_operation_mismatch",
        } else 403
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        material_failure = {
            "workspace_bind_rebind_failed",
            "workspace_bind_save_failed",
            "workspace_bind_last_path_failed",
        }
        target_failure = {
            "workspace_bind_authorization_required",
            "workspace_bind_path_required",
            "workspace_bind_path_absolute_required",
            "workspace_bind_target_invalid",
            "workspace_bind_validator_missing",
            "workspace_bind_resource_invalid",
            "workspace_bind_operation_invalid",
            "workspace_bind_rebind_unavailable",
            "workspace_bind_save_unavailable",
            "workspace_bind_binding_digest_required",
            "workspace_bind_binding_changed",
            "workspace_bind_identity_changed",
            "workspace_bind_scope_changed",
        }
        status = 500 if exc.code in material_failure else 403 if exc.code in target_failure else 409
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    """GET /workspace/list — lista workspaces disponibles.

    Lee de ~/.bago/last_workspace.json + workspaces registrados en el
    base_path y devuelve la lista. Para v1, devuelve solo el último + el
    base_path actual.
    """
    from api_serializers import send_json
    import json as _json
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 1) Workspace actual
    mgr = _mgr(handler)
    if mgr is not None:
        # CANON[WS-002]: project_root es el path del workspace del usuario,
        # no el base_path que puede ser un dir temporal del bridge.
        current = str(getattr(mgr, "project_root", "") or getattr(mgr, "base_path", "")).strip()
        if current and current not in seen:
            out.append({
                "path": current,
                "id": str(getattr(mgr, "workspace_id", "")),
                "name": Path(current).name or current,
                "is_current": True,
                "binding_confirmed": bool(getattr(mgr, "workspace_state", lambda: {})().get("binding_confirmed", False)),
            })
            seen.add(current)

    # 2) Último workspace persistido
    last_ws = Path.home() / ".bago" / "last_workspace.json"
    if last_ws.exists():
        try:
            payload = _json.loads(last_ws.read_text(encoding="utf-8"))
            last_path = str(payload.get("path", "")).strip()
            if last_path and last_path not in seen and Path(last_path).is_dir():
                out.append({
                    "path": last_path,
                    "id": "",
                    "name": Path(last_path).name or last_path,
                    "is_current": False,
                    "binding_confirmed": False,
                })
                seen.add(last_path)
        except (OSError, _json.JSONDecodeError):
            pass

    send_json(handler, 200, {"ok": True, "workspaces": out, "count": len(out)})


def _is_loopback_request(handler: "BaseHTTPRequestHandler") -> bool:
    """Fail closed: filesystem browsing is only exposed to the local UI bridge."""
    from ipaddress import ip_address

    try:
        address = ip_address(str(handler.client_address[0]))
        if address.is_loopback:
            return True
        return bool(address.version == 6 and address.ipv4_mapped and address.ipv4_mapped.is_loopback)
    except (AttributeError, IndexError, TypeError, ValueError):
        return False


def _browse_roots() -> list[dict[str, str]]:
    import os
    import string

    candidates: list[Path] = [Path.home()]
    if os.name == "nt":
        candidates.extend(Path(f"{letter}:\\") for letter in string.ascii_uppercase)
    else:
        candidates.append(Path("/"))

    roots: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
            key = str(resolved).casefold()
            if not resolved.is_dir() or key in seen:
                continue
            seen.add(key)
            roots.append({"label": "Inicio" if candidate == Path.home() else str(resolved), "path": str(resolved)})
        except OSError:
            continue
    return roots


def _browse_breadcrumbs(path: Path) -> list[dict[str, str]]:
    parts = list(path.parts)
    if not parts:
        return [{"label": str(path), "path": str(path)}]
    crumbs: list[dict[str, str]] = []
    current = Path(parts[0])
    crumbs.append({"label": parts[0], "path": str(current)})
    for part in parts[1:]:
        current = current / part
        crumbs.append({"label": part, "path": str(current)})
    return crumbs


def _recent_workspace_locations(mgr: Any) -> list[dict[str, str]]:
    import json

    candidates = [str(getattr(mgr, "project_root", "") or getattr(mgr, "base_path", "")).strip()] if mgr else []
    last_ws = Path.home() / ".bago" / "last_workspace.json"
    if last_ws.exists():
        try:
            candidates.append(str(json.loads(last_ws.read_text(encoding="utf-8")).get("path", "")).strip())
        except (OSError, json.JSONDecodeError):
            pass
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in candidates:
        try:
            path = Path(raw).expanduser().resolve()
            key = str(path).casefold()
            if not raw or key in seen or not path.is_dir():
                continue
            seen.add(key)
            result.append({"label": path.name or str(path), "path": str(path)})
        except OSError:
            continue
    return result


def handle_browse(handler: "BaseHTTPRequestHandler") -> None:
    """GET /workspace/browse?path=... — local, read-only directory browser."""
    import os
    from api_serializers import send_json

    if not _is_loopback_request(handler):
        send_json(handler, 403, {"ok": False, "error": "Explorador disponible solo desde el equipo local", "error_code": "workspace_browse_local_only"})
        return

    mgr = _mgr(handler)
    query = parse_qs(urlparse(handler.path).query)
    raw_path = str((query.get("path") or [""])[0]).strip()
    fallback = str(getattr(mgr, "project_root", "") or getattr(mgr, "base_path", "")).strip() if mgr else ""
    try:
        current = Path(raw_path or fallback or Path.home()).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        send_json(handler, 400, {"ok": False, "error": "Ruta no válida", "error_code": "workspace_browse_invalid_path"})
        return
    if not current.is_dir():
        send_json(handler, 404, {"ok": False, "error": f"Directorio no encontrado: {current}", "error_code": "workspace_browse_not_found"})
        return

    directories: list[dict[str, str]] = []
    try:
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.name.startswith(".") or entry.is_symlink():
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        directories.append({"name": entry.name, "path": str(Path(entry.path).resolve())})
                except OSError:
                    continue
    except OSError as exc:
        send_json(handler, 403, {"ok": False, "error": f"No se puede leer el directorio: {exc}", "error_code": "workspace_browse_unreadable"})
        return

    directories.sort(key=lambda item: item["name"].casefold())
    parent = current.parent
    send_json(handler, 200, {
        "ok": True,
        "path": str(current),
        "parent": "" if parent == current else str(parent),
        "roots": _browse_roots(),
        "recent": _recent_workspace_locations(mgr),
        "breadcrumbs": _browse_breadcrumbs(current),
        "directories": directories[:500],
        "truncated": len(directories) > 500,
    })
