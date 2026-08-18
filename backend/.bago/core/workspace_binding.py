#!/usr/bin/env python3
"""workspace_binding.py - canonical workspace/project/framework binding.

Small helper used by the runtime to keep the three authorities separated:

- framework_root: the active BAGO installation (.bago)
- project_root: the real project checkout
- workspace_state_root: the project workspace state (.gabo)

The helper is intentionally conservative. It derives stable defaults from
the current project root and only trusts on-disk manifest data when present.
"""
# CANON[WS-001]: this module is the authoritative resolver for framework,
# project, and workspace binding.
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def _first_existing(*candidates: str | os.PathLike[str] | None) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        try:
            path = path.resolve()
        except Exception:
            continue
        if path.exists():
            return path
    return None


def resolve_framework_root() -> Path:
    """Resolve the active BAGO framework root.

    Prefer explicit environment overrides, then walk from this module's
    location back to the repository/installation root.
    """
    env_root = _first_existing(
        os.environ.get("BAGO_FRAMEWORK_ROOT"),
        os.environ.get("BAGO_ROOT"),
    )
    if env_root is not None:
        if env_root.name.lower() == ".bago":
            return env_root
        bago_dir = env_root / ".bago"
        if bago_dir.exists():
            return bago_dir
        if (env_root / "bago_core").exists():
            return env_root / ".bago" if (env_root / ".bago").exists() else env_root
    repo_root = Path(__file__).resolve().parents[2]
    if (repo_root / ".bago").exists():
        return repo_root / ".bago"
    if (repo_root / "bago_core").exists():
        return repo_root / ".bago" if (repo_root / ".bago").exists() else repo_root
    return repo_root / ".bago"


def resolve_project_root(project_root: str | Path | None = None) -> Path:
    """Resolve the real project checkout root."""
    if project_root is None or str(project_root).strip() == "":
        return Path.cwd().resolve()
    return Path(project_root).expanduser().resolve()


def resolve_workspace_state_root(project_root: str | Path) -> Path:
    # CANON[WS-002]: workspace state always lives under project_root/.gabo.
    return resolve_project_root(project_root) / ".gabo"


def _hash_workspace_id(project_root: Path) -> str:
    token = hashlib.sha256(str(project_root).encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"ws-{token}"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@dataclass(frozen=True)
class WorkspaceBinding:
    framework_root: str
    project_root: str
    workspace_state_root: str
    workspace_scope_root: str
    workspace_id: str
    manifest_path: str
    manifest_exists: bool
    project_exists: bool
    workspace_exists: bool
    binding_confirmed: bool
    binding_reason: str
    source: str = "derived"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_workspace_binding(project_root: str | Path | None = None) -> WorkspaceBinding:
    project = resolve_project_root(project_root)
    framework_root = resolve_framework_root()
    # CANON[WS-003]: workspace.json is the canonical identity record for the workspace.
    workspace_state_root = resolve_workspace_state_root(project)
    manifest_path = workspace_state_root / "workspace.json"
    manifest = _read_json(manifest_path)

    # LEGACY[WS-L001]: derived workspace_id is a fallback when the manifest is absent.
    workspace_id = str(manifest.get("workspace_id") or "").strip() or _hash_workspace_id(project)
    scope_root = str(manifest.get("workspace_scope_root") or project).strip() or str(project)

    project_exists = project.exists()
    workspace_exists = workspace_state_root.exists()
    manifest_exists = manifest_path.exists()
    framework_exists = framework_root.exists()

    reasons: list[str] = []
    if not project_exists:
        reasons.append("project missing")
    if not workspace_exists:
        reasons.append("workspace missing")
    if not framework_exists:
        reasons.append("framework missing")
    if not manifest_exists:
        reasons.append("manifest missing")
    if workspace_state_root.name != ".gabo":
        reasons.append("workspace root mismatch")
    if Path(scope_root).resolve() != project:
        reasons.append("scope mismatch")
    if manifest and str(manifest.get("project_root", "")).strip() and Path(str(manifest["project_root"])).resolve() != project:
        reasons.append("manifest project mismatch")

    # CANON[WS-004]: binding fails closed if any authority is incoherent.
    confirmed = bool(
        project_exists
        and workspace_exists
        and framework_exists
        and manifest_exists
        and workspace_state_root.name == ".gabo"
        and Path(scope_root).resolve() == project
        and not reasons
    )
    reason = "ok" if confirmed else "; ".join(reasons) if reasons else "binding unavailable"

    return WorkspaceBinding(
        framework_root=str(framework_root),
        project_root=str(project),
        workspace_state_root=str(workspace_state_root),
        workspace_scope_root=str(Path(scope_root).resolve()),
        workspace_id=workspace_id,
        manifest_path=str(manifest_path),
        manifest_exists=manifest_exists,
        project_exists=project_exists,
        workspace_exists=workspace_exists,
        binding_confirmed=confirmed,
        binding_reason=reason,
        source="manifest" if manifest_exists else "derived",
    )
