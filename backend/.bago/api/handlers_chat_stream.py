"""handlers_chat_stream.py — POST /chat/stream for the BAGO HTTP bridge.

SSE-style streaming endpoint: sends `text/event-stream` response and
flushes each chunk from `session_mgr.send_stream()` as it arrives.

Format: `data: <chunk>\n\n` per chunk, final `data: [DONE]\n\n`.

Internal canonical error payloads (emitted by `_canonical_task_failure_payload`
in session_turn_mixin.py when the model fails the JSON contract) are
intercepted and replaced with a user-friendly message. The technical
details are forwarded as a separate `diagnostic` event for the UI/logs.
"""
from __future__ import annotations

import json
import time
from typing import Any, TYPE_CHECKING

from error_payload_filter import (
    extract_diagnostic,
    is_canonical_error_payload,
    rewrite_to_user_friendly,
)

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

    raw_message = body.get("message", "")
    if not isinstance(raw_message, str) or not raw_message.strip():
        handler.send_response(400)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()
        handler.wfile.write(b"data: " + json.dumps({"error": "Campo 'message' requerido"}).encode() + b"\n\n")
        handler.wfile.flush()
        return

    message = raw_message

    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.end_headers()

    started = time.time()
    leaked_error: str | None = None
    stream_failed = False
    try:
        for chunk in ctx.session_mgr.send_stream(message):
            if is_canonical_error_payload(chunk):
                # Do NOT stream the internal canonical error payload to
                # the user. Capture it for logging and stop the stream
                # early; the friendly message is emitted below.
                leaked_error = chunk
                break
            line = f"data: {json.dumps({'chunk': chunk})}\n\n"
            handler.wfile.write(line.encode("utf-8"))
            handler.wfile.flush()
    except Exception as exc:
        stream_failed = True
        import os
        import traceback
        if os.environ.get("BAGO_DEBUG"):
            traceback.print_exc()
        err_line = f"data: {json.dumps({'error': str(exc)})}\n\n"
        handler.wfile.write(err_line.encode("utf-8"))
        handler.wfile.flush()

    if leaked_error is not None:
        friendly = rewrite_to_user_friendly(leaked_error)
        line = f"data: {json.dumps({'chunk': friendly})}\n\n"
        handler.wfile.write(line.encode("utf-8"))
        handler.wfile.flush()
        diag_line = f"data: {json.dumps(extract_diagnostic(leaked_error))}\n\n"
        handler.wfile.write(diag_line.encode("utf-8"))
        handler.wfile.flush()

    receipt = ctx.session_mgr.last_receipt.to_dict() if ctx.session_mgr.last_receipt else None
    done_payload = {
        "done": True,
        "ok": not stream_failed and leaked_error is None,
        "latency_ms": round((time.time() - started) * 1000, 2),
        "session_id": ctx.session_mgr.session_id,
        "provider": ctx.session_mgr.provider,
        "model": ctx.session_mgr.model,
        "response_state": "failed" if stream_failed else str(getattr(ctx.session_mgr, "last_response_state", "done") or "done"),
        "clarification": getattr(ctx.session_mgr, "last_clarification", None),
        "context_receipt": receipt,
    }
    done_line = f"data: {json.dumps(done_payload)}\n\n"
    handler.wfile.write(done_line.encode("utf-8"))
    handler.wfile.flush()
