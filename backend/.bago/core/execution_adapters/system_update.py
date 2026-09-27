"""Server-owned, directly authorized system update application."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class SystemUpdateApplyEffectAdapter:
    """Launch only the verified BAGO update helper bound into a strong Permit."""

    effect_ids = frozenset({"system.update.apply"})

    @staticmethod
    def _write_helper_ticket(
        request: ExecutionRequest,
        authorization: dict[str, Any],
        bundle: Path,
    ) -> tuple[Path, str, str]:
        proof = authorization.get("proof")
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            not isinstance(proof, dict)
            or proof.get("effect_id") != request.effect_id
            or proof.get("operation_fingerprint") != request.fingerprint
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
        ):
            raise ExecutionGatewayError(
                "System update helper requires the consumed direct-interaction proof",
                code="system_update_helper_proof_required",
            )

        permit_id = str(authorization.get("permit_id") or "")
        if not permit_id or "/" in permit_id or "\\" in permit_id:
            raise ExecutionGatewayError(
                "System update Permit identity is invalid",
                code="system_update_helper_permit_invalid",
            )
        ticket_path = bundle.parent / f".apply-{permit_id}.json"
        nonce = uuid.uuid4().hex
        payload = {
            "schema": "bago.system-update-helper-ticket.v1",
            "nonce": nonce,
            "permit_id": permit_id,
            "operation_fingerprint": request.fingerprint,
            "effect_id": request.effect_id,
            "session_id": request.session_id,
            "target": dict(request.target),
        }
        try:
            with ticket_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise ExecutionGatewayError(
                "An update helper ticket already exists for this Permit",
                code="system_update_helper_ticket_replay",
            ) from exc
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Could not persist the one-time update helper ticket: {exc}",
                code="system_update_helper_ticket_write_failed",
            ) from exc
        return ticket_path, nonce, permit_id

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager is None or not manager_session or manager_session != request.session_id:
            raise ExecutionGatewayError(
                "System update requires the current SessionManager",
                code="system_update_session_mismatch",
            )

        authorization = context.services.get("_authorization")
        proof = authorization.get("proof") if isinstance(authorization, dict) else None
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            not isinstance(authorization, dict)
            or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(proof, dict)
            or proof.get("effect_id") != request.effect_id
            or proof.get("operation_fingerprint") != request.fingerprint
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
        ):
            raise ExecutionGatewayError(
                "System update requires direct user authorization for this exact operation",
                code="system_update_strong_proof_required",
            )

        from update_manager import _lock, _replace_state, _set_state, status, update_apply_descriptor

        try:
            with _lock:
                current = update_apply_descriptor()
                if current != dict(request.target):
                    raise ExecutionGatewayError(
                        "Prepared update or installation changed after authorization",
                        code="system_update_target_changed",
                    )
                previous = status()
        except Exception as exc:
            if isinstance(exc, ExecutionGatewayError):
                raise
            raise ExecutionGatewayError(
                f"Prepared update is no longer applicable: {exc}",
                code="system_update_preflight_failed",
            ) from exc

        bundle = Path(current["bundle_path"])
        log_path = Path(current["log_path"])
        if log_path.parent != bundle.parent or log_path.name != "apply.log":
            raise ExecutionGatewayError(
                "System update log target is outside the server cache",
                code="system_update_log_target_invalid",
            )

        ticket_path, ticket_nonce, permit_id = self._write_helper_ticket(
            request, authorization, bundle
        )

        try:
            _set_state(
                status="applying",
                phase="apply",
                message="BAGO se cerrará, instalará la actualización y volverá a abrirse.",
                error="",
            )
        except Exception as exc:
            ticket_path.unlink(missing_ok=True)
            raise ExecutionGatewayError(
                f"Could not record the authorized update transition: {exc}",
                code="system_update_state_transition_failed",
            ) from exc

        command = [
            current["powershell"],
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", current["helper_path"],
            "-BundlePath", current["bundle_path"],
            "-InstallRoot", current["install_root"],
            "-StatePath", current["state_path"],
            "-ExpectedVersion", current["expected_version"],
            "-ExpectedSha256", current["bundle_sha256"],
            "-AuthorizationLedgerPath", current["authorization_ledger_path"],
            "-AuthorizationTicketPath", str(ticket_path),
            "-AuthorizationTicketNonce", ticket_nonce,
            "-PermitId", permit_id,
            "-BackendPid", current["backend_pid"],
            "-Restart",
        ]
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as log:
                process = subprocess.Popen(
                    command,
                    cwd=str(bundle.parent),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                    close_fds=True,
                )
        except OSError as exc:
            ticket_path.unlink(missing_ok=True)
            _replace_state(previous)
            raise ExecutionGatewayError(
                f"No se pudo iniciar el helper de actualización: {exc}",
                code="system_update_process_start_failed",
            ) from exc

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "status": "applying",
            "process_id": int(getattr(process, "pid", 0) or 0),
            "target": current,
            "receipt_id": f"system-update:{request.fingerprint}",
        }
