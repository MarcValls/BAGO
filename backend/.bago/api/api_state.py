"""api_state.py \u2014 shared state-root resolution for the BAGO HTTP bridge.

Multiple handlers need to resolve the BAGO state directory the same way.
This module centralises that logic so handlers_memory, handlers_schedule,
handlers_router and bridge.py don't each carry their own copy.

Resolution order:
  1. session_mgr.state_root  (set by the server runner)
  2. session_context.current_state_root()  (REPL fallback)
  3. ~/.bago/state  (last resort)
"""

from __future__ import annotations

from pathlib import Path


def resolve_state_root(handler) -> Path:
    mgr = getattr(handler, "session_mgr", None)
    if mgr is not None and hasattr(mgr, "state_root"):
        return Path(mgr.state_root)
    try:
        from session_context import current_state_root
        return current_state_root()
    except Exception:
        return Path.home() / ".bago" / "state"


def get_mgr(handler):
    return getattr(handler, "session_mgr", None)