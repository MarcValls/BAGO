from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_ROOT_ENV = "BAGO_WORKSPACE_ROOT"


def framework_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


def workspace_state_root() -> Path:
    override = _env_path(WORKSPACE_ROOT_ENV)
    if override is not None:
        return override
    return Path.home() / ".gabo"


def legacy_workspace_root() -> Path:
    return Path.home() / ".bago"
