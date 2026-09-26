"""Safely stage a verified release ZIP inside the canonical release-job area."""
from __future__ import annotations

import os
import re
import shutil
import stat
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class ReleaseBundleStageEffectAdapter:
    effect_ids = frozenset({"release.bundle.stage"})
    server_policy_only = True
    _MAX_ENTRIES = 250_000
    _MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024

    @staticmethod
    def _roots() -> tuple[Path, Path]:
        import os
        from bago_core.user_state_paths import user_root

        override = os.environ.get("BAGO_USER_ROOT", "").strip() or os.environ.get("BAGO_ROOT", "").strip()
        root = Path(override).expanduser() if override else user_root()
        base = (root / "manager" / "release-jobs").resolve()
        return base / "cache", base / "staging"

    @staticmethod
    def _reject_links(path: Path, stop: Path) -> None:
        current = path
        while True:
            if current.is_symlink():
                raise ExecutionGatewayError(
                    "Release staging path cannot traverse symlinks",
                    code="release_stage_symlink_forbidden",
                )
            if current == stop:
                break
            current = current.parent

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Release bundle staging requires server policy authorization",
                code="release_stage_authorization_required",
            )
        target = request.target if isinstance(request.target, dict) else {}
        cache, staging = self._roots()
        bundle = Path(str(target.get("bundle_path") or "")).absolute()
        job_id = str(target.get("job_id") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,179}", job_id):
            raise ExecutionGatewayError("Release job id is invalid", code="release_stage_job_id_invalid")
        try:
            bundle.relative_to(cache)
        except ValueError as exc:
            raise ExecutionGatewayError("Release bundle must be inside the canonical cache", code="release_stage_path_invalid") from exc
        self._reject_links(bundle, cache)
        bundle = bundle.resolve()
        if not bundle.is_file():
            raise ExecutionGatewayError("Release bundle does not exist", code="release_stage_bundle_missing")

        destination = staging / job_id
        self._reject_links(destination, staging)
        temp = staging / f".{job_id}.{uuid.uuid4().hex}.tmp"
        backup = staging / f".{job_id}.{uuid.uuid4().hex}.bak"
        expanded = 0
        entries: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        try:
            with zipfile.ZipFile(bundle, "r") as archive:
                infos = archive.infolist()
                if len(infos) > self._MAX_ENTRIES:
                    raise ExecutionGatewayError("Release archive has too many entries", code="release_stage_entry_limit")
                seen: dict[str, bool] = {}
                for info in infos:
                    name = info.filename.replace("\\", "/")
                    relative = PurePosixPath(name)
                    mode = (info.external_attr >> 16) & 0xFFFF
                    if (relative.is_absolute() or not relative.parts or ".." in relative.parts
                            or ":" in relative.parts[0] or stat.S_ISLNK(mode)):
                        raise ExecutionGatewayError("Release archive contains an unsafe path or link", code="release_stage_entry_invalid")
                    normalized = "/".join(part for part in relative.parts if part not in ("", "."))
                    key = normalized.casefold().rstrip("/")
                    is_dir = info.is_dir()
                    if not key or key in seen:
                        raise ExecutionGatewayError("Release archive contains duplicate paths", code="release_stage_duplicate_entry")
                    parts = key.split("/")
                    for index in range(1, len(parts)):
                        ancestor = "/".join(parts[:index])
                        if ancestor in seen and not seen[ancestor]:
                            raise ExecutionGatewayError("Release archive contains a file/directory collision", code="release_stage_entry_conflict")
                    if not is_dir and any(existing.startswith(key + "/") for existing in seen):
                        raise ExecutionGatewayError("Release archive contains a file/directory collision", code="release_stage_entry_conflict")
                    seen[key] = is_dir
                    expanded += info.file_size
                    if expanded > self._MAX_EXPANDED_BYTES:
                        raise ExecutionGatewayError("Release archive exceeds the expanded-size limit", code="release_stage_size_limit")
                    entries.append((info, PurePosixPath(normalized)))
        except zipfile.BadZipFile as exc:
            raise ExecutionGatewayError("Release bundle is not a valid ZIP archive", code="release_stage_zip_invalid") from exc

        try:
            staging.mkdir(parents=True, exist_ok=True)
            temp.mkdir()
            with zipfile.ZipFile(bundle, "r") as archive:
                for info, relative in entries:
                    output = temp.joinpath(*relative.parts)
                    if info.is_dir():
                        output.mkdir(parents=True, exist_ok=True)
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as source, output.open("xb") as sink:
                        shutil.copyfileobj(source, sink, length=1024 * 1024)

            if destination.exists():
                if destination.is_symlink() or not destination.is_dir():
                    raise ExecutionGatewayError("Release staging target is not a safe directory", code="release_stage_target_invalid")
                os.replace(destination, backup)
            try:
                os.replace(temp, destination)
            except Exception:
                if backup.exists() and not destination.exists():
                    os.replace(backup, destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            if temp.exists():
                shutil.rmtree(temp, ignore_errors=True)
            if backup.exists() and destination.exists():
                shutil.rmtree(backup, ignore_errors=True)

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "staging_path": str(destination),
            "entries": len(entries),
            "expanded_bytes": expanded,
            "receipt_id": f"release-stage:{request.fingerprint}",
        }
