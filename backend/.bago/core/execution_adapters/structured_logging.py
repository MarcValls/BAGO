"""Server-owned writer and rotator for the canonical bridge log."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import logs_root
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class StructuredLoggingEffectAdapter:
    effect_ids = frozenset({"logging.append"})
    server_policy_only = True
    _lock = threading.RLock()
    _MAX_BACKUPS = 10

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError("Structured logging requires server policy authorization", code="structured_log_authorization_required")

        root = logs_root().expanduser().resolve()
        target = root / "bridge.jsonl"
        declared_root = str((request.target or {}).get("allowed_root") or "")
        declared_target = str((request.target or {}).get("path") or "")
        if declared_root != str(root) or declared_target != str(target) or str((request.target or {}).get("operation") or "") != "append_rotate":
            raise ExecutionGatewayError("Structured log target is not canonical", code="structured_log_target_invalid")
        if target.exists() and target.is_symlink():
            raise ExecutionGatewayError("Structured log cannot be a symlink", code="structured_log_symlink_forbidden")

        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        content = str(arguments.get("content") or "")
        try:
            encoded = content.encode("utf-8")
            max_bytes = int(arguments.get("max_bytes", 5 * 1024 * 1024))
            backup_count = int(arguments.get("backup_count", 3))
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ExecutionGatewayError("Structured log request is invalid", code="structured_log_request_invalid") from exc
        if not encoded.endswith(b"\n") or len(encoded) > 65536 or not 1 <= max_bytes <= 1024 * 1024 * 1024 or not 1 <= backup_count <= self._MAX_BACKUPS:
            raise ExecutionGatewayError("Structured log bounds are invalid", code="structured_log_request_invalid")
        try:
            if not isinstance(json.loads(encoded.decode("utf-8")), dict):
                raise ValueError("log record must be an object")
        except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionGatewayError("Structured log record must be one JSON object", code="structured_log_record_invalid") from exc

        try:
            with self._lock:
                root.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.stat().st_size >= max_bytes:
                    for index in range(backup_count - 1, 0, -1):
                        source = root / f"bridge.{index}.jsonl"
                        destination = root / f"bridge.{index + 1}.jsonl"
                        if source.exists():
                            if destination.exists():
                                destination.unlink()
                            os.replace(source, destination)
                    if target.exists():
                        os.replace(target, root / "bridge.1.jsonl")
                with target.open("ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
        except OSError as exc:
            raise ExecutionGatewayError(f"Structured log write failed: {exc}", code="structured_log_write_failed") from exc

        digest = hashlib.sha256(encoded).hexdigest()
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "path": str(target),
            "bytes_written": len(encoded),
            "sha256": digest,
            "receipt_id": f"structured-log:sha256:{digest}",
        }
