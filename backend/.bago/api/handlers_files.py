"""handlers_files.py \u2014 file listing + read endpoints for the BAGO HTTP bridge.

GET /files/list              \u2014 walk the project's base_path
GET /files/read/<path>       \u2014 read a single file (UTF-8 with replace)

Both endpoints are sandboxed to `session_mgr.base_path`; the read
endpoint rejects any path that escapes that root.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlparse

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".venv", "venv", "target", ".idea", ".vscode",
    ".gradle", "vendor", ".mypy_cache", ".pytest_cache", ".next",
    ".nuxt", ".svelte-kit", ".cache", ".parcel-cache", "coverage",
}
_SOURCE_KEY_RE = re.compile(r"[^a-z0-9]+")


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def _project_root(mgr) -> Path:
    return Path(getattr(mgr, "project_root", getattr(mgr, "base_path", Path.cwd()))).resolve()


def _workspace_root(mgr) -> Path:
    return Path(getattr(mgr, "workspace_mirror_root", getattr(mgr, "base_path", Path.cwd()))).resolve()


def _slugify(value: str) -> str:
    clean = _SOURCE_KEY_RE.sub("-", value.strip().lower()).strip("-")
    return clean or "source"


def _source_key(key: str | None, label: str, path: Path, existing: set[str]) -> str:
    base = _slugify(key or label or path.name)
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}-{index}"
        index += 1
    existing.add(candidate)
    return candidate


def _resolve_source_path(raw: str, base: Path) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def _configured_source_roots(mgr) -> list[dict[str, str]]:
    cfg = getattr(mgr, "config", None)
    if cfg is None:
        return []
    roots = []
    try:
        roots = cfg.read_roots() if hasattr(cfg, "read_roots") else list(cfg.get("sources.read_roots", []) or [])
    except Exception:
        roots = []
    if not isinstance(roots, list):
        return []

    base = _project_root(mgr)
    seen_paths: set[str] = set()
    seen_keys: set[str] = {"workspace"}
    entries: list[dict[str, str]] = []
    for index, raw in enumerate(roots):
        if isinstance(raw, str):
            path_text = raw
            label = Path(raw).name or f"source-{index + 1}"
            key = ""
        elif isinstance(raw, dict):
            path_text = str(raw.get("path") or raw.get("root") or "").strip()
            label = str(raw.get("label") or raw.get("name") or "").strip() or Path(path_text).name or f"source-{index + 1}"
            key = str(raw.get("key") or "").strip()
        else:
            continue
        if not path_text:
            continue
        try:
            resolved = _resolve_source_path(path_text, base)
        except Exception:
            continue
        if not resolved.exists() or not resolved.is_dir():
            continue
        resolved_text = str(resolved)
        if resolved_text in seen_paths:
            continue
        seen_paths.add(resolved_text)
        source_key = _source_key(key, label, resolved, seen_keys)
        entries.append({
            "key": source_key,
            "label": label,
            "path": resolved_text,
            "kind": "source",
            "read_only": "true",
        })
    return entries


def _all_read_roots(mgr) -> list[dict[str, str]]:
    workspace = _workspace_root(mgr)
    roots = [{
        "key": "workspace",
        "label": "Workspace",
        "path": str(workspace),
        "kind": "workspace",
        "read_only": "false",
    }]
    roots.extend(_configured_source_roots(mgr))
    return roots


def _relative_name(root: Path, target: Path) -> str:
    try:
        rel = target.relative_to(root)
    except ValueError:
        return ""
    rel_text = str(rel).replace("\\", "/")
    return "" if rel_text == "." else rel_text


def _namespaced_path(source_key: str, relative: str) -> str:
    return source_key if not relative else f"{source_key}/{relative}"


def _resolve_namespaced_target(mgr, raw_path: str) -> tuple[Path, str]:
    clean = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    roots = _all_read_roots(mgr)
    if not clean:
        return _workspace_root(mgr), ""
    parts = clean.split("/", 1)
    if len(parts) == 2 and parts[0] in {root["key"] for root in roots}:
        root = next(root for root in roots if root["key"] == parts[0])
        return Path(root["path"]).resolve(), parts[1]
    # Backward compatible: resolve against workspace first, then extra roots.
    workspace = Path(roots[0]["path"]).resolve()
    candidate = (workspace / clean).resolve()
    try:
        candidate.relative_to(workspace)
        if candidate.exists():
            return workspace, clean
    except Exception:
        pass
    for root in roots[1:]:
        base = Path(root["path"]).resolve()
        candidate = (base / clean).resolve()
        try:
            candidate.relative_to(base)
            if candidate.exists():
                return base, clean
        except Exception:
            continue
    return workspace, clean


def _file_entries_for_root(root_key: str, root_label: str, root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for current_root, dirs, files in os.walk(root):
        rel_root = Path(current_root).relative_to(root)
        rel_root_text = "" if str(rel_root) == "." else str(rel_root).replace("\\", "/")
        for d in sorted(dirs):
            rel_path = _namespaced_path(root_key, "/".join(part for part in [rel_root_text, d] if part))
            entries.append({
                "path": rel_path,
                "name": d,
                "type": "directory",
                "source_key": root_key,
                "source_label": root_label,
                "source_root": str(root),
            })
        for f in sorted(files):
            rel_path = _namespaced_path(root_key, "/".join(part for part in [rel_root_text, f] if part))
            entries.append({
                "path": rel_path,
                "name": f,
                "type": "file",
                "source_key": root_key,
                "source_label": root_label,
                "source_root": str(root),
            })
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
    return entries


def build_files_payload(mgr):
    roots = _all_read_roots(mgr)
    entries: list[dict[str, str]] = []
    for root in roots:
        path = Path(root["path"]).resolve()
        if not path.exists() or not path.is_dir():
            continue
        entries.extend(_file_entries_for_root(root["key"], root["label"], path))
    return {
        "ok": True,
        "base_path": str(_workspace_root(mgr)),
        "workspace_mirror_root": str(_workspace_root(mgr)),
        "workspace_scope_root": str(getattr(mgr, "workspace_scope_root", "")),
        "workspace_id": str(getattr(mgr, "workspace_id", "")),
        "source_roots": roots,
        "entries": entries,
    }


def handle_list(handler):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    try:
        send_json(handler, 200, build_files_payload(mgr))
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "state": "failed", "error_code": "FILES_LIST_FAILED", "message": f"Error listando archivos: {exc}"})


def handle_read(handler, file_path: str):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    raw_path = unquote(file_path)
    optional = parse_qs(urlparse(str(getattr(handler, "path", ""))).query).get("optional", [""])[0].strip().lower() in {
        "1", "true", "yes",
    }
    base, relative_path = _resolve_namespaced_target(mgr, raw_path)
    target = (base / relative_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        send_json(handler, 403, {"ok": False, "state": "blocked", "error_code": "PATH_OUT_OF_SCOPE", "message": "La ruta está fuera del alcance autorizado.", "path": raw_path, "workspace_mirror_root": str(base)})
        return
    if not target.is_file():
        if optional:
            send_json(handler, 200, {
                "ok": True,
                "exists": False,
                "path": raw_path,
                "workspace_id": str(getattr(mgr, "workspace_id", "")),
                "workspace_mirror_root": str(base),
                "content": "",
                "encoding": "utf-8",
                "size": 0,
            })
            return
        send_json(handler, 404, {"ok": False, "state": "blocked", "error_code": "FILE_NOT_FOUND", "message": "Archivo no encontrado", "path": raw_path, "workspace_mirror_root": str(base)})
        return
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        send_json(handler, 200, {
            "ok": True,
            "exists": True,
            "path": raw_path,
            "absolute_path": str(target),
            "workspace_id": str(getattr(mgr, "workspace_id", "")),
            "workspace_mirror_root": str(base),
            "hash": "",
            "content": content,
            "encoding": "utf-8",
            "size": target.stat().st_size,
        })
    except OSError as exc:
        send_json(handler, 500, {"ok": False, "state": "failed", "error_code": "FILE_READ_FAILED", "message": f"Error leyendo archivo: {exc}", "path": raw_path, "workspace_mirror_root": str(base)})


def handle_sources(handler, body: dict | None = None):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    body = body or {}
    cfg = getattr(mgr, "config", None)
    if cfg is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "CONFIG_UNAVAILABLE", "message": "ConfigManager no disponible"})
        return
    if handler.command == "GET":
        send_json(handler, 200, {"ok": True, "source_roots": _all_read_roots(mgr)})
        return

    action = str(body.get("action") or "add").strip().lower()
    raw_path = str(body.get("path") or "").strip()
    raw_label = str(body.get("label") or "").strip()
    if not raw_path and action != "list":
        send_json(handler, 400, {"ok": False, "state": "blocked", "error_code": "MISSING_PATH", "message": "Campo 'path' requerido"})
        return

    base = _project_root(mgr)
    if action == "add":
        try:
            resolved = _resolve_source_path(raw_path, base)
        except Exception as exc:
            send_json(handler, 400, {"ok": False, "state": "blocked", "error_code": "INVALID_PATH", "message": f"Ruta inválida: {exc}"})
            return
        if not resolved.exists() or not resolved.is_dir():
            send_json(handler, 404, {"ok": False, "state": "blocked", "error_code": "SOURCE_NOT_FOUND", "message": "La fuente debe existir y ser un directorio.", "path": str(resolved)})
            return
        roots = list(cfg.read_roots() if hasattr(cfg, "read_roots") else list(cfg.get("sources.read_roots", []) or []))
        normalized = str(resolved)
        for item in roots:
            current_path = str(item.get("path") or item.get("root") or "").strip()
            if current_path and Path(current_path).expanduser().resolve() == resolved:
                send_json(handler, 200, {"ok": True, "state": "ready", "source_roots": _all_read_roots(mgr), "message": "Fuente ya registrada"})
                return
        existing_keys = {str(item.get("key") or "").strip().lower() for item in roots if isinstance(item, dict)}
        key = _source_key(str(body.get("key") or ""), raw_label or resolved.name, resolved, existing_keys)
        roots.append({
            "key": key,
            "label": raw_label or resolved.name,
            "path": normalized,
        })
        if hasattr(cfg, "set_read_roots"):
            cfg.set_read_roots(roots)
        else:
            cfg.set("sources.read_roots", roots)
        send_json(handler, 200, {"ok": True, "state": "ready", "source_roots": _all_read_roots(mgr), "message": "Fuente añadida", "source": {"key": key, "label": raw_label or resolved.name, "path": normalized}})
        return

    if action == "remove":
        removed = False
        if hasattr(cfg, "remove_read_root"):
            removed = cfg.remove_read_root(raw_path)
        else:
            roots = list(cfg.get("sources.read_roots", []) or [])
            next_roots = [item for item in roots if str(item.get("key") or "").strip().lower() != raw_path.lower() and str(item.get("path") or "").strip().lower() != raw_path.lower()]
            removed = len(next_roots) != len(roots)
            if removed:
                cfg.set("sources.read_roots", next_roots)
        send_json(handler, 200 if removed else 404, {"ok": removed, "state": "ready" if removed else "blocked", "source_roots": _all_read_roots(mgr), "message": "Fuente eliminada" if removed else "Fuente no encontrada"})
        return

    send_json(handler, 400, {"ok": False, "state": "blocked", "error_code": "INVALID_ACTION", "message": f"Acción no soportada: {action}"})


_WRITE_FORBIDDEN = {".git", ".env", "state", "dist", "release", "__pycache__", "node_modules", ".venv", "venv"}


def _resolve_write_root(mgr) -> "Path":
    """Resolve the best available writable root from the session manager.
    Explicit project authorities remain writable even when the user selected a
    directory below Temp/AppData. Only derived mirror/base-path fallbacks are
    filtered, so an isolated runtime can never redirect writes to ``cwd``."""
    import tempfile, os
    _tmp = Path(tempfile.gettempdir()).resolve()
    _appdata = Path(os.environ.get("APPDATA", "")).resolve() if os.environ.get("APPDATA") else None
    _localappdata = Path(os.environ.get("LOCALAPPDATA", "")).resolve() if os.environ.get("LOCALAPPDATA") else None

    def _is_temp(p: Path) -> bool:
        try:
            p.relative_to(_tmp)
            return True
        except ValueError:
            pass
        if _appdata:
            try:
                p.relative_to(_appdata)
                return True
            except ValueError:
                pass
        if _localappdata:
            try:
                p.relative_to(_localappdata)
                return True
            except ValueError:
                pass
        return False

    for attr in ("project_root", "workspace_scope_root"):
        val = getattr(mgr, attr, None)
        if val:
            p = Path(str(val)).resolve()
            if p.exists():
                return p

    for attr in ("workspace_mirror_root", "base_path"):
        val = getattr(mgr, attr, None)
        if val:
            p = Path(str(val)).resolve()
            if p.exists() and not _is_temp(p):
                return p
    return Path.cwd().resolve()


def handle_write(handler, body: dict):
    """POST /files/write - authorize and execute one workspace write.

    The HTTP handler never writes directly.  It only constructs the exact
    request, exposes the challenge/approval lifecycle, and delegates the
    material effect to the server-owned filesystem adapter.
    """
    from api_serializers import send_json
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_gateway import ExecutionContext, ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError, build_execution_request

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return

    payload = dict(body or {})
    raw_path = str(payload.get("path") or "").strip()
    if not raw_path:
        send_json(handler, 400, {"ok": False, "error_code": "MISSING_PATH", "message": "Campo 'path' requerido"})
        return

    request = build_execution_request(
        effect_id="filesystem.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=str(getattr(mgr, "session_id", "") or ""),
        source_surface="api.files.write",
        target={"path": raw_path},
        arguments={"content": str(payload.get("content") or "")},
        scope="workspace",
    )
    boundary = AuthorizationBoundary()
    action = str(payload.get("authorization_action") or "").strip().lower()
    interaction_id = str(payload.get("interaction_id") or "").strip()
    try:
        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {"ok": True, "authorization": {"state": "challenge", "challenge": challenge}})
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
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **authorization}})
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
        send_json(handler, 200, response)
    except AuthorizationError as exc:
        status = 409 if exc.code in {
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
        status = 500 if getattr(exc, "code", "") == "filesystem_write_failed" else 403 if str(getattr(exc, "code", "")).startswith("filesystem_") else 409
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
