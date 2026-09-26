"""Operation-bound materialization of a generated Process Monitor report."""
from __future__ import annotations

import hashlib
import os
import stat
import uuid
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class ProcessMonitorGenerateEffectAdapter:
    effect_ids = frozenset({"monitor.generate"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
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
            or provenance.get("channel") != "cli"
        ):
            raise ExecutionGatewayError("Monitor output requires its consumed CLI Permit", code="monitor_generate_authorization_required")

        target_data = request.target if isinstance(request.target, dict) else {}
        raw_root = str(target_data.get("project_root") or "")
        raw_path = str(target_data.get("path") or "")
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        content = arguments.get("content")
        if not raw_root or not raw_path or not isinstance(content, str):
            raise ExecutionGatewayError("Monitor output request is incomplete", code="monitor_generate_request_invalid")
        try:
            root = Path(raw_root).expanduser().resolve(strict=True)
            lexical = Path(raw_path).expanduser()
            if not lexical.is_absolute():
                raise ExecutionGatewayError("Monitor output path must be absolute", code="monitor_generate_path_invalid")
            path = Path(os.path.abspath(str(lexical)))
            relative = path.relative_to(root)
        except (OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, ExecutionGatewayError):
                raise
            raise ExecutionGatewayError("Monitor output must stay inside its selected project root", code="monitor_generate_path_out_of_scope") from exc
        if not relative.parts or relative.suffix.lower() != ".html" or any(
            part.lower() in {".git", ".env", "node_modules", ".venv", "venv", "release"}
            for part in relative.parts
        ):
            raise ExecutionGatewayError("Monitor output path is not an allowed HTML target", code="monitor_generate_path_invalid")

        for component in reversed((path, *path.parents)):
            if component == root.parent:
                break
            if not component.exists() and not component.is_symlink():
                continue
            try:
                metadata = component.lstat()
            except OSError as exc:
                raise ExecutionGatewayError("Monitor output path cannot be inspected", code="monitor_generate_preflight_failed") from exc
            if component.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise ExecutionGatewayError("Monitor output refuses linked path components", code="monitor_generate_link_forbidden")
        if path.exists() and not stat.S_ISREG(path.stat().st_mode):
            raise ExecutionGatewayError("Monitor output target must be a regular file", code="monitor_generate_target_invalid")

        prior_digest = "missing"
        if path.exists():
            try:
                prior_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ExecutionGatewayError("Monitor output target cannot be fingerprinted", code="monitor_generate_preflight_failed") from exc
        if prior_digest != str(target_data.get("expected_prior_sha256") or ""):
            raise ExecutionGatewayError("Monitor output changed after CLI authorization", code="monitor_generate_target_changed")

        encoded = content.encode("utf-8")
        if len(encoded) > 8 * 1024 * 1024 or hashlib.sha256(encoded).hexdigest() != str(target_data.get("content_sha256") or ""):
            raise ExecutionGatewayError("Monitor content changed or exceeds its size limit", code="monitor_generate_content_invalid")
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            raise ExecutionGatewayError("Could not write the authorized monitor report", code="monitor_generate_write_failed") from exc
        finally:
            temporary.unlink(missing_ok=True)

        digest = hashlib.sha256(encoded).hexdigest()
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "path": str(path),
            "content_sha256": digest,
            "receipt_id": f"monitor.generate:sha256:{digest}",
        }
