"""POST /chat/stream: incremental SSE backed by shared per-manager turn admission."""
from __future__ import annotations

import copy
import json
import logging
import time
from contextlib import nullcontext
from typing import Any, TYPE_CHECKING

from error_payload_filter import (
    extract_diagnostic,
    is_canonical_error_payload,
    rewrite_to_user_friendly,
)

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_LOGGER = logging.getLogger(__name__)


class _ClientDisconnected(Exception):
    pass


def _interpretation(manager: Any, receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    interpretation = getattr(manager, "last_stream_interpretation", None)
    if not isinstance(interpretation, dict) and isinstance(receipt, dict):
        metadata = receipt.get("metadata")
        interpretation = metadata.get("reflexive_interpretation") if isinstance(metadata, dict) else None
    return copy.deepcopy(interpretation) if isinstance(interpretation, dict) else None


def _capture_stream_state(
    manager: Any,
    *,
    session_id: str,
    provider: str,
    model: str,
    stream_failed: bool,
    cancelled: bool,
) -> dict[str, Any]:
    receipt_object = getattr(manager, "last_receipt", None)
    receipt = receipt_object.to_dict() if receipt_object is not None else None
    interpretation = _interpretation(manager, receipt)
    receipt = receipt if isinstance(receipt, dict) else None
    receipt_provider = receipt.get("provider_used") if receipt is not None else None
    receipt_model = receipt.get("model_used") if receipt is not None else None
    return copy.deepcopy({
        "session_id": session_id,
        "provider": str(receipt_provider or getattr(manager, "provider", "") or provider),
        "model": str(receipt_model or getattr(manager, "model", "") or model),
        "response_state": (
            "cancelled" if cancelled else "failed" if stream_failed
            else str(getattr(manager, "last_response_state", "done") or "done")
        ),
        "clarification": getattr(manager, "last_clarification", None),
        "context_receipt": receipt,
        "interpretation": interpretation,
    })


def _send_admission_error(ctx: Any, status: int, code: str, message: str, turn_id: str = "") -> None:
    ctx.send_json(status, {
        "ok": False,
        "code": code,
        "error": message,
        **({"turn_id": turn_id} if turn_id else {}),
    })


def _send_sse_error(handler: "BaseHTTPRequestHandler", status: int, message: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "text/event-stream")
    handler.end_headers()
    handler.wfile.write(
        b"data: " + json.dumps({"error": message}).encode("utf-8") + b"\n\n"
    )
    handler.wfile.flush()


def _write_event(handler: "BaseHTTPRequestHandler", event: dict[str, Any]) -> None:
    line = f"data: {json.dumps(event)}\n\n".encode("utf-8")
    try:
        handler.wfile.write(line)
        handler.wfile.flush()
    except OSError as exc:
        raise _ClientDisconnected from exc


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from request_context import build_context
    from chat_turns import ChatTurnError, turn_store

    ctx = build_context(handler)
    if ctx.session_mgr is None:
        _send_sse_error(handler, 503, "SessionManager no disponible")
        return

    manager = ctx.session_mgr
    turn_store_for_manager = turn_store(manager)
    turn_id = str(body.get("turn_id") or "").strip()
    raw_message = body.get("message", "")
    conversation_id = getattr(getattr(manager, "store", None), "active_conversation_id", None)

    if turn_id:
        try:
            previous = turn_store_for_manager.lookup(turn_id)
        except ChatTurnError as exc:
            _send_admission_error(ctx, 404, exc.code, str(exc), turn_id)
            return
        if "conversation_id" in body and body.get("conversation_id") != previous.conversation_id:
            _send_admission_error(
                ctx, 409, "chat_turn_request_mismatch",
                "El turno pertenece a otra conversación.", turn_id,
            )
            return
        conversation_id = previous.conversation_id
        if "message" not in body:
            raw_message = previous.message

    if not isinstance(raw_message, str) or not raw_message.strip():
        _send_sse_error(handler, 400, "Campo 'message' requerido")
        return
    message = raw_message

    try:
        turn, owns_execution = turn_store_for_manager.reserve_stream(
            message, conversation_id, turn_id=turn_id,
        )
    except ChatTurnError as exc:
        status = 404 if exc.code == "chat_turn_not_found" else 409
        _send_admission_error(ctx, status, exc.code, str(exc), exc.turn_id or turn_id)
        return

    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Bago-Turn-Id", turn.turn_id)
        handler.end_headers()
    except OSError:
        if owns_execution:
            snapshot = {
                "session_id": str(getattr(manager, "session_id", "") or ""),
                "provider": str(getattr(manager, "provider", "") or ""),
                "model": str(getattr(manager, "model", "") or ""),
                "response_state": "cancelled",
                "clarification": None,
                "context_receipt": None,
                "interpretation": None,
            }
            turn_store_for_manager.complete_stream(
                turn,
                events=[],
                done_payload={"done": True, "ok": False, **snapshot, "turn_id": turn.turn_id},
                response="",
                snapshot=snapshot,
                status="cancelled",
            )
        return

    if not owns_execution:
        try:
            for event in turn.stream_events:
                _write_event(handler, event)
            if turn.stream_done is not None:
                _write_event(handler, turn.stream_done)
        except _ClientDisconnected:
            return
        return

    started = time.monotonic()
    session_id = str(getattr(manager, "session_id", "") or "")
    provider = str(getattr(manager, "provider", "") or "")
    model = str(getattr(manager, "model", "") or "")
    events: list[dict[str, Any]] = []
    response_chunks: list[str] = []
    leaked_error: str | None = None
    stream_failed = False
    cancelled = False
    disconnected = False
    stream = None
    snapshot: dict[str, Any] = {}
    done_payload: dict[str, Any] = {}

    def emit(event: dict[str, Any]) -> None:
        events.append(copy.deepcopy(event))
        _write_event(handler, event)
        if isinstance(event.get("chunk"), str):
            response_chunks.append(event["chunk"])

    try:
        store = getattr(manager, "store", None)
        scope = getattr(store, "conversation_scope", None)
        with scope(turn.conversation_id) if callable(scope) else nullcontext():
            stream = iter(manager.send_stream(message))
            first_chunk = next(stream, None)
            current_receipt = getattr(manager, "last_receipt", None)
            receipt_data = current_receipt.to_dict() if current_receipt is not None else None
            interpretation = _interpretation(manager, receipt_data)
            if interpretation is not None:
                emit({"interpretation": interpretation})

            pending = [] if first_chunk is None else [first_chunk]
            for chunk in pending:
                if is_canonical_error_payload(chunk):
                    leaked_error = chunk
                    break
                emit({"chunk": chunk})
            if leaked_error is None:
                for chunk in stream:
                    if is_canonical_error_payload(chunk):
                        leaked_error = chunk
                        break
                    emit({"chunk": chunk})

            if leaked_error is not None:
                emit({"chunk": rewrite_to_user_friendly(leaked_error)})
                emit(extract_diagnostic(leaked_error))
    except _ClientDisconnected:
        cancelled = True
        disconnected = True
    except Exception as exc:
        stream_failed = True
        _LOGGER.exception("Chat stream failed for turn %s", turn.turn_id)
        try:
            emit({"error": str(exc)})
        except _ClientDisconnected:
            cancelled = True
            disconnected = True
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                stream_failed = True
                _LOGGER.exception("Chat stream cleanup failed for turn %s", turn.turn_id)
        try:
            snapshot = _capture_stream_state(
                manager,
                session_id=session_id,
                provider=provider,
                model=model,
                stream_failed=stream_failed,
                cancelled=cancelled,
            )
        except Exception:
            stream_failed = True
            _LOGGER.exception("Chat stream metadata capture failed for turn %s", turn.turn_id)
            snapshot = {
                "session_id": session_id,
                "provider": provider,
                "model": model,
                "response_state": "failed",
                "clarification": None,
                "context_receipt": None,
                "interpretation": None,
            }

        if leaked_error is not None:
            snapshot["response_state"] = "failed"
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        done_payload = {
            "done": True,
            "ok": not stream_failed and leaked_error is None and not cancelled,
            "latency_ms": latency_ms,
            **snapshot,
            "turn_id": turn.turn_id,
        }
        turn_store_for_manager.complete_stream(
            turn,
            events=events,
            done_payload=done_payload,
            response="".join(response_chunks),
            snapshot=snapshot,
            status="cancelled" if cancelled else "failed" if stream_failed or leaked_error else "done",
        )

    if not disconnected:
        try:
            _write_event(handler, done_payload)
        except _ClientDisconnected:
            pass
