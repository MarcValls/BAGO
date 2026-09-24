"""Trusted filesystem effect implementation for :mod:`execution_gateway`.

Only the gateway-owned filesystem adapter may call ``write_text`` for a
runtime effect.  HTTP handlers and plan orchestration validate and authorize
requests, but they do not perform the material write themselves.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any


WRITE_FORBIDDEN = frozenset({
    ".git",
    ".env",
    "state",
    "dist",
    "release",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
})


class FilesystemEffectError(RuntimeError):
    """Fail-closed filesystem validation or write error."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _resolve_write_root(manager: Any) -> Path:
    """Resolve the explicit project authority used for a write."""

    temp_root = Path(tempfile.gettempdir()).resolve()
    appdata = Path(os.environ["APPDATA"]).resolve() if os.environ.get("APPDATA") else None
    localappdata = Path(os.environ["LOCALAPPDATA"]).resolve() if os.environ.get("LOCALAPPDATA") else None

    def is_runtime_path(path: Path) -> bool:
        for root in (temp_root, appdata, localappdata):
            if root is None:
                continue
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    for attr in ("project_root", "workspace_scope_root"):
        value = getattr(manager, attr, None)
        if value:
            path = Path(str(value)).resolve()
            if path.exists():
                return path

    for attr in ("workspace_mirror_root", "base_path"):
        value = getattr(manager, attr, None)
        if value:
            path = Path(str(value)).resolve()
            if path.exists() and not is_runtime_path(path):
                return path
    return Path.cwd().resolve()


def _resolve_target(manager: Any, raw_path: str) -> tuple[Path, Path, Path]:
    """Return ``(target, scope_root, write_root)`` after scope validation."""

    from handlers_files import _resolve_namespaced_target, _workspace_root

    clean = str(raw_path or "").strip()
    if not clean:
        raise FilesystemEffectError("path vacío", code="filesystem_path_required")

    normalized = clean.replace("\\", "/").lower()
    if any(segment.lower() in normalized.split("/") for segment in WRITE_FORBIDDEN):
        raise FilesystemEffectError(
            f"Ruta no permitida: {clean}",
            code="filesystem_forbidden_path",
        )

    write_root = _resolve_write_root(manager)
    first_segment = clean.replace("\\", "/").split("/", 1)[0].lower()
    if first_segment in {"workspace", "source"}:
        target_root, relative = _resolve_namespaced_target(manager, clean)
        if target_root != _workspace_root(manager):
            raise FilesystemEffectError(
                "Solo se puede escribir en el workspace principal.",
                code="filesystem_source_write_forbidden",
            )
        target = (target_root / relative).resolve()
        scope_root = target_root
    else:
        candidate = Path(clean)
        target = (write_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        scope_root = write_root

    try:
        target.relative_to(scope_root)
    except ValueError as exc:
        raise FilesystemEffectError(
            "La ruta está fuera del proyecto activo.",
            code="filesystem_path_out_of_scope",
        ) from exc
    return target, scope_root, write_root


def write_file_effect(manager: Any, raw_path: str, content: str) -> dict[str, Any]:
    """Apply one already-authorized workspace write and return its receipt."""

    target, scope_root, write_root = _resolve_target(manager, raw_path)
    existed = target.exists()
    payload = str(content).encode("utf-8")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not (target.is_file() and target.read_bytes() == payload):
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.bago-{uuid.uuid4().hex}.",
                suffix=".tmp",
                dir=target.parent,
            )
            try:
                with os.fdopen(descriptor, "wb") as temporary:
                    temporary.write(payload)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_name, target)
                if os.name != "nt":
                    directory_fd = os.open(target.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
            finally:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        raise FilesystemEffectError(
            f"Error escribiendo archivo: {exc}",
            code="filesystem_write_failed",
        ) from exc

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    receipt_id = "filesystem-write:sha256:" + hashlib.sha256(
        f"{target}|{digest}".encode("utf-8")
    ).hexdigest()
    try:
        relative = str(target.relative_to(write_root)).replace("\\", "/")
    except ValueError:
        relative = str(target)
    return {
        "ok": True,
        "executed": True,
        "effect_id": "filesystem.write",
        "path": relative,
        "absolute_path": str(target),
        "project_root": str(scope_root),
        "created": not existed,
        "overwritten": existed,
        "bytes_written": len(payload),
        "evidence": [f"file_sha256:{digest}", f"path:{target}"],
        "receipt_id": receipt_id,
    }


def read_file_effect(manager: Any, raw_path: str) -> dict[str, Any]:
    """Read one scoped file for a governed plan child effect."""

    clean = str(raw_path or "").strip()
    if not clean:
        raise FilesystemEffectError("path vacío", code="filesystem_path_required")
    normalized = clean.replace("\\", "/").lower()
    if any(segment.lower() in normalized.split("/") for segment in WRITE_FORBIDDEN):
        raise FilesystemEffectError(
            f"Ruta no permitida: {clean}",
            code="filesystem_forbidden_path",
        )
    target = resolve_plan_read_path(manager, clean)
    if not target.exists():
        raise FilesystemEffectError(
            f"No existe: {clean}",
            code="filesystem_read_missing",
        )
    if not target.is_file():
        raise FilesystemEffectError(
            f"No es un archivo: {clean}",
            code="filesystem_read_not_file",
        )
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "ok": True,
        "executed": True,
        "effect_id": "filesystem.read",
        "result": raw.decode("utf-8", errors="replace")[:500],
        "path": str(target),
        "evidence": [f"file_sha256:{digest}", f"path:{target}"],
        "receipt_id": f"filesystem-read:sha256:{digest}",
    }


def resolve_plan_read_path(manager: Any, raw_path: str) -> Path:
    """Resolve a plan read to its manager base without permitting escapes."""

    from pathlib import PurePosixPath

    base = Path(getattr(manager, "base_path", Path.cwd())).resolve()
    normalized = str(raw_path or "").strip()
    if normalized.startswith("/"):
        parts = [
            part
            for part in PurePosixPath(normalized).parts
            if part not in {"/", "home", "tmp", "etc", "var", "usr", "opt", "root", "Users"}
        ]
        normalized = str(Path(*parts)) if parts else Path(normalized).name
    if len(normalized) >= 2 and normalized[1] == ":":
        normalized = normalized[2:].lstrip("/\\")
    for prefix in ("home/user/", "home/admin/", "Users/user/", "Documents/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    candidate = (base / normalized).resolve() if normalized else base
    if base in candidate.parents or candidate == base:
        return candidate
    return (base / Path(raw_path).name).resolve()


__all__ = [
    "FilesystemEffectError",
    "WRITE_FORBIDDEN",
    "read_file_effect",
    "resolve_plan_read_path",
    "write_file_effect",
]
