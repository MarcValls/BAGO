"""Policy adapter for durable release-job JSON state."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from release_job_paths import release_job_file


class ReleaseJobStateEffectAdapter:
    effect_ids = frozenset({"release.job.persist"})
    server_policy_only = True

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError("Release-job persistence requires server policy authorization", code="release_job_authorization_required")
        job_id = str((request.target or {}).get("job_id") or "")
        state = (request.arguments or {}).get("state") if isinstance(request.arguments, dict) else None
        if not isinstance(state, dict) or str(state.get("id") or "") != job_id:
            raise ExecutionGatewayError("Release-job state identity does not match its target", code="release_job_state_identity_mismatch")
        try:
            encoded = (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            target = release_job_file(job_id, "jobs", ".json")
        except (TypeError, ValueError) as exc:
            raise ExecutionGatewayError(str(exc), code="release_job_state_invalid") from exc
        if len(encoded) > 1024 * 1024:
            raise ExecutionGatewayError("Release-job state exceeds the storage limit", code="release_job_state_too_large")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{job_id}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        digest = hashlib.sha256(encoded).hexdigest()
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "path": str(target),
            "sha256": digest,
            "receipt_id": f"release-job-state:{job_id}:{digest}",
        }
