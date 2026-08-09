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


def _workspace_payload(mgr: Any) -> dict[str, Any]:
    status = mgr.status()
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


def _save_last_workspace(path: str) -> None:
    """Guarda el path del workspace activo en ~/.bago/last_workspace.json"""
    import json
    try:
        target = Path.home() / ".bago" / "last_workspace.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"path": str(path)}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except OSError:
        pass


def _persist_workspace(mgr: Any, path: str) -> dict[str, Any]:
    """Persist and activate a workspace path for the current session."""
    if not path:
        return {"ok": False, "error": "no se pudo determinar path"}

    workspace_path = Path(path).expanduser().resolve()
    if not workspace_path.exists():
        return {"ok": False, "error": f"Ruta no existe: {workspace_path}"}

    rebinding_error = ""
    rebind = getattr(mgr, "rebind_project_root", None)
    if callable(rebind):
        try:
            rebind(workspace_path)
        except Exception as exc:
            return {"ok": False, "error": f"No se pudo activar el workspace {workspace_path}: {exc}"}
    else:
        rebinding_error = "SessionManager no expone rebind_project_root()"

    _save_last_workspace(str(workspace_path))
    payload: dict[str, Any] = {"ok": True, "saved": str(workspace_path)}
    if rebinding_error:
        payload["warning"] = rebinding_error
    return payload


def handle_persist(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /workspace/persist — guarda el path actual como último workspace.

    Body: {"path": "..."} (opcional; si no se pasa, usa el base_path del mgr)
    """
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    path = ""
    if isinstance(body, dict):
        path = str(body.get("path", "")).strip()
    if not path:
        # CANON[WS-002]: project_root es el path del workspace del usuario.
        path = str(getattr(mgr, "project_root", "") or getattr(mgr, "base_path", ""))
    result = _persist_workspace(mgr, path)
    send_json(handler, 200 if result.get("ok") else 400, result)


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
