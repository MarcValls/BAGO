"""Narrow process operation for the trusted PI provider sidecar."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class PiSidecarProcessEffectAdapter:
    effect_ids = frozenset({"process.sidecar.execute"})
    server_policy_effects = effect_ids

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not (
            isinstance(authorization, dict)
            and authorization.get("kind") == "server_policy"
            and authorization.get("effect_id") == request.effect_id
            and authorization.get("operation_fingerprint") == request.fingerprint
            and authorization.get("session_id") == request.session_id
            and request.source_surface == "server.pi.sidecar"
            and request.actor_kind == "server"
            and request.principal_id == "bago-pi-provider"
        ):
            raise ExecutionGatewayError("PI sidecar requires its exact server policy request", code="pi_sidecar_authorization_required")

        target = request.target if isinstance(request.target, dict) else {}
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        if target.get("operation") != "provider-sidecar" or set(target) != {
            "operation", "node_path", "sidecar_path", "sidecar_sha256", "cwd", "timeout_seconds", "home_parent",
        } or set(arguments) != {"stdin_payload", "environment", "execution_id"}:
            raise ExecutionGatewayError("PI sidecar request shape is invalid", code="pi_sidecar_request_invalid")

        expected_script = (Path(__file__).resolve().parents[2] / "integrations" / "pi" / "sidecar" / "src" / "main.js").resolve()
        raw_script = Path(str(target.get("sidecar_path") or "")).expanduser()
        if raw_script.is_symlink() or raw_script.resolve(strict=False) != expected_script or not expected_script.is_file():
            raise ExecutionGatewayError("PI sidecar is outside its canonical runtime path", code="pi_sidecar_path_invalid")
        actual_digest = hashlib.sha256(expected_script.read_bytes()).hexdigest()
        if actual_digest != str(target.get("sidecar_sha256") or ""):
            raise ExecutionGatewayError("PI sidecar changed before process dispatch", code="pi_sidecar_digest_mismatch")

        raw_node = Path(str(target.get("node_path") or "")).expanduser()
        if raw_node.name.lower() not in {"node", "node.exe"} or not raw_node.is_file():
            raise ExecutionGatewayError("Node executable is not approved", code="pi_sidecar_node_invalid")
        resolved_node = raw_node.resolve(strict=True)
        if Path(shutil.which(str(resolved_node)) or "").resolve() != resolved_node:
            raise ExecutionGatewayError("Node executable is not resolvable", code="pi_sidecar_node_unavailable")

        try:
            cwd = Path(str(target.get("cwd") or "")).expanduser().resolve(strict=True)
            home_parent = Path(str(target.get("home_parent") or "")).expanduser().resolve(strict=True)
            timeout = float(target.get("timeout_seconds"))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ExecutionGatewayError("PI sidecar runtime paths or timeout are invalid", code="pi_sidecar_runtime_invalid") from exc
        if not cwd.is_dir() or not home_parent.is_dir() or not 0 < timeout <= 600:
            raise ExecutionGatewayError("PI sidecar cwd, temp root, or timeout is outside policy", code="pi_sidecar_runtime_invalid")

        execution_id = str(arguments.get("execution_id") or "")
        stdin_payload = arguments.get("stdin_payload")
        environment = arguments.get("environment")
        if not execution_id or len(execution_id) > 128 or not isinstance(stdin_payload, str) or len(stdin_payload.encode("utf-8")) > 1_048_576:
            raise ExecutionGatewayError("PI sidecar input identity or payload is invalid", code="pi_sidecar_input_invalid")
        if not isinstance(environment, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()
        ):
            raise ExecutionGatewayError("PI sidecar environment is invalid", code="pi_sidecar_environment_invalid")
        from integrations.pi.process_boundary import ALLOWED_ENV_KEYS
        if set(environment) - (set(ALLOWED_ENV_KEYS) - {"NODE_OPTIONS"}):
            raise ExecutionGatewayError("PI sidecar environment contains unapproved keys", code="pi_sidecar_environment_invalid")
        if environment.get("BAGO_BRIDGE_EXECUTION_ID") != execution_id or environment.get("BAGO_BRIDGE_CORRELATION_ID") != request.session_id:
            raise ExecutionGatewayError("PI sidecar process identity is inconsistent", code="pi_sidecar_identity_mismatch")

        child_env = dict(environment)
        cancel_token = context.services.get("_pi_cancel_token")
        try:
            with tempfile.TemporaryDirectory(prefix="bago-pi-home-", dir=str(home_parent)) as home:
                child_env["HOME"] = home
                child_env["USERPROFILE"] = home
                try:
                    process = subprocess.Popen(
                        [str(resolved_node), str(expected_script)],
                        cwd=str(cwd),
                        env=child_env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        shell=False,
                    )
                except OSError as exc:
                    raise ExecutionGatewayError(f"PI sidecar process could not start: {exc}", code="pi_sidecar_spawn_failed") from exc

                communication: list[tuple[str, str] | BaseException] = []

                def communicate() -> None:
                    try:
                        communication.append(process.communicate(input=stdin_payload))
                    except BaseException as exc:  # surfaced in the dispatch thread
                        communication.append(exc)

                worker = threading.Thread(target=communicate, name="bago-pi-sidecar-io", daemon=True)
                worker.start()
                deadline = time.monotonic() + timeout
                cancelled = False
                timed_out = False
                while worker.is_alive():
                    if cancel_token is not None and callable(getattr(cancel_token, "is_cancelled", None)) and cancel_token.is_cancelled():
                        cancelled = True
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    worker.join(timeout=min(0.05, remaining))
                if cancelled or timed_out:
                    process.terminate()
                    try:
                        process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                worker.join(timeout=2.0)
                if worker.is_alive():
                    process.kill()
                    process.wait()
                    worker.join()
                if timed_out:
                    raise ExecutionGatewayError("PI sidecar timed out", code="pi_sidecar_timeout")
                if communication and isinstance(communication[0], BaseException):
                    raise ExecutionGatewayError("PI sidecar stream communication failed", code="pi_sidecar_process_failed") from communication[0]
                stdout, stderr = communication[0] if communication else ("", "")
                if cancelled:
                    return {
                        "ok": False,
                        "executed": True,
                        "effect_id": request.effect_id,
                        "exit_code": int(process.returncode or 0),
                        "stdout": str(stdout or "")[-65536:],
                        "stderr": str(stderr or "")[-65536:],
                        "cancelled": True,
                        "receipt_id": f"pi-sidecar:{request.fingerprint}",
                    }
        except ExecutionGatewayError:
            raise
        except OSError as exc:
            raise ExecutionGatewayError(f"PI sidecar process failed: {exc}", code="pi_sidecar_process_failed") from exc

        return {
            "ok": process.returncode == 0,
            "executed": True,
            "effect_id": request.effect_id,
            "exit_code": int(process.returncode),
            "stdout": str(stdout or "")[-65536:],
            "stderr": str(stderr or "")[-65536:],
            "cancelled": False,
            "receipt_id": f"pi-sidecar:{request.fingerprint}",
        }
