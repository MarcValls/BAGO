"""Strong-Permit owner for launching a prepared BAGO installation."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import stat
import uuid
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from install_plan import InstallPlanError, build_install_plan, configuration_digest


class SystemInstallEffectAdapter:
    """Own authorized install application and release-job rollback effects."""

    effect_ids = frozenset({"system.install.apply"})

    @staticmethod
    def _current_plan(request: ExecutionRequest) -> tuple[dict[str, Any], dict[str, Any]]:
        target = request.target
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        configuration = arguments.get("configuration")
        if not isinstance(configuration, dict):
            raise ExecutionGatewayError(
                "Install authorization requires the complete prepared configuration",
                code="system_install_configuration_required",
            )
        try:
            current = build_install_plan(
                action=str(target.get("action") or ""),
                source_root=str(target.get("source_root") or ""),
                helper_path=str(target.get("helper_path") or ""),
                install_dir=str(target.get("install_dir") or ""),
                mode=str(target.get("mode") or ""),
                options=target.get("options") if isinstance(target.get("options"), dict) else {},
                configuration=configuration,
                package_digest=str(target.get("package_sha256") or ""),
            )
        except InstallPlanError as exc:
            raise ExecutionGatewayError(str(exc), code="system_install_plan_invalid") from exc
        if current != target:
            raise ExecutionGatewayError(
                "Install source, helper, configuration, or destination changed after approval",
                code="system_install_plan_changed",
            )
        return current, configuration

    @staticmethod
    def _authorization_ledger_path() -> Path:
        from authorization_boundary import authorization_ledger_path

        return authorization_ledger_path().resolve()

    @staticmethod
    def _prepare_release_backup(target: Path, permit_id: str) -> tuple[str, bool]:
        """Copy the live runtime while preserving it in place for the installer."""
        if not target.exists():
            return "", True
        if target.is_symlink() or not target.is_dir():
            raise ExecutionGatewayError(
                "Release install target must be a regular directory",
                code="system_install_backup_target_invalid",
            )
        size = 0
        try:
            for entry in target.rglob("*"):
                metadata = entry.lstat()
                if entry.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                    raise ExecutionGatewayError(
                        f"Release install target contains a linked entry: {entry}",
                        code="system_install_backup_link_forbidden",
                    )
                if stat.S_ISREG(metadata.st_mode):
                    size += metadata.st_size
            parent = target.parent
            if shutil.disk_usage(parent).free < size:
                raise ExecutionGatewayError(
                    "Not enough free space to make a recoverable release backup",
                    code="system_install_backup_space_insufficient",
                )
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Could not inspect release install target before backup: {exc}",
                code="system_install_backup_preflight_failed",
            ) from exc

        backup = target.with_name(f"{target.name}.bago-rollback-{permit_id}")
        temporary = target.with_name(f".{target.name}.bago-backup-{permit_id}.tmp")
        if backup.exists() or temporary.exists():
            raise ExecutionGatewayError(
                "Release backup path already exists",
                code="system_install_backup_collision",
            )
        try:
            shutil.copytree(target, temporary, symlinks=False, copy_function=shutil.copy2)
            os.replace(temporary, backup)
        except OSError as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            raise ExecutionGatewayError(
                f"Could not create recoverable release backup: {exc}",
                code="system_install_backup_failed",
            ) from exc
        return str(backup), False

    @staticmethod
    def _restore_failed_release(target: Path, backup_path: str, permit_id: str) -> None:
        backup = Path(backup_path) if backup_path else None
        if backup is None:
            if target.exists():
                failed = target.with_name(f"{target.name}.bago-failed-{permit_id}")
                if failed.exists():
                    raise ExecutionGatewayError(
                        f"Failed install data is already recoverable at {failed}",
                        code="system_install_failed_target_collision",
                    )
                os.replace(target, failed)
            return
        displaced = target.with_name(f"{target.name}.bago-failed-{permit_id}")
        if target.exists():
            if displaced.exists():
                raise ExecutionGatewayError(
                    f"Failed install data is already recoverable at {displaced}",
                    code="system_install_failed_target_collision",
                )
            os.replace(target, displaced)
        try:
            os.replace(backup, target)
        except OSError as exc:
            if displaced.exists() and not target.exists():
                os.replace(displaced, target)
            raise ExecutionGatewayError(
                f"Could not restore release backup {backup}: {exc}",
                code="system_install_backup_restore_failed",
            ) from exc

    @classmethod
    def _write_helper_ticket(
        cls,
        request: ExecutionRequest,
        authorization: dict[str, Any],
        configuration: dict[str, Any],
    ) -> tuple[Path, str, str, Path]:
        proof = authorization.get("proof")
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(proof, dict)
            or proof.get("effect_id") != request.effect_id
            or proof.get("operation_fingerprint") != request.fingerprint
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
            or provenance.get("channel") not in {"ui-react", "desktop"}
        ):
            raise ExecutionGatewayError(
                "Install helper requires a consumed direct-user Permit for this exact operation",
                code="system_install_strong_proof_required",
            )

        permit_id = str(authorization.get("permit_id") or "")
        if not re.fullmatch(r"permit-[A-Za-z0-9-]+", permit_id):
            raise ExecutionGatewayError(
                "Install Permit identity is invalid",
                code="system_install_permit_invalid",
            )
        ledger_path = cls._authorization_ledger_path()
        ticket_dir = ledger_path.parent / "install-tickets"
        if ticket_dir.exists() and (ticket_dir.is_symlink() or not ticket_dir.is_dir()):
            raise ExecutionGatewayError(
                "Install ticket directory is unsafe",
                code="system_install_ticket_directory_unsafe",
            )
        try:
            ticket_dir.mkdir(parents=True, exist_ok=True)
            ticket_path = ticket_dir / f"{permit_id}.json"
            nonce = uuid.uuid4().hex
            payload = {
                "schema": "bago.system-install-helper-ticket.v1",
                "nonce": nonce,
                "permit_id": permit_id,
                "effect_id": request.effect_id,
                "session_id": request.session_id,
                "operation_fingerprint": request.fingerprint,
                "arguments_digest": request.arguments_digest,
                "configuration_digest": configuration_digest(configuration),
                "authorization_ledger_path": str(ledger_path),
                "target": request.target,
                "configuration": configuration,
            }
            with ticket_path.open("x", encoding="utf-8", newline="\n") as stream:
                os.chmod(ticket_path, 0o600)
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise ExecutionGatewayError(
                "Install helper ticket already exists for this Permit",
                code="system_install_ticket_replay",
            ) from exc
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Could not persist one-use install helper ticket: {exc}",
                code="system_install_ticket_write_failed",
            ) from exc
        return ticket_path, nonce, permit_id, ledger_path

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        if manager is None or str(getattr(manager, "session_id", "") or "") != request.session_id:
            raise ExecutionGatewayError(
                "System install requires the active SessionManager",
                code="system_install_session_mismatch",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "System install must be dispatched by ExecutionGateway",
                code="system_install_gateway_context_required",
            )

        current, configuration = self._current_plan(request)
        ticket_path, nonce, permit_id, ledger_path = self._write_helper_ticket(
            request, authorization, configuration
        )
        backup_path = ""
        created_target = False
        if current["action"] == "release-job":
            try:
                backup_path, created_target = self._prepare_release_backup(
                    Path(current["install_dir"]), permit_id
                )
            except Exception:
                ticket_path.unlink(missing_ok=True)
                raise
        powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
        if not powershell:
            ticket_path.unlink(missing_ok=True)
            if backup_path:
                shutil.rmtree(backup_path, ignore_errors=True)
            raise ExecutionGatewayError(
                "PowerShell 5.1 or PowerShell 7 is required for BAGO installation",
                code="system_install_powershell_missing",
            )

        command = [
            powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            current["helper_path"],
            "-SourceRoot", current["source_root"],
            "-InstallDir", current["install_dir"],
            "-Mode", current["mode"],
            "-AuthorizationLedgerPath", str(ledger_path),
            "-AuthorizationTicketPath", str(ticket_path),
            "-AuthorizationTicketNonce", nonce,
            "-PermitId", permit_id,
        ]
        if current["action"] == "release-job":
            command.append("-GatewayBackupProvided")
        if current["action"] == "repair":
            command.append("-RepairOnly")
        for option, switch in (
            ("skip_tests", "-SkipTests"),
            ("no_path_update", "-NoPathUpdate"),
            ("no_shell_integration", "-NoShellIntegration"),
            ("preserve_dev_role", "-PreserveDevRole"),
            ("explorer_context_menu", "-ExplorerContextMenu"),
        ):
            if current["options"][option]:
                command.append(switch)

        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            process = subprocess.Popen(
                command,
                cwd=current["source_root"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
        except OSError as exc:
            ticket_path.unlink(missing_ok=True)
            if backup_path:
                shutil.rmtree(backup_path, ignore_errors=True)
            raise ExecutionGatewayError(
                f"Could not start the authorized install helper: {exc}",
                code="system_install_process_start_failed",
            ) from exc
        try:
            return_code = process.wait()
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Could not observe the authorized install helper: {exc}",
                code="system_install_process_wait_failed",
            ) from exc
        finally:
            ticket_path.unlink(missing_ok=True)
            ticket_path.with_name(ticket_path.name + ".consumed").unlink(missing_ok=True)
        if return_code != 0:
            if current["action"] == "release-job":
                self._restore_failed_release(
                    Path(current["install_dir"]), backup_path, permit_id
                )
            raise ExecutionGatewayError(
                f"Authorized install helper exited with code {return_code}",
                code="system_install_process_failed",
            )
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "status": "completed",
            "process_id": int(getattr(process, "pid", 0) or 0),
            "backup_path": backup_path,
            "created_target": created_target,
            "operation_sha256": current["operation_sha256"],
            "receipt_id": f"system-install:{request.fingerprint}",
        }
