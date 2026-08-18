from __future__ import annotations

from pathlib import Path

from bago_core.user_state_paths import state_root as configured_state_root


def resolve_state_root(state_root: str | Path | None = None) -> Path:
    """Resolve and create the canonical mutable-state directory.

    An explicit non-empty path wins. Otherwise the shared user-state contract
    resolves BAGO_STATE_ROOT, then BAGO_USER_ROOT/state, then the per-user
    default. The legacy ~/.bago tree is intentionally not a write default.
    """
    explicit = state_root
    if isinstance(explicit, str) and not explicit.strip():
        explicit = None
    root = (
        Path(explicit).expanduser().resolve()
        if explicit is not None
        else configured_state_root()
    )
    root.mkdir(parents=True, exist_ok=True)
    return root
