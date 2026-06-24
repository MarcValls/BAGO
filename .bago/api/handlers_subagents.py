"""handlers_subagents.py \u2014 GET /subagents/catalogue for the BAGO HTTP bridge.

Mirrors .bago/chat/repl_subagent.AGENTS so the ControlPlane can render
the agent catalogue (explore / plan / implement / review / test)
without importing the runtime module.
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

    try:
        from repl_subagent import AGENTS
    except Exception as exc:
        send_json(handler, 503, {"error": f"repl_subagent no disponible: {exc}"})
        return
    send_json(handler, 200, {"agents": list(AGENTS)})
