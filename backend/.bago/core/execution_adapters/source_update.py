"""Strong-Permit owner for fast-forwarding one clean BAGO source checkout."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class SystemSourceUpdateEffectAdapter:
    effect_ids = frozenset({"system.source.update"})

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", timeout=1800, check=False, shell=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutionGatewayError(f"Git source update failed: {exc}", code="system_source_update_git_failed") from exc
        if result.returncode:
            raise ExecutionGatewayError(
                (result.stderr or result.stdout or "git source update failed").strip(),
                code="system_source_update_git_failed",
            )
        return result.stdout.strip()

    @classmethod
    def prepare_target(cls, source_root: str, branch: str) -> dict[str, Any]:
        raw = str(source_root or "").strip()
        branch_name = str(branch or "main").strip() or "main"
        if not raw or not branch_name or branch_name.startswith("-") or "\x00" in branch_name:
            raise ExecutionGatewayError("source_root and a valid branch are required", code="system_source_update_request_invalid")
        root = Path(raw).expanduser().absolute()
        if root.is_symlink() or not root.is_dir():
            raise ExecutionGatewayError("source_root must be a regular checkout directory", code="system_source_update_root_invalid")
        root = root.resolve(strict=True)
        if not (root / ".git").exists():
            raise ExecutionGatewayError("source_root is not a Git checkout", code="system_source_update_checkout_invalid")
        branch_now = cls._git(root, "branch", "--show-current")
        if branch_now != branch_name:
            raise ExecutionGatewayError("Checked-out branch must match the requested update branch", code="system_source_update_branch_mismatch")
        if cls._git(root, "status", "--porcelain", "--untracked-files=all"):
            raise ExecutionGatewayError("Source checkout must be clean before update approval", code="system_source_update_checkout_dirty")
        origin = cls._git(root, "remote", "get-url", "origin")
        parsed_origin = urlsplit(origin)
        ssh_identity = (
            parsed_origin.scheme in {"ssh", "git+ssh"} and parsed_origin.username == "git"
        ) or (not parsed_origin.scheme and origin.startswith("git@"))
        if parsed_origin.username and not ssh_identity:
            raise ExecutionGatewayError("Credential-bearing origin URLs are not allowed", code="system_source_update_origin_credentials")
        head = cls._git(root, "rev-parse", "HEAD")
        return {
            "schema": "bago.system-source-update-plan.v1",
            "source_root": str(root),
            "branch": branch_name,
            "expected_head": head,
            "origin_url": origin,
            "origin_sha256": hashlib.sha256(origin.encode("utf-8")).hexdigest(),
        }

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        if manager is None or str(getattr(manager, "session_id", "") or "") != request.session_id:
            raise ExecutionGatewayError("Source update requires the active SessionManager", code="system_source_update_session_mismatch")
        authorization = context.services.get("_authorization")
        proof = authorization.get("proof") if isinstance(authorization, dict) else None
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            not isinstance(authorization, dict) or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(proof, dict) or proof.get("effect_id") != request.effect_id
            or proof.get("operation_fingerprint") != request.fingerprint
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict) or provenance.get("kind") != "direct_user_interaction"
            or provenance.get("channel") != "desktop"
        ):
            raise ExecutionGatewayError("Source update requires a consumed desktop Permit for this exact operation", code="system_source_update_strong_proof_required")
        target = self.prepare_target(str(request.target.get("source_root") or ""), str(request.target.get("branch") or ""))
        if target != request.target:
            raise ExecutionGatewayError("Source checkout changed after approval", code="system_source_update_target_changed")
        root = Path(target["source_root"])
        stdout = self._git(root, "pull", "--ff-only", "origin", target["branch"])
        resulting_head = self._git(root, "rev-parse", "HEAD")
        return {
            "ok": True, "executed": True, "effect_id": request.effect_id,
            "source_root": str(root), "branch": target["branch"],
            "previous_head": target["expected_head"], "head": resulting_head,
            "stdout": stdout[-65536:], "receipt_id": f"system-source-update:{request.fingerprint}",
        }
