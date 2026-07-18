from __future__ import annotations

from pathlib import Path

from bago_core.resolver import legacy_workspace_root as _legacy_workspace_root
from bago_core.resolver import workspace_state_root as _workspace_state_root


def workspace_root() -> Path:
    return _workspace_state_root()


def legacy_workspace_root() -> Path:
    return _legacy_workspace_root()
