"""Canonical identity for a prepared BAGO installation operation.

This module is pure planning: it reads and hashes inputs but performs no
installation, elevation, network, or persistent configuration effects. API
handlers and the installer gateway adapter share this contract so a Permit
cannot authorize a path while leaving the staged bundle or chosen operation
unbound.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class InstallPlanError(ValueError):
    """Raised when an install operation cannot be given a stable identity."""


_ALLOWED_MODES = frozenset({"Express", "Advanced"})
_ALLOWED_ACTIONS = frozenset({"install", "repair", "reinstall", "new-copy", "source-update", "release-job"})
_ALLOWED_OPTIONS = frozenset({
    "skip_tests", "no_path_update", "no_shell_integration",
    "preserve_dev_role", "explorer_context_menu",
})
_PROVIDER_FIELDS = {
    "ollama-local": frozenset({"enabled", "base_url", "model"}),
    "codex": frozenset({"enabled", "base_url", "api_key", "model"}),
    "copilot": frozenset({"enabled", "base_url", "api_key", "auth_mode", "model"}),
    "ollama-cloud": frozenset({"enabled", "base_url", "api_key", "auth_mode", "model"}),
}


def validate_install_configuration(configuration: dict[str, Any]) -> None:
    """Validate the complete guided configuration before requesting approval."""
    if not isinstance(configuration, dict) or set(configuration) != {"providers", "knowledge", "credential_store"}:
        raise InstallPlanError("configuration must contain providers, knowledge, and credential_store")
    providers = configuration["providers"]
    if not isinstance(providers, dict) or set(providers) != set(_PROVIDER_FIELDS):
        raise InstallPlanError("configuration must define all supported providers")
    for name, allowed in _PROVIDER_FIELDS.items():
        item = providers[name]
        if not isinstance(item, dict) or set(item) != allowed:
            raise InstallPlanError(f"provider configuration is incomplete or has unknown fields: {name}")
        if not isinstance(item["enabled"], bool) or any(
            not isinstance(value, str) for key, value in item.items() if key != "enabled"
        ):
            raise InstallPlanError(f"provider fields have invalid types: {name}")
    if providers["copilot"]["auth_mode"] not in {"device-flow", "pat"}:
        raise InstallPlanError("copilot auth_mode must be device-flow or pat")
    if providers["ollama-cloud"]["auth_mode"] not in {"signin", "api_key"}:
        raise InstallPlanError("ollama-cloud auth_mode must be signin or api_key")

    knowledge = configuration["knowledge"]
    if (
        not isinstance(knowledge, dict)
        or set(knowledge) != {"mode", "path", "visibility", "git_init"}
        or knowledge.get("mode") not in {"none", "existing", "new"}
        or not isinstance(knowledge.get("path"), str)
        or knowledge.get("visibility") not in {"private", "public"}
        or not isinstance(knowledge.get("git_init"), bool)
    ):
        raise InstallPlanError("knowledge configuration is invalid")

    credentials = configuration["credential_store"]
    if (
        not isinstance(credentials, dict)
        or set(credentials) != {"mode", "path", "encrypted", "scope"}
        or credentials.get("mode") not in {"session", "persistent", "external"}
        or not isinstance(credentials.get("path"), str)
        or not isinstance(credentials.get("encrypted"), bool)
        or credentials.get("scope") not in {"session", "CurrentUser"}
    ):
        raise InstallPlanError("credential_store configuration is invalid")


def _canonical_path(raw: str | os.PathLike[str], *, label: str) -> Path:
    value = str(raw or "").strip()
    if not value:
        raise InstallPlanError(f"{label} is required")
    path = Path(value).expanduser()
    _assert_no_link_components(path.absolute())
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise InstallPlanError(f"{label} does not resolve to an existing path") from exc


def _assert_no_link_components(path: Path) -> None:
    """Reject symlinks and Windows reparse points in the lexical path."""
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise InstallPlanError(f"Cannot inspect install path component: {current}") from exc
        if current.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            raise InstallPlanError(f"Linked path component is not permitted: {current}")


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except OSError as exc:
        raise InstallPlanError(f"Cannot inspect install source entry: {path}") from exc


def source_tree_digest(source_root: str | os.PathLike[str]) -> str:
    """Hash a complete source tree deterministically and reject links.

    The digest includes relative names, file lengths, and file bytes. It does
    not follow symlinks/reparse points, so the identity cannot silently escape
    the staged source tree between approval and execution.
    """
    root = _canonical_path(source_root, label="source_root")
    if not root.is_dir() or _is_reparse_or_symlink(root):
        raise InstallPlanError("source_root must be a non-linked directory")

    digest = hashlib.sha256()
    try:
        paths = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        for path in paths:
            relative = path.relative_to(root).as_posix()
            if _is_reparse_or_symlink(path):
                raise InstallPlanError(f"Linked source entry is not permitted: {relative}")
            if not path.is_file():
                continue
            encoded_name = relative.encode("utf-8")
            digest.update(len(encoded_name).to_bytes(8, "big"))
            digest.update(encoded_name)
            size = path.stat().st_size
            digest.update(size.to_bytes(8, "big"))
            file_digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    file_digest.update(chunk)
            digest.update(file_digest.digest())
    except OSError as exc:
        raise InstallPlanError(f"Cannot hash install source tree: {exc}") from exc
    return digest.hexdigest()


def build_install_plan(
    *,
    action: str,
    source_root: str | os.PathLike[str],
    helper_path: str | os.PathLike[str],
    install_dir: str | os.PathLike[str],
    mode: str,
    options: dict[str, Any],
    configuration: dict[str, Any],
    package_digest: str = "",
) -> dict[str, Any]:
    """Return the public, secret-free, operation-bound install descriptor.

    The digest binds provider/knowledge choices, including secret values,
    without copying those values into a public challenge descriptor. The
    original configuration is returned separately by the caller and must
    travel only in the private execution request/helper plan.
    """
    clean_action = str(action or "").strip().lower()
    clean_mode = str(mode or "").strip().title()
    if clean_action not in _ALLOWED_ACTIONS:
        raise InstallPlanError("action is not a supported install operation")
    if clean_mode not in _ALLOWED_MODES:
        raise InstallPlanError("mode must be selected before authorization")
    if not isinstance(options, dict) or set(options) - _ALLOWED_OPTIONS:
        raise InstallPlanError("options contain unsupported installer switches")
    if any(not isinstance(value, bool) for value in options.values()):
        raise InstallPlanError("installer options must be booleans")
    if not isinstance(configuration, dict):
        raise InstallPlanError("configuration must be an object")
    validate_install_configuration(configuration)
    configuration_hash = configuration_digest(configuration)
    if package_digest and (len(package_digest) != 64 or any(c not in "0123456789abcdef" for c in package_digest.lower())):
        raise InstallPlanError("package_digest must be a SHA-256 hex digest")

    source = _canonical_path(source_root, label="source_root")
    helper = _canonical_path(helper_path, label="helper_path")
    target = Path(install_dir).expanduser()
    if not target.is_absolute():
        raise InstallPlanError("install_dir must be absolute")
    _assert_no_link_components(target)
    target = target.resolve(strict=False)
    drive_root = Path(target.anchor) if target.anchor else None
    if not str(target) or (drive_root is not None and os.path.normcase(str(target)) == os.path.normcase(str(drive_root))):
        raise InstallPlanError("install_dir cannot be a filesystem root")
    if not helper.is_file() or _is_reparse_or_symlink(helper):
        raise InstallPlanError("helper_path must be a regular, non-linked file")
    try:
        helper.relative_to(source)
    except ValueError as exc:
        raise InstallPlanError("helper_path must be inside source_root") from exc

    clean_options = {key: bool(options.get(key, False)) for key in sorted(_ALLOWED_OPTIONS)}
    descriptor = {
        "schema": "bago.system-install-plan.v1",
        "action": clean_action,
        "source_root": str(source),
        "source_tree_sha256": source_tree_digest(source),
        "helper_path": str(helper),
        "helper_sha256": _sha256_file(helper),
        "install_dir": str(target),
        "mode": clean_mode,
        "options": clean_options,
        "configuration_digest": configuration_hash,
        "package_sha256": package_digest.lower(),
    }
    descriptor["operation_sha256"] = plan_digest(descriptor)
    return descriptor


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise InstallPlanError(f"Cannot hash install helper: {path}") from exc
    return digest.hexdigest()


def plan_digest(plan: dict[str, Any]) -> str:
    """Hash a JSON-safe plan excluding its self-referential digest field."""
    value = {key: item for key, item in plan.items() if key != "operation_sha256"}
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def configuration_digest(configuration: dict[str, Any]) -> str:
    """Digest JSON-safe configuration, including secrets, without returning it."""
    try:
        encoded = json.dumps(
            configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InstallPlanError("configuration must contain only JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["InstallPlanError", "build_install_plan", "configuration_digest", "plan_digest", "source_tree_digest", "validate_install_configuration"]
