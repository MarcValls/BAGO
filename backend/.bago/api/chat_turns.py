"""Process-local chat operation identity; retries never create another turn.

A server-issued turn_id is a lookup key, not authorization. Missing/evicted IDs
fail closed (including after restart); only a request without an ID can start
work. Completed result retention is bounded and one operation may run per manager.
All material work remains in SessionManager and its existing effect owners.
"""
from __future__ import annotations

from collections import OrderedDict
import copy
from dataclasses import dataclass, field
import threading
import time
import uuid
from typing import Any, Callable


@dataclass
class ChatTurn:
    turn_id: str
    message: str
    internal: bool
    conversation_id: str | None
    kind: str = "chat"
    started: float = field(default_factory=time.monotonic)
    done: threading.Event = field(default_factory=threading.Event)
    response: str | None = None
    error: dict[str, Any] | None = None
    snapshot: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    stream_events: list[dict[str, Any]] = field(default_factory=list)
    stream_done: dict[str, Any] | None = None
    stream_status: str = ""


class ChatTurnError(ValueError):
    def __init__(self, code: str, message: str, *, turn_id: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.turn_id = turn_id


class ChatTurnStore:
    def __init__(self, max_completed: int = 64) -> None:
        self._lock = threading.Lock()
        self._turns: OrderedDict[str, ChatTurn] = OrderedDict()
        self._active: ChatTurn | None = None
        self.max_completed = max_completed

    def lookup(self, turn_id: str) -> ChatTurn:
        with self._lock:
            turn = self._turns.get(turn_id)
            if turn is None:
                raise ChatTurnError("chat_turn_not_found", "Turno desconocido o resultado expirado; no se reejecutó.")
            return turn

    def get_or_start(
        self, message: str, internal: bool, conversation_id: str | None,
        runner: Callable[[], tuple[str, dict[str, Any]]], *, turn_id: str = "",
        kind: str = "chat",
    ) -> ChatTurn:
        with self._lock:
            if turn_id:
                turn = self._turns.get(turn_id)
                if turn is None:
                    raise ChatTurnError("chat_turn_not_found", "Turno desconocido o resultado expirado; no se reejecutó.")
                if (
                    turn.message != message
                    or turn.internal != internal
                    or turn.conversation_id != conversation_id
                    or turn.kind != kind
                ):
                    raise ChatTurnError("chat_turn_request_mismatch", "El turno pertenece a otra solicitud.", turn_id=turn_id)
                return turn
            if self._active is not None and not self._active.done.is_set():
                raise ChatTurnError("chat_turn_in_progress", "Existe un turno en curso; consulta su turn_id antes de reintentar.", turn_id=self._active.turn_id)
            # Eviction only removes completed results. An evicted ID can never
            # restart work because IDs are generated solely on the server.
            while len(self._turns) >= self.max_completed:
                oldest = next(iter(self._turns))
                del self._turns[oldest]
            turn = ChatTurn(uuid.uuid4().hex, message, internal, conversation_id, kind=kind)
            self._turns[turn.turn_id] = turn
            self._active = turn

            def run() -> None:
                try:
                    turn.response, turn.snapshot = runner()
                except BaseException as exc:
                    turn.error = {"ok": False, "error": f"Error interno: {exc}"}
                finally:
                    with self._lock:
                        turn.elapsed_ms = (time.monotonic() - turn.started) * 1000
                        turn.done.set()
                        if self._active is turn:
                            self._active = None

            try:
                threading.Thread(target=run, daemon=True, name=f"bago-chat-{turn.turn_id}").start()
            except BaseException:
                self._turns.pop(turn.turn_id)
                self._active = None
                raise
            return turn

    def reserve_stream(
        self,
        message: str,
        conversation_id: str | None,
        *,
        turn_id: str = "",
    ) -> tuple[ChatTurn, bool]:
        """Reserve the manager for one synchronous SSE operation or replay it."""
        with self._lock:
            if turn_id:
                turn = self._turns.get(turn_id)
                if turn is None:
                    raise ChatTurnError("chat_turn_not_found", "Turno desconocido o resultado expirado; no se reejecutó.")
                if (
                    turn.message != message
                    or turn.internal
                    or turn.conversation_id != conversation_id
                    or turn.kind != "stream"
                ):
                    raise ChatTurnError(
                        "chat_turn_request_mismatch",
                        "El turno pertenece a otra solicitud.",
                        turn_id=turn_id,
                    )
                if not turn.done.is_set():
                    raise ChatTurnError(
                        "chat_turn_in_progress",
                        "El turno sigue en curso; consulta su mismo turn_id.",
                        turn_id=turn_id,
                    )
                return turn, False

            if self._active is not None and not self._active.done.is_set():
                raise ChatTurnError(
                    "chat_turn_in_progress",
                    "Existe un turno en curso; consulta su turn_id antes de reintentar.",
                    turn_id=self._active.turn_id,
                )
            while len(self._turns) >= self.max_completed:
                oldest = next(iter(self._turns))
                del self._turns[oldest]
            turn = ChatTurn(
                uuid.uuid4().hex,
                message,
                False,
                conversation_id,
                kind="stream",
            )
            self._turns[turn.turn_id] = turn
            self._active = turn
            return turn, True

    def complete_stream(
        self,
        turn: ChatTurn,
        *,
        events: list[dict[str, Any]],
        done_payload: dict[str, Any],
        response: str,
        snapshot: dict[str, Any],
        status: str,
    ) -> None:
        with self._lock:
            if turn.kind != "stream" or turn.done.is_set():
                raise ChatTurnError(
                    "chat_turn_not_active",
                    "El turno de streaming ya está cerrado.",
                    turn_id=turn.turn_id,
                )
            turn.stream_events = copy.deepcopy(events)
            turn.stream_done = copy.deepcopy(done_payload)
            turn.response = response
            turn.snapshot = copy.deepcopy(snapshot)
            turn.stream_status = status
            turn.elapsed_ms = (time.monotonic() - turn.started) * 1000
            turn.done.set()
            if self._active is turn:
                self._active = None


_STORE_LOCK = threading.Lock()


def turn_store(manager: Any) -> ChatTurnStore:
    with _STORE_LOCK:
        store = getattr(manager, "_api_chat_turn_store", None)
        if store is None:
            store = ChatTurnStore()
            manager._api_chat_turn_store = store
        return store
