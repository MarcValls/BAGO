from __future__ import annotations

import os
from pathlib import Path


def resolve_state_root(state_root: str | Path | None = None) -> Path:
    override = state_root if state_root is not None else os.environ.get("BAGO_STATE_ROOT", "").strip()
    if override:
        root = Path(override).expanduser().resolve()
    else:
        root = Path.home() / ".bago" / "state"
    root.mkdir(parents=True, exist_ok=True)
    return root
