"""handlers_chat_stream.py — POST /chat/stream for the BAGO HTTP bridge.

SSE-style streaming endpoint: sends `text/event-stream` response and
flushes each chunk from `session_mgr.send_stream()` as it arrives.

Format: `data: <chunk>\n\n` per chunk, final `data: [DONE]\n\n`.
"""
from __future__ import annotations

import json
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from request_context import build_context

    ctx = build_context(handler)
    if ctx.session_mgr is None:
        handler.send_response(503)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.write(b"data: " + json.dumps({"error": "SessionManager no disponible"}).encode() + b"\n\n")
        handler.wfile.flush()
        return

    message = body.get("message", "")
    if not message:
        handler.send_response(400)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.write(b"data: " + json.dumps({"error": "Campo 'message' requerido"}).encode() + b"\n\n")
        handler.wfile.flush()
        return

    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.end_headers()

    started = time.time()
    try:
        for chunk in ctx.session_mgr.send_stream(message):
            line = f"data: {json.dumps({'chunk': chunk})}\n\n"
            handler.wfile.write(line.encode("utf-8"))
            handler.wfile.flush()
    except Exception as exc:
        err_line = f"data: {json.dumps({'error': str(exc)})}\n\n"
        handler.wfile.write(err_line.encode("utf-8"))
        handler.wfile.flush()

    done_line = f"data: {json.dumps({'done': True, 'latency_ms': round((time.time() - started) * 1000, 2)})}\n\n"
    handler.wfile.write(done_line.encode("utf-8"))
    handler.wfile.flush()