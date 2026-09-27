"""Server-owned signature verification for cached release-job bundles."""
from __future__ import annotations

import shutil
import subprocess
import os
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class ReleaseSignatureEffectAdapter:
    effect_ids = frozenset({"release.signature.verify"})
    server_policy_only = True

    @staticmethod
    def _paths(request: ExecutionRequest) -> tuple[Path, Path]:
        from bago_core.user_state_paths import user_root

        override = os.environ.get("BAGO_USER_ROOT", "").strip() or os.environ.get("BAGO_ROOT", "").strip()
        root = Path(override).expanduser() if override else user_root()
        cache = (root / "manager" / "release-jobs" / "cache").resolve()
        target = request.target if isinstance(request.target, dict) else {}
        paths = []
        for raw in (target.get("signature_path"), target.get("bundle_path")):
            lexical = Path(str(raw or "")).absolute()
            try:
                lexical.relative_to(cache)
            except ValueError:
                raise ExecutionGatewayError(
                    "Release signature inputs must stay inside the canonical cache",
                    code="release_signature_path_invalid",
                )
            current = lexical
            while True:
                if current.is_symlink():
                    raise ExecutionGatewayError(
                        "Release signature inputs cannot traverse symlinks",
                        code="release_signature_symlink_forbidden",
                    )
                if current == cache:
                    break
                current = current.parent
            path = lexical.resolve()
            try:
                path.relative_to(cache)
            except ValueError:
                raise ExecutionGatewayError(
                    "Release signature inputs must stay inside the canonical cache",
                    code="release_signature_path_invalid",
                )
            if not path.is_file():
                raise ExecutionGatewayError(
                    "Release signature inputs must be existing files inside the canonical cache",
                    code="release_signature_path_invalid",
                )
            paths.append(path)
        signature, bundle = paths
        if signature == bundle:
            raise ExecutionGatewayError(
                "Signature and bundle must be separate files",
                code="release_signature_inputs_invalid",
            )
        return signature, bundle

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Release signature verification requires server policy authorization",
                code="release_signature_authorization_required",
            )
        signature, bundle = self._paths(request)
        executable = shutil.which("gpg.exe") or shutil.which("gpg")
        if not executable:
            raise ExecutionGatewayError("GPG is unavailable", code="release_signature_gpg_missing")
        try:
            completed = subprocess.run(
                [executable, "--batch", "--verify", str(signature), str(bundle)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExecutionGatewayError(
                f"GPG signature verification could not complete: {exc}",
                code="release_signature_verification_failed",
            ) from exc
        if completed.returncode:
            raise ExecutionGatewayError(
                completed.stderr.strip() or "Release signature is invalid",
                code="release_signature_invalid",
            )
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "status": "verified",
            "signature_path": str(signature),
            "bundle_path": str(bundle),
            "receipt_id": f"release-signature:{request.fingerprint}",
        }
