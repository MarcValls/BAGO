"""Read-only identity and safety preflight for an uninstall operation."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionGatewayError


def resolve_uninstall_python(install_root: Path) -> str:
    """Find an interpreter outside the tree that the uninstall will remove."""
    candidates = [sys.executable, shutil.which("python.exe") or "", shutil.which("python") or ""]
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).resolve()
        if candidate.is_file() and candidate != install_root and install_root not in candidate.parents:
            return str(candidate)
    raise ExecutionGatewayError(
        "No Python interpreter outside the install directory is available for uninstall",
        code="system_install_uninstall_python_unavailable",
    )


def path_has_link(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            return True
    return False


def _program_data_root() -> Path:
    override = os.environ.get("BAGO_DATA_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    root = os.environ.get("ProgramData", "").strip()
    return Path(root) if root else Path.home() / "AppData" / "Local"


def _tree_digest(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    entries = []
    for path in root.rglob("*"):
        info = path.lstat()
        if path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            raise ExecutionGatewayError(f"Install tree contains a link: {path}", code="system_install_uninstall_link_forbidden")
        if stat.S_ISREG(info.st_mode):
            entries.append(path)
    total_bytes = 0
    for path in sorted(entries, key=lambda item: item.relative_to(root).as_posix().casefold()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        total_bytes += path.stat().st_size
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest(), total_bytes


def validate_uninstall_backup_space(target: dict[str, Any]) -> None:
    backup_root = Path(str(target.get("backup_root") or ""))
    existing = backup_root
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    try:
        free_bytes = shutil.disk_usage(existing).free
    except OSError as exc:
        raise ExecutionGatewayError(f"Cannot check uninstall backup space: {exc}", code="system_install_uninstall_disk_check_failed") from exc
    required = int(target.get("tree_bytes") or 0) + 64 * 1024 * 1024
    if free_bytes < required:
        raise ExecutionGatewayError("Insufficient free space for a recoverable uninstall backup", code="system_install_uninstall_backup_space_insufficient")


def build_uninstall_target(install_dir: str, purge_state: bool) -> dict[str, Any]:
    raw = str(install_dir or "").strip()
    if not raw:
        raise ExecutionGatewayError("install_dir is required", code="system_install_uninstall_target_invalid")
    root = Path(raw).expanduser().absolute()
    if path_has_link(root) or not root.is_dir():
        raise ExecutionGatewayError("Install directory must be a regular directory without links", code="system_install_uninstall_target_invalid")
    root = root.resolve(strict=True)
    cli = root / "bago_core" / "cli.py"
    if path_has_link(cli) or not cli.is_file():
        raise ExecutionGatewayError("Install directory lacks a safe BAGO CLI entrypoint", code="system_install_uninstall_helper_invalid")
    try:
        cli_digest = hashlib.sha256(cli.read_bytes()).hexdigest()
        tree_digest, tree_bytes = _tree_digest(root)
    except OSError as exc:
        raise ExecutionGatewayError(f"Cannot fingerprint install tree: {exc}", code="system_install_uninstall_preflight_failed") from exc
    data_root = _program_data_root() / "BAGO"
    backup_root = (data_root / "backups").absolute()
    user_state_dir = (data_root / "user").absolute()
    for label, candidate in (("backup", backup_root), ("user state", user_state_dir)):
        if path_has_link(candidate):
            raise ExecutionGatewayError(f"{label} path contains a link", code="system_install_uninstall_path_link_forbidden")
        resolved = candidate.resolve(strict=False)
        if resolved == root or resolved in root.parents or root in resolved.parents:
            raise ExecutionGatewayError(f"{label} path overlaps the install tree", code="system_install_uninstall_path_overlap")
    return {
        "schema": "bago.system-install-uninstall-plan.v1",
        "install_dir": str(root),
        "cli_path": str(cli.resolve(strict=True)),
        "cli_sha256": cli_digest,
        "tree_sha256": tree_digest,
        "tree_bytes": tree_bytes,
        "backup_root": str(backup_root),
        "user_state_dir": str(user_state_dir),
        "purge_state": bool(purge_state),
    }
