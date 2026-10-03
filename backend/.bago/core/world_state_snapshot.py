"""Canonical world-state snapshot used by governed material effects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution_request import UNSPECIFIED_WORLD_STATE, build_execution_request, stable_digest


@dataclass(frozen=True, slots=True)
class WorldStateSnapshot:
    """Small, deterministic projection of the state relevant to one effect."""

    workspace: str
    workspace_state_root: str
    session_id: str
    context_revision: str
    policy_version: str
    target: dict[str, Any]
    effect_id: str
    runtime: str = ""
    authority_root: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "contract": "bago.world-state-snapshot/v1",
            "workspace": self.workspace,
            "workspace_state_root": self.workspace_state_root,
            "session_id": self.session_id,
            "context_revision": self.context_revision,
            "policy_version": self.policy_version,
            "target": self.target,
            "effect_id": self.effect_id,
            "runtime": self.runtime,
            "authority_root": self.authority_root,
        }

    @property
    def digest(self) -> str:
        return stable_digest(self.payload)

    @classmethod
    def from_request(
        cls, request: Any, manager: Any = None, *, authority_root: str = ""
    ) -> "WorldStateSnapshot":
        if isinstance(manager, (str, Path)):
            authority_root = authority_root or str(manager)
            manager = None
        state = {}
        if manager is not None:
            getter = getattr(manager, "workspace_state", None)
            if callable(getter):
                candidate = getter()
                if isinstance(candidate, dict):
                    state = candidate
        manager_root = getattr(manager, "base_path", "") or getattr(manager, "project_root", "")
        selected_root = str(state.get("project_root") or state.get("workspace") or manager_root or authority_root or "")
        state_root = str(state.get("workspace_state_root") or (Path(selected_root) / ".gabo" if selected_root else ""))
        return cls(
            workspace=selected_root,
            workspace_state_root=state_root,
            session_id=str(getattr(request, "session_id", "") or ""),
            context_revision=str(state.get("context_revision") or getattr(manager, "context_revision", "") or ""),
            policy_version=str(getattr(request, "policy_version", "") or ""),
            target=dict(getattr(request, "target", {}) or {}),
            effect_id=str(getattr(request, "effect_id", "") or ""),
            runtime=str(getattr(manager, "runtime", "") or ""),
            authority_root=str(authority_root or manager_root or ""),
        )


def require_fresh_world_state(request: Any, manager: Any = None) -> WorldStateSnapshot:
    snapshot = WorldStateSnapshot.from_request(request, manager)
    declared = str(getattr(request, "world_state_digest", "") or "")
    if declared == stable_digest({"state": UNSPECIFIED_WORLD_STATE}):
        raise ValueError("material execution requires a WorldStateSnapshot")
    if declared != snapshot.digest:
        raise ValueError("declared world state is stale")
    return snapshot


def build_execution_request_with_snapshot(manager: Any = None, **kwargs: Any) -> Any:
    """Build a request whose digest is derived from the trusted manager.

    This is the migration seam for API/CLI callers: they provide the normal
    request fields, while the manager supplies the state authority.
    """
    authority_root = str(kwargs.pop("authority_root", "") or "")
    authority = manager if manager is not None else authority_root
    if authority is None or authority == "":
        raise ValueError("WorldStateSnapshot requires a trusted manager or authority_root")
    return build_execution_request(**kwargs, world_state_authority=authority)


__all__ = ["WorldStateSnapshot", "require_fresh_world_state", "build_execution_request_with_snapshot"]
