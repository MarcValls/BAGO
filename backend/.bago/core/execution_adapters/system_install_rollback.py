"""Strong-Permit owner for restoring one release-job installation."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class SystemInstallRollbackEffectAdapter:
    effect_ids = frozenset({"system.install.rollback"})

    @staticmethod
    def _execute_rollback(request: ExecutionRequest) -> dict[str, Any]:
        target_data = request.target
        target_raw = str(target_data.get("install_dir") or "")
        backup_raw = str(target_data.get("backup_path") or "")
        displaced_raw = str(target_data.get("displaced_path") or "")
        if not os.path.isabs(target_raw) or not os.path.isabs(displaced_raw) or (backup_raw and not os.path.isabs(backup_raw)):
            raise ExecutionGatewayError("Rollback paths must be absolute", code="system_install_rollback_path_invalid")
        target = Path(os.path.abspath(target_raw))
        displaced = Path(os.path.abspath(displaced_raw))
        backup = Path(os.path.abspath(backup_raw)) if backup_raw else None
        if displaced.parent != target.parent or not re.fullmatch(re.escape(target.name) + r"\.bago-(?:failed|replaced)-[A-Za-z0-9._-]+", displaced.name):
            raise ExecutionGatewayError("Rollback preservation path is outside the install target", code="system_install_rollback_path_invalid")
        if backup and (backup.parent != target.parent or not re.fullmatch(re.escape(target.name) + r"\.bago-rollback-permit-[A-Za-z0-9-]+", backup.name)):
            raise ExecutionGatewayError("Rollback backup path is not a gateway release backup", code="system_install_rollback_path_invalid")

        for candidate in (target, displaced, backup):
            if candidate is None:
                continue
            for component in (candidate, *candidate.parents):
                if not component.exists() and not component.is_symlink():
                    continue
                try:
                    metadata = component.lstat()
                except OSError as exc:
                    raise ExecutionGatewayError(f"Could not inspect rollback path {component}: {exc}", code="system_install_rollback_preflight_failed") from exc
                if component.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                    raise ExecutionGatewayError(f"Rollback refuses linked path component {component}", code="system_install_rollback_link_forbidden")
        if target.exists() and not target.is_dir():
            raise ExecutionGatewayError("Rollback target must be a directory", code="system_install_rollback_target_invalid")
        if displaced.exists() and not displaced.is_dir():
            raise ExecutionGatewayError("Rollback preservation target must be a directory", code="system_install_rollback_target_invalid")
        if backup and backup.exists() and not backup.is_dir():
            raise ExecutionGatewayError("Rollback backup must be a directory", code="system_install_rollback_target_invalid")

        if target.exists():
            if displaced.exists():
                if backup and not backup.exists() and target.exists():
                    return {
                        "ok": True, "executed": True, "effect_id": request.effect_id,
                        "status": "completed", "restored": False, "already_completed": True,
                        "preserved_path": str(displaced), "receipt_id": f"install-rollback:{request.fingerprint}",
                    }
                raise ExecutionGatewayError("Rollback is blocked because recoverable data already exists", code="system_install_rollback_collision")
            os.replace(target, displaced)
        if backup and backup.exists():
            if target.exists():
                raise ExecutionGatewayError("Rollback destination and backup coexist", code="system_install_rollback_collision")
            try:
                os.replace(backup, target)
            except OSError as exc:
                if displaced.exists() and not target.exists():
                    os.replace(displaced, target)
                raise ExecutionGatewayError(f"Could not restore release backup: {exc}", code="system_install_rollback_restore_failed") from exc
        elif backup and not target.exists():
            raise ExecutionGatewayError("Rollback backup is missing", code="system_install_rollback_backup_missing")
        elif not displaced.exists():
            raise ExecutionGatewayError("Neither install target nor recoverable data exists", code="system_install_rollback_data_missing")

        return {
            "ok": True, "executed": True, "effect_id": request.effect_id,
            "status": "completed", "restored": bool(backup),
            "preserved_path": str(displaced), "receipt_id": f"install-rollback:{request.fingerprint}",
        }

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        if manager is None or str(getattr(manager, "session_id", "") or "") != request.session_id:
            raise ExecutionGatewayError("System install rollback requires the active SessionManager", code="system_install_session_mismatch")
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
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
            or provenance.get("channel") not in {"ui-react", "desktop"}
        ):
            raise ExecutionGatewayError("System install rollback must use its consumed ExecutionGateway Permit", code="system_install_gateway_context_required")
        return self._execute_rollback(request)
