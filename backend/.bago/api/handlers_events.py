"""handlers_events.py — GET /api/v1/events (Server-Sent Events).

Streams `text/event-stream` to the UI client. Each line is
`event: <name>\ndata: <json>\n\n` so EventSource can dispatch by event name.

The handler subscribes to the in-process `event_bus` and forwards every
event. A `heartbeat` is sent every 15s so reverse proxies don't close
the connection on idle.

This is the foundation of the UI's live updates: jobs, evidence,
router, binding, chat completion, etc. Without SSE, the UI relies on
manual refresh (F5) or after every command.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


HEARTBEAT_S = 15.0
SEND_TIMEOUT_S = 5.0


def _sse_send(handler: "BaseHTTPRequestHandler", event: str, payload: dict) -> bool:
    """Write a single SSE frame. Returns False if the client is gone."""
    try:
        frame = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        handler.wfile.write(frame.encode("utf-8"))
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def _listener(q: "queue.Queue[tuple[str, dict]]", event: str, payload: dict) -> None:
    """Bridge event_bus -> queue.Queue (must be thread-safe and non-blocking)."""
    try:
        q.put_nowait((event, payload))
    except queue.Full:
        # Drop the event. The UI is slow or disconnected; the next
        # snapshot refresh will catch up.
        pass


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from event_bus import subscribe

    # 1. Open the SSE stream BEFORE subscribing so the client sees
    #    headers and we can fail early on a bad connection.
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache, no-transform")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return

    # 2. Send an immediate `connected` frame so the client knows the
    #    stream is live. Also serves as a ping for any proxy.
    if not _sse_send(handler, "connected", {"ts": time.time(), "channel": "ui-react"}):
        return

    # 3. Bridge event_bus -> per-connection queue. The queue decouples
    #    listener threads from the network write loop.
    q: "queue.Queue[tuple[str, dict]]" = queue.Queue(maxsize=256)
    unsubscribe = subscribe("*", lambda ev, pl: _listener(q, ev, pl))

    last_heartbeat = time.time()
    try:
        while True:
            try:
                event, payload = q.get(timeout=HEARTBEAT_S)
            except queue.Empty:
                event, payload = None, None  # heartbeat tick

            now = time.time()
            if event is not None:
                if not _sse_send(handler, event, payload):
                    break
                last_heartbeat = now
            elif now - last_heartbeat >= HEARTBEAT_S:
                if not _sse_send(handler, "heartbeat", {"ts": now}):
                    break
                last_heartbeat = now
    finally:
        try:
            unsubscribe()
        except Exception:
            pass
