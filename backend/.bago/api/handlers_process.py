"""Desktop-confirmed process execution through the canonical Gateway."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_OPERATIONS = {
    "launcher": ("module", "bago_core.launcher", 300),
    "session_control": ("module", "bago_core.session_control", 180),
    "supervisor": ("script", "scripts/bago_supervisor.py", 15),
    "cleanup_zombies": ("terminate", "cleanup_zombies", 20),
    "stop_webchat": ("terminate", "stop_webchat", 20),
    "github_cli": ("executable", "gh", 120),
    "git_identity": ("executable", "git", 30),
}


def handle_execute(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_gateway import ExecutionGateway
    from execution_request import ExecutionRequestError, build_execution_request
    from execution_adapters.process import ProcessExecutionEffectAdapter

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return

    operation = str((body or {}).get("operation") or "").strip()
    operation_spec = _OPERATIONS.get(operation)
    raw_argv = (body or {}).get("argv")
    if operation_spec is None or not isinstance(raw_argv, list) or len(raw_argv) > 256:
        send_json(handler, 400, {"ok": False, "error": "Operación de proceso no válida"})
        return
    argv = [str(value) for value in raw_argv]
    if any("\x00" in value or len(value) > 16384 for value in argv):
        send_json(handler, 400, {"ok": False, "error": "Argumentos de proceso no válidos"})
        return
    if operation in {"cleanup_zombies", "stop_webchat"} and argv:
        send_json(handler, 400, {"ok": False, "error": "La operación de terminación no acepta argumentos"})
        return

    if operation == "github_cli" and not ProcessExecutionEffectAdapter.is_authorized_executable_argv("gh", argv):
        send_json(handler, 400, {"ok": False, "error": "Operación gh no permitida"})
        return
    if operation == "git_identity" and not ProcessExecutionEffectAdapter.is_authorized_executable_argv("git", argv):
        send_json(handler, 400, {"ok": False, "error": "Operación git identity no permitida"})
        return

    if operation == "session_control" and any(value == "--base-path" or value.startswith("--base-path=") for value in argv):
        send_json(handler, 400, {"ok": False, "error": "--base-path lo fija el backend según la sesión activa"})
        return
    if operation == "session_control":
        argv = ["--base-path", str(getattr(manager, "base_path", "") or ""), *argv]

    target_kind, trusted_program, timeout = operation_spec
    read_only_inspection = (
        operation == "launcher" and ProcessExecutionEffectAdapter.is_read_only_launcher_argv(argv)
    ) or (
        operation == "github_cli" and ProcessExecutionEffectAdapter.is_read_only_github_argv(argv)
    )
    if read_only_inspection:
        timeout = 30
    cwd = str(getattr(manager, "base_path", "") or "").strip()
    python_root = str(getattr(manager, "framework_root", "") or "").strip()
    session_id = str(getattr(manager, "session_id", "") or "").strip()
    if not cwd or not python_root or not session_id:
        send_json(handler, 503, {"ok": False, "error": "Identidad de sesión incompleta"})
        return
    trusted_root = Path(python_root).expanduser().resolve()
    module_digest = ""
    if target_kind in {"module", "script"}:
        module_file = trusted_root.joinpath(*trusted_program.split(".")) if target_kind == "module" else trusted_root / trusted_program
        if target_kind == "module":
            module_file = module_file.with_suffix(".py")
        try:
            module_digest = hashlib.sha256(module_file.read_bytes()).hexdigest()
        except OSError:
            send_json(handler, 503, {"ok": False, "error": "Programa BAGO no disponible en el runtime confiable"})
            return
    effect_id = "process.inspect" if read_only_inspection else ("process.terminate" if target_kind == "terminate" else "process.execute")
    target = {"cwd": cwd, "timeout_seconds": timeout, "operation": trusted_program}
    if target_kind in {"module", "script"}:
        target.update({
            "python_module" if target_kind == "module" else "python_script": trusted_program,
            "python_root": str(trusted_root),
            "python_module_sha256": module_digest,
        })
    elif target_kind == "executable":
        target["executable"] = trusted_program
    if target_kind == "terminate":
        if trusted_program == "cleanup_zombies":
            state_root = str(getattr(manager, "state_root", "") or "").strip()
            if not state_root:
                send_json(handler, 503, {"ok": False, "error": "Raíz de estado confiable no disponible"})
                return
            target["cleanup_roots"] = sorted({str(trusted_root), str(Path(state_root).expanduser().resolve())})
        else:
            server = getattr(handler, "server", None)
            try:
                port = int(getattr(server, "server_port", 0) or 0)
            except (TypeError, ValueError):
                port = 0
            if not 1 <= port <= 65535:
                send_json(handler, 503, {"ok": False, "error": "Identidad del servidor HTTP incompleta"})
                return
            target.update({"process_id": os.getpid(), "port": port, "python_root": str(trusted_root)})
    try:
        request = build_execution_request(
            effect_id=effect_id,
            actor_kind="server" if read_only_inspection else "user",
            principal_id="bago-runtime" if read_only_inspection else "interactive-local-user",
            session_id=session_id,
            source_surface="server.process.inspect" if read_only_inspection else "api.process.terminate.desktop" if target_kind == "terminate" else "api.process.execute.desktop",
            target=target,
            arguments={"argv": argv},
            scope="system" if target_kind == "terminate" else "workspace",
        )
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
        return

    if read_only_inspection:
        try:
            result, authorization = ExecutionGateway().execute_server_owned(
                request=request,
                context=ExecutionContext(manager=manager),
            )
            send_json(handler, 200, {
                "ok": True,
                "read_only": True,
                "process_result": result,
                "authorization": {"state": "server_policy", "proof_id": authorization.get("proof_id")},
            })
        except ExecutionGatewayError as exc:
            send_json(handler, 403, {"ok": False, "error": str(exc), "code": str(getattr(exc, "code", "") or "")})
        return

    boundary = AuthorizationBoundary()
    action = str((body or {}).get("authorization_action") or "").strip().lower()
    interaction_id = str((body or {}).get("interaction_id") or "").strip()
    try:
        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {"ok": True, "authorization": {"state": "challenge", "challenge": challenge}})
            return
        if action == "approve":
            if str((body or {}).get("user_decision") or "").strip().lower() != "approve":
                raise AuthorizationError("La decisión explícita debe ser approve", code="authorization_user_decision_required")
            headers = getattr(handler, "headers", {}) or {}
            channel = headers.get("X-Bago-Channel", "") if hasattr(headers, "get") else ""
            if channel != "desktop":
                raise AuthorizationError("Esta operación requiere confirmación desktop directa", code="process_execution_desktop_confirmation_required")
            approval = boundary.approve_challenge(
                challenge_id=str((body or {}).get("challenge_id") or ""),
                interaction_id=interaction_id,
                session_id=request.session_id,
                channel=channel,
            )
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **approval}})
            return
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_required")
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str((body or {}).get("authorization_permit") or ""),
            request=request,
            context=ExecutionContext(manager=manager),
        )
        send_json(handler, 200, {
            "ok": True,
            "process_result": result,
            "authorization": {
                "state": "consumed",
                "permit_id": authorization.get("permit_id"),
                "decision_id": authorization.get("decision_id"),
                "proof_id": authorization.get("proof_id"),
                "operation_fingerprint": authorization.get("operation_fingerprint"),
            },
        })
    except AuthorizationError as exc:
        status = 409 if exc.code in {
            "authorization_challenge_not_pending", "authorization_challenge_expired",
            "authorization_permit_replay", "authorization_permit_expired",
            "authorization_operation_mismatch",
        } else 403
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        code = str(getattr(exc, "code", "") or "")
        send_json(handler, 403 if code.startswith("process_execution_") else 409, {"ok": False, "error": str(exc), "code": code})

