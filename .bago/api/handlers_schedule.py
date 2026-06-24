"""handlers_schedule.py \u2014 GET /schedule/list for the BAGO HTTP bridge.

Mirrors .bago/chat/repl_schedule.load_jobs() so the ControlPlane can
list cron/loop jobs without importing the runtime module.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "chat"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    from repl_schedule import load_jobs

    try:
        base_path = _resolve_state_root(handler)
        jobs = load_jobs(base_path)
        serialised = [
            {
                "id": j.id,
                "kind": j.kind,
                "prompt": j.prompt,
                "cron_expr": j.cron_expr,
                "interval_s": j.interval_s,
                "next_run_at": j.next_run_at,
                "last_run_at": j.last_run_at,
                "status": j.status,
                "created_at": j.created_at,
                "run_count": j.run_count,
                "error": j.error,
            }
            for j in jobs
        ]
        send_json(handler, 200, {"jobs": serialised})
    except Exception as exc:
        send_json(handler, 500, {"error": f"load_jobs fall\u00f3: {exc}"})


def _resolve_state_root(handler) -> Path:
    """Pick the state root: session_manager > session_context > ~/.bago/state."""
    mgr = getattr(handler, "session_mgr", None)
    if mgr is not None and hasattr(mgr, "state_root"):
        return Path(mgr.state_root)
    try:
        from session_context import current_state_root
        return current_state_root()
    except Exception:
        return Path.home() / ".bago" / "state"
