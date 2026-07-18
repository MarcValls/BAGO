"""handlers_schedule.py \u2014 GET /schedule/list for the BAGO HTTP bridge.

Mirrors .bago/chat/repl_schedule.load_jobs() so the ControlPlane can
list cron/loop jobs without importing the runtime module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from handlers_jobs import _scheduled_jobs

    try:
        mgr = get_mgr(handler)
        jobs = _scheduled_jobs(mgr) if mgr is not None else []
        serialised = [
            {
                "id": str(j.get("execution_id") or ""),
                "kind": str(j.get("kind") or "schedule"),
                "prompt": str(j.get("prompt") or ""),
                "cron_expr": str(j.get("cron_expr") or ""),
                "interval_s": j.get("interval_s"),
                "next_run_at": str(j.get("next_run_at") or ""),
                "last_run_at": str(j.get("last_run_at") or ""),
                "status": str(j.get("status") or ""),
                "created_at": str(j.get("created_at") or ""),
                "run_count": int(j.get("run_count") or 0),
                "error": str(j.get("error") or ""),
            }
            for j in jobs
        ]
        send_json(handler, 200, {"jobs": serialised})
    except Exception as exc:
        send_json(handler, 500, {"error": f"load_jobs fall\u00f3: {exc}"})
