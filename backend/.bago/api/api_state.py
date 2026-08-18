"""api_state.py \u2014 shared state-root resolution for the BAGO HTTP bridge.

Multiple handlers need to resolve the BAGO state directory the same way.
This module centralises that logic so handlers_memory, handlers_schedule,
handlers_router and bridge.py don't each carry their own copy.

Resolution order:
  1. session_mgr.state_root  (set by the server runner)
  2. session_context.current_state_root()  (REPL fallback)
  3. BAGO_STATE_ROOT
  4. BAGO_USER_ROOT/state
  5. per-user LocalAppData BAGO state
"""

from __future__ import annotations

from pathlib import Path

from bago_core.user_state_paths import state_root as configured_state_root


def resolve_state_root(handler) -> Path:
    mgr = getattr(handler, "session_mgr", None)
    if mgr is not None and hasattr(mgr, "state_root"):
        return Path(mgr.state_root)
    try:
        from session_context import current_state_root
        return current_state_root()
    except Exception:
        return configured_state_root()


def get_mgr(handler):
    return getattr(handler, "session_mgr", None)
