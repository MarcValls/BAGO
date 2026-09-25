"""Materialize authorized workspace patch batches and recover their snapshots.

Only ProjectWriteEffectAdapter calls this module. Request construction and
interactive authorization remain at the API/caller boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from bago_core.codegen.patch_parser import Patch, PatchParseError, parse_patch


FORBIDDEN = frozenset({".git", ".env", "state", "dist", "release", "__pycache__", ".bago", "node_modules", ".venv", "venv"})
MAX_PATCHES = 32
MANIFEST = "patch-receipt.v1.json"


class WorkspacePatchError(ValueError):
    def __init__(self, message: str, *, code: str = "workspace_patch_invalid") -> None:
        super().__init__(message)
        self.code = code


def _is_link(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _relative_path(raw: str) -> str:
    clean = str(raw or "").replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    parts = clean.split("/")
    if not clean or clean.startswith("/") or re.match(r"^[A-Za-z]:", clean) or any(p in {"", ".", ".."} for p in parts):
        raise WorkspacePatchError("Patch path must be a normalized workspace-relative file", code="workspace_patch_path_invalid")
    if any(part.lower() in FORBIDDEN for part in parts):
        raise WorkspacePatchError("Patch path contains a forbidden workspace segment", code="workspace_patch_forbidden_path")
    return "/".join(parts)


def _target(workspace: Path, relative: str) -> Path:
    result = workspace
    for part in relative.split("/"):
        result = result / part
        if _is_link(result):
            raise WorkspacePatchError("Patch path cannot traverse links or reparse points", code="workspace_patch_link_forbidden")
    resolved = result.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise WorkspacePatchError("Patch path escapes the authorized workspace", code="workspace_patch_out_of_scope") from exc
    if resolved.exists() and not resolved.is_file():
        raise WorkspacePatchError("Patch target must be a regular file", code="workspace_patch_target_invalid")
    return resolved


def parse_diffs(diffs: Any) -> tuple[Patch, ...]:
    if not isinstance(diffs, list) or not diffs or len(diffs) > MAX_PATCHES:
        raise WorkspacePatchError(f"Expected 1 to {MAX_PATCHES} unified diffs", code="workspace_patch_batch_invalid")
    parsed: list[Patch] = []
    for raw in diffs:
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 1_048_576:
            raise WorkspacePatchError("Unified diff is invalid or exceeds 1 MiB", code="workspace_patch_size_invalid")
        try:
            patch = parse_patch(raw)
        except PatchParseError as exc:
            raise WorkspacePatchError(str(exc), code="workspace_patch_parse_failed") from exc
        old_path = _relative_path(patch.old_path)
        new_path = _relative_path(patch.new_path)
        if old_path != new_path:
            raise WorkspacePatchError("File moves and deletions require a separate authorized operation", code="workspace_patch_rename_forbidden")
        parsed.append(patch)
    if len({patch.new_path for patch in parsed}) != len(parsed):
        raise WorkspacePatchError("A patch batch cannot target the same file twice", code="workspace_patch_duplicate_target")
    return tuple(parsed)


def _reconstruct(old_body: str, patch: Patch) -> str:
    lines = old_body.splitlines(keepends=False) if old_body else []
    for hunk in patch.hunks:
        index = max(0, hunk.old_start - 1)
        for line in hunk.lines:
            if line.marker == " ":
                if index >= len(lines) or lines[index] != line.text:
                    raise WorkspacePatchError(f"Patch context mismatch at line {hunk.old_start}", code="workspace_patch_context_mismatch")
                index += 1
            elif line.marker == "-":
                if index >= len(lines) or lines[index] != line.text:
                    raise WorkspacePatchError(f"Patch deletion mismatch at line {hunk.old_start}", code="workspace_patch_context_mismatch")
                del lines[index]
            elif line.marker == "+":
                lines.insert(index, line.text)
                index += 1
    result = "\n".join(lines)
    if lines and old_body.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def _prepare(workspace: Path, diffs: Any) -> list[dict[str, Any]]:
    if not workspace.is_dir():
        raise WorkspacePatchError("Authorized workspace does not exist", code="workspace_patch_workspace_missing")
    rows: list[dict[str, Any]] = []
    for patch in parse_diffs(diffs):
        relative = _relative_path(patch.new_path)
        target = _target(workspace, relative)
        try:
            old = target.read_text(encoding="utf-8") if target.exists() else ""
        except UnicodeDecodeError as exc:
            raise WorkspacePatchError("Binary patch targets are not supported", code="workspace_patch_binary_file") from exc
        except OSError as exc:
            raise WorkspacePatchError(f"Could not read patch target: {exc}", code="workspace_patch_read_failed") from exc
        new = _reconstruct(old, patch)
        rows.append({
            "path": relative,
            "existed": target.exists(),
            "before_sha256": _sha(old.encode("utf-8")),
            "after_sha256": _sha(new.encode("utf-8")),
            "bytes_written": len(new.encode("utf-8")),
            "new_text": new,
            "old_text": old,
        })
    return rows


def describe_patch(workspace_root: str | Path, diffs: Any) -> dict[str, Any]:
    workspace = Path(workspace_root).expanduser().resolve()
    rows = _prepare(workspace, diffs)
    entries = [{key: row[key] for key in ("path", "existed", "before_sha256", "after_sha256")} for row in rows]
    return {"workspace": str(workspace), "entries": entries}


def apply_patch(workspace_root: str | Path, diffs: Any, expected_descriptor: str) -> dict[str, Any]:
    workspace = Path(workspace_root).expanduser().resolve()
    rows = _prepare(workspace, diffs)
    descriptor = {"workspace": str(workspace), "entries": [{key: row[key] for key in ("path", "existed", "before_sha256", "after_sha256")} for row in rows]}
    encoded_descriptor = json.dumps(descriptor, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if _sha(encoded_descriptor) != expected_descriptor:
        raise WorkspacePatchError("Patch targets changed after authorization", code="workspace_patch_target_changed")
    bago = workspace / ".bago"
    snapshots = bago / "snapshots"
    if _is_link(bago) or _is_link(snapshots):
        raise WorkspacePatchError("Patch snapshot root cannot be linked", code="workspace_patch_snapshot_link_forbidden")
    snapshot = snapshots / f"{int(time.time() * 1000)}_{uuid.uuid4().hex}.bago-snap"
    changed: list[dict[str, Any]] = []
    try:
        snapshot.mkdir(parents=True, exist_ok=False)
        for row in rows:
            backup = snapshot / row["path"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(row["old_text"], encoding="utf-8")
        manifest = {"contract": "bago.workspace-patch-snapshot.v1", "workspace": str(workspace), "entries": descriptor["entries"]}
        (snapshot / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        for row in rows:
            target = _target(workspace, row["path"])
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                temporary.write_text(row["new_text"], encoding="utf-8", newline="\n")
                os.replace(temporary, target)
                changed.append(row)
            finally:
                temporary.unlink(missing_ok=True)
    except Exception as exc:
        rollback_errors: list[str] = []
        for row in reversed(changed):
            try:
                target = _target(workspace, row["path"])
                if row["existed"]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(row["old_text"], encoding="utf-8", newline="\n")
                else:
                    target.unlink(missing_ok=True)
            except OSError as rollback_exc:
                rollback_errors.append(f"{row['path']}: {rollback_exc}")
        if not rollback_errors:
            shutil.rmtree(snapshot, ignore_errors=True)
        else:
            raise WorkspacePatchError(
                "Patch application failed and recovery snapshot was preserved: " + "; ".join(rollback_errors),
                code="workspace_patch_rollback_failed",
            ) from exc
        if isinstance(exc, WorkspacePatchError):
            raise
        raise WorkspacePatchError(f"Patch application failed and was rolled back: {exc}", code="workspace_patch_apply_failed") from exc
    return {"snapshot": str(snapshot), "applied": [{key: row[key] for key in ("path", "before_sha256", "after_sha256")} for row in rows]}


def describe_rollback(workspace_root: str | Path, snapshot_path: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_root).expanduser().resolve()
    snapshot = Path(snapshot_path).expanduser()
    snapshots = workspace / ".bago" / "snapshots"
    bago = workspace / ".bago"
    if _is_link(snapshot) or _is_link(bago) or _is_link(snapshots):
        raise WorkspacePatchError("Patch snapshot cannot be linked", code="workspace_patch_snapshot_link_forbidden")
    try:
        resolved_snapshots = snapshots.resolve(strict=True)
        snapshot = snapshot.resolve(strict=True)
        snapshot.relative_to(resolved_snapshots)
        manifest_path = snapshot / MANIFEST
        if _is_link(manifest_path):
            raise WorkspacePatchError("Patch snapshot manifest cannot be linked", code="workspace_patch_snapshot_invalid")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise WorkspacePatchError(f"Patch snapshot is invalid: {exc}", code="workspace_patch_snapshot_invalid") from exc
    if manifest.get("contract") != "bago.workspace-patch-snapshot.v1" or manifest.get("workspace") != str(workspace):
        raise WorkspacePatchError("Patch snapshot belongs to another workspace", code="workspace_patch_snapshot_mismatch")
    return {"workspace": str(workspace), "snapshot": str(snapshot), "entries": manifest.get("entries", [])}


def rollback_patch(workspace_root: str | Path, snapshot_path: str | Path, expected_descriptor: str) -> dict[str, Any]:
    workspace = Path(workspace_root).expanduser().resolve()
    snapshot = Path(snapshot_path).expanduser()
    descriptor = describe_rollback(workspace, snapshot)
    snapshot = Path(descriptor["snapshot"])
    encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if _sha(encoded) != expected_descriptor:
        raise WorkspacePatchError("Patch snapshot changed after authorization", code="workspace_patch_snapshot_changed")
    rows: list[tuple[dict[str, Any], Path, str, bool]] = []
    for item in descriptor.get("entries", []):
        relative = _relative_path(item.get("path", ""))
        target = _target(workspace, relative)
        target_exists = target.exists()
        current = target.read_bytes() if target_exists else b""
        matches_after = target_exists and _sha(current) == item.get("after_sha256")
        matches_before = target_exists == bool(item.get("existed")) and (
            _sha(current) == item.get("before_sha256") if target_exists else True
        )
        if not matches_after and not matches_before:
            raise WorkspacePatchError(f"Patch target changed after apply: {relative}", code="workspace_patch_rollback_target_changed")
        if not matches_after:
            rows.append((item, target, "", False))
            continue
        lexical_backup = snapshot / relative
        current = lexical_backup
        while current != snapshot:
            if _is_link(current):
                raise WorkspacePatchError("Snapshot entries cannot be links", code="workspace_patch_snapshot_invalid")
            current = current.parent
        backup = lexical_backup.resolve(strict=True)
        try:
            backup.relative_to(snapshot)
        except ValueError as exc:
            raise WorkspacePatchError("Snapshot entry escaped its root", code="workspace_patch_snapshot_invalid") from exc
        old = backup.read_text(encoding="utf-8")
        if _sha(old.encode("utf-8")) != item.get("before_sha256"):
            raise WorkspacePatchError(f"Snapshot content digest mismatch: {relative}", code="workspace_patch_snapshot_digest_mismatch")
        rows.append((item, target, old, True))
    restored: list[str] = []
    try:
        for item, target, old, should_restore in rows:
            if not should_restore:
                continue
            if item["existed"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(old, encoding="utf-8", newline="\n")
            else:
                target.unlink(missing_ok=True)
            restored.append(item["path"])
    except OSError as exc:
        raise WorkspacePatchError(f"Patch rollback is incomplete: {exc}", code="workspace_patch_rollback_failed") from exc
    return {"snapshot": str(snapshot), "restored": restored}
