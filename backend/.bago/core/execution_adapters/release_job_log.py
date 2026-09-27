"""Policy adapter for bounded append-only release-job log records."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from release_job_paths import release_job_file


class ReleaseJobLogEffectAdapter:
    effect_ids = frozenset({"release.job.log.append"})
    server_policy_only = True
    _LEVELS = frozenset({"info", "warn", "error"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError("Release-job logging requires server policy authorization", code="release_job_log_authorization_required")
        job_id = str((request.target or {}).get("job_id") or "")
        record = (request.arguments or {}).get("record") if isinstance(request.arguments, dict) else None
        if not isinstance(record, dict) or record.get("level") not in self._LEVELS:
            raise ExecutionGatewayError("Release-job log record is invalid", code="release_job_log_record_invalid")
        clean = {
            "timestamp": str(record.get("timestamp") or "")[:40],
            "level": record["level"],
            "message": str(record.get("message") or "").replace("\r", " ").replace("\n", " ")[:8192],
        }
        try:
            encoded = (json.dumps(clean, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            target = release_job_file(job_id, "logs", ".jsonl")
        except (TypeError, ValueError) as exc:
            raise ExecutionGatewayError(str(exc), code="release_job_log_target_invalid") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as stream:
            stream.write(encoded)
            stream.flush()
        digest = hashlib.sha256(encoded).hexdigest()
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "path": str(target),
            "bytes_written": len(encoded),
            "sha256": digest,
            "receipt_id": f"release-job-log:{job_id}:{digest}",
        }
