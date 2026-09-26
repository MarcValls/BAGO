"""Strong-Permit dispatcher for one ticket-bound BAGO uninstall operation."""
from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from install_uninstall_plan import build_uninstall_target, resolve_uninstall_python, validate_uninstall_backup_space


class SystemInstallUninstallEffectAdapter:
    effect_ids = frozenset({"system.install.uninstall"})

    @staticmethod
    def _write_ticket(request: ExecutionRequest, authorization: dict[str, Any]) -> tuple[Path, str, Path]:
        proof = authorization.get("proof")
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (authorization.get("state") != "consumed" or authorization.get("effect_id") != request.effect_id
                or authorization.get("operation_fingerprint") != request.fingerprint
                or not isinstance(proof, dict) or proof.get("user_decision") != "approve"
                or proof.get("operation_fingerprint") != request.fingerprint
                or not isinstance(provenance, dict) or provenance.get("kind") != "direct_user_interaction"
                or provenance.get("channel") != "desktop"):
            raise ExecutionGatewayError("Uninstall requires a consumed desktop Permit for this exact operation", code="system_install_uninstall_proof_required")
        permit_id = str(authorization.get("permit_id") or "")
        if not re.fullmatch(r"permit-[A-Za-z0-9-]+", permit_id):
            raise ExecutionGatewayError("Uninstall Permit identity is invalid", code="system_install_uninstall_permit_invalid")
        from authorization_boundary import authorization_ledger_path
        ledger = authorization_ledger_path().resolve()
        directory = ledger.parent / "install-tickets"
        if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise ExecutionGatewayError("Uninstall ticket directory is unsafe", code="system_install_uninstall_ticket_directory_unsafe")
        try:
            directory.mkdir(parents=True, exist_ok=True)
            ticket = directory / f"{permit_id}.json"
            nonce = uuid.uuid4().hex
            body = {"schema": "bago.system-install-uninstall-ticket.v1", "nonce": nonce,
                    "permit_id": permit_id, "effect_id": request.effect_id,
                    "session_id": request.session_id, "operation_fingerprint": request.fingerprint,
                    "target": request.target}
            with ticket.open("x", encoding="utf-8", newline="\n") as stream:
                os.chmod(ticket, 0o600)
                json.dump(body, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise ExecutionGatewayError("Uninstall ticket already exists for this Permit", code="system_install_uninstall_ticket_replay") from exc
        except OSError as exc:
            raise ExecutionGatewayError(f"Could not persist uninstall ticket: {exc}", code="system_install_uninstall_ticket_write_failed") from exc
        return ticket, nonce, ledger

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        if manager is None or str(getattr(manager, "session_id", "") or "") != request.session_id:
            raise ExecutionGatewayError("Uninstall requires the active SessionManager", code="system_install_uninstall_session_mismatch")
        try:
            current = build_uninstall_target(str(request.target.get("install_dir") or ""), bool(request.target.get("purge_state")))
        except ExecutionGatewayError:
            raise
        if current != request.target:
            raise ExecutionGatewayError("Uninstall target/helper changed after approval", code="system_install_uninstall_target_changed")
        validate_uninstall_backup_space(current)
        authorization = context.services.get("_authorization")
        python = resolve_uninstall_python(Path(request.target["install_dir"]))
        ticket, nonce, ledger = self._write_ticket(request, authorization if isinstance(authorization, dict) else {})
        active_cli = Path(__file__).resolve().parents[3] / "bago_core" / "cli.py"
        command = [python, str(active_cli), "uninstall",
                   "--install-dir", request.target["install_dir"], "--backup-root", request.target["backup_root"],
                   "--user-state-dir", request.target["user_state_dir"],
                   "--authorization-ticket-path", str(ticket), "--authorization-ticket-nonce", nonce,
                   "--authorization-permit-id", str(authorization.get("permit_id")),
                   "--authorization-ledger-path", str(ledger)]
        if request.target["purge_state"]:
            command.append("--purge-state")
        try:
            # The helper may remove install_dir; its parent process must not
            # hold that directory as its current working directory on Windows.
            result = subprocess.run(command, cwd=str(active_cli.parent.parent), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    encoding="utf-8", errors="replace", timeout=1800, check=False, shell=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutionGatewayError(f"Uninstall helper failed: {exc}", code="system_install_uninstall_process_failed") from exc
        finally:
            ticket.unlink(missing_ok=True)
            ticket.with_suffix(".consumed").unlink(missing_ok=True)
        if result.returncode:
            raise ExecutionGatewayError((result.stderr or result.stdout or f"uninstall exited {result.returncode}").strip(), code="system_install_uninstall_process_failed")
        return {"ok": True, "executed": True, "effect_id": request.effect_id,
                "target": {k: v for k, v in request.target.items() if "sha256" not in k},
                "stdout": str(result.stdout or "")[-65536:],
                "receipt_id": f"system-install-uninstall:{request.fingerprint}"}
