from __future__ import annotations

import sys, uuid
from pathlib import Path
from typing import Any

CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

# CANON[PRJ-001]: /project is the canonical binding surface for project/workspace state.
# CANON[PRJ-002]: analyze/status/init/link all rebind through SessionManager before reporting.
# LEGACY[PRJ-L001]: load_tool_module and parse_project_args stay local for direct file imports.
from command_utils import load_tool_module, parse_project_args


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve().samefile(right.resolve())
    except Exception:
        try:
            return left.resolve() == right.resolve()
        except Exception:
            return str(left).lower() == str(right).lower()


PROJECT_WRITE_ACTIONS = frozenset({"init", "link", "seed"})


def build_project_write_request(mgr: Any, action: str, project_root: Path):
    from execution_gateway import ProjectWriteEffectAdapter
    from execution_request import build_execution_request

    trusted_root, target, target_digest = ProjectWriteEffectAdapter.prepare_operation(
        mgr,
        str(project_root),
        action,
    )
    arguments = {"depth": 3, "ref": ""} if action == "seed" else {}
    return build_execution_request(
        effect_id="project.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=str(getattr(mgr, "session_id", "") or ""),
        source_surface=f"project.command.{action}",
        target={
            "path": str(target),
            "allowed_root": str(trusted_root),
            "resource": "project_operation",
            "operation": action,
            "root_digest": target_digest,
        },
        arguments=arguments,
        scope="workspace",
    )


def _format_project_write(action: str, receipt: dict[str, Any]) -> dict[str, Any]:
    report = dict(receipt.get("result") or {})
    if action == "init":
        message = (
            f"Initialized project memory at: {report['bago_dir']}\n"
            f"Created directories: {len(report['created_dirs'])}\n"
            f"Created files: {len(report['created_files'])}"
        )
    elif action == "link":
        message = (
            f"Linked project memory at: {report['root']}\n"
            f"Link mode: {report['link_mode']}\n"
            f"Marker: {report['marker']}"
        )
    else:
        message = (
            f"Seeded workspace at: {report['root']}\n"
            f"Tree files: {report['tree']['count']}\n"
            f"Files indexed: {report['meta']['files_indexed']}\n"
            f"Symbols indexed: {report['meta']['symbols_indexed']}\n"
            f"Working set size: {report['meta']['working_set_size']}"
        )
    return {"ok": True, "message": message, "data": report, "receipt": receipt}


def _execute_project_write(mgr: Any, request, permit_token: str) -> dict[str, Any]:
    from authorization_boundary import AuthorizationBoundary
    from execution_gateway import ExecutionContext, ExecutionGateway

    result, _authorization = ExecutionGateway(AuthorizationBoundary()).execute(
        permit_token=permit_token,
        request=request,
        context=ExecutionContext(manager=mgr),
    )
    return dict(result)


def _execute_direct_user_project_write(mgr: Any, request) -> dict[str, Any]:
    from authorization_boundary import AuthorizationBoundary

    boundary = AuthorizationBoundary()
    interaction_id = f"project-command-{uuid.uuid4().hex}"
    challenge = boundary.create_challenge(request, interaction_id=interaction_id)
    authorization = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id=interaction_id,
        session_id=request.session_id,
        channel="desktop",
    )
    return _execute_project_write(mgr, request, authorization["permit"]["token"])


def cmd_project(
    mgr: Any,
    engine: Any,
    args: list[str],
    *,
    load_module=load_tool_module,
    permit_token: str = "",
    direct_user_authorized: bool = False,
) -> dict:
    mod = load_module("project_memory", "project_memory.py")
    action, root = parse_project_args(args)
    project_root = None
    if root:
        project_root = mod.resolve_project_root(root, allow_fallback_cwd=False)
    else:
        project_root = Path(getattr(mgr, "project_root", getattr(mgr, "base_path", Path.cwd()))).expanduser().resolve()
    if project_root is None:
        return {
            "ok": False,
            "message": "No hay proyecto activo. Usa /project <analyze|status|init|link|seed|sync> <ruta>.",
        }

    if action == "sync" and root:
        return {"ok": False, "message": "Uso: /project sync (sin ruta)."}

    if action in PROJECT_WRITE_ACTIONS:
        try:
            request = build_project_write_request(mgr, action, project_root)
            if direct_user_authorized:
                receipt = _execute_direct_user_project_write(mgr, request)
            elif permit_token:
                receipt = _execute_project_write(mgr, request, permit_token)
            else:
                return {
                    "ok": False,
                    "message": f"/project {action} requiere autorización explícita",
                    "authorization_required": True,
                    "request": request,
                }
            return _format_project_write(action, receipt)
        except Exception as exc:
            return {"ok": False, "message": f"No se pudo ejecutar /project {action}: {exc}"}
    if action == "status":
        data = mod.status_data(project_root)
        return {"ok": True, "message": mod.format_status(data), "data": data}
    if action == "analyze":
        data = mod.analyze_data(project_root)
        if hasattr(mgr, "record_project_analysis"):
            mgr.record_project_analysis(data)
        return {"ok": True, "message": mod.format_analysis(data), "data": data}
    if action == "sync":
        if not hasattr(mgr, "sync_workspace_mirror"):
            return {"ok": False, "message": "La sesión no expone sync_workspace_mirror()."}
        data = mgr.sync_workspace_mirror()
        return {"ok": bool(data.get("ok")), "message": data.get("message", "Sincronización completada"), "data": data}
    return {"ok": False, "message": "Uso: /project [analyze|status|init|link|seed|sync] [ruta|depth]"}
