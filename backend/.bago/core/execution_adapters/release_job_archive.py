"""Explicit, operation-bound archival of terminal release jobs."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from release_job_paths import release_job_archive_directory, release_job_file, release_jobs_root


class ReleaseJobArchiveEffectAdapter:
    effect_ids = frozenset({"release.job.archive"})
    _TERMINAL = frozenset({"ready", "completed", "cancelled", "failed", "rolled-back"})

    @staticmethod
    def state_path(job_id: str) -> Path:
        try:
            return release_job_file(job_id, "jobs", ".json")
        except ValueError as exc:
            raise ExecutionGatewayError(str(exc), code="release_job_archive_target_invalid") from exc

    @staticmethod
    def _reject_links(path: Path, stop: Path) -> None:
        current = path
        while True:
            if current.is_symlink():
                raise ExecutionGatewayError("Release-job archive cannot traverse symlinks", code="release_job_archive_symlink")
            if current == stop:
                return
            current = current.parent

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        proof = authorization.get("proof", {}) if isinstance(authorization, dict) else {}
        decision = authorization.get("decision", {}) if isinstance(authorization, dict) else {}
        provenance = proof.get("provenance", {}) if isinstance(proof, dict) else {}
        if (
            not isinstance(authorization, dict)
            or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(decision, dict)
            or decision.get("result") != "allow"
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
        ):
            raise ExecutionGatewayError("Release-job archival requires a consumed user Permit", code="release_job_archive_authorization_required")
        target = request.target if isinstance(request.target, dict) else {}
        job_id = str(target.get("job_id") or "")
        try:
            state_path = self.state_path(job_id)
            log_path = release_job_file(job_id, "logs", ".jsonl")
            archive_dir = release_job_archive_directory(job_id)
            root = release_jobs_root()
            staging_path = root / "staging" / job_id
        except ValueError as exc:
            raise ExecutionGatewayError(str(exc), code="release_job_archive_target_invalid") from exc

        for path, boundary in ((state_path, root), (log_path, root), (staging_path, root), (archive_dir, root)):
            self._reject_links(path, boundary)
        if not state_path.is_file():
            raise ExecutionGatewayError("Persisted release job does not exist", code="release_job_archive_missing")
        encoded_state = state_path.read_bytes()
        digest = hashlib.sha256(encoded_state).hexdigest()
        if digest != str(target.get("state_sha256") or ""):
            raise ExecutionGatewayError("Release job changed after authorization", code="release_job_archive_state_changed")
        try:
            state = json.loads(encoded_state.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionGatewayError("Persisted release job is invalid", code="release_job_archive_state_invalid") from exc
        if not isinstance(state, dict) or state.get("id") != job_id or state.get("state") not in self._TERMINAL:
            raise ExecutionGatewayError("Only the exact persisted terminal job can be archived", code="release_job_archive_not_terminal")
        archived_at = str((request.arguments or {}).get("archived_at") or "")
        try:
            parsed_at = datetime.fromisoformat(archived_at.replace("Z", "+00:00"))
            if parsed_at.tzinfo is None:
                raise ValueError("timezone required")
        except ValueError as exc:
            raise ExecutionGatewayError("Archive timestamp is invalid", code="release_job_archive_timestamp_invalid") from exc
        if archive_dir.exists():
            raise ExecutionGatewayError("Release job archive already exists", code="release_job_archive_collision")

        archived_job = {**state, "state": "deleted", "deleted_at": archived_at, "archived_at": archived_at}
        moves = [(state_path, "job.active.json"), (log_path, "job.log.jsonl"), (staging_path, "staging")]
        moved: list[tuple[Path, Path]] = []
        try:
            archive_dir.mkdir(parents=True, exist_ok=False)
            manifest = archive_dir / "job.json"
            manifest.write_text(json.dumps(archived_job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            for source, name in moves:
                if source.exists():
                    destination = archive_dir / name
                    os.replace(source, destination)
                    moved.append((destination, source))
        except Exception as exc:
            rollback_failures: list[str] = []
            for source, destination in reversed(moved):
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
                except OSError as rollback_error:
                    rollback_failures.append(f"{destination.name}: {rollback_error}")
            if rollback_failures:
                raise ExecutionGatewayError(
                    f"Release job archive failed; recovery data remains at {archive_dir}: {'; '.join(rollback_failures)}",
                    code="release_job_archive_recovery_required",
                ) from exc
            shutil.rmtree(archive_dir, ignore_errors=True)
            raise ExecutionGatewayError(f"Release job archive failed before completion: {exc}", code="release_job_archive_failed") from exc
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "job_id": job_id,
            "archived_at": archived_at,
            "archive_dir": str(archive_dir),
            "receipt_id": f"release-job-archive:{job_id}:{digest}",
        }
