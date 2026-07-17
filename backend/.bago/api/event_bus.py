"""event_bus.py — Minimal in-process pub/sub for UI live updates.

Thread-safe. Listeners are callables: `listener(event_name, payload)`.

Usage:
    from event_bus import emit, subscribe

    def my_listener(event, payload):
        ...

    subscribe('chat.completed', my_listener)
    emit('chat.completed', {'session_id': '...', 'latency_ms': 123})

Keep the surface tiny: this is for UI reactivity, not a general event
mesh. Cross-process messaging still lives in the bridges (AppData,
cmd-rl, etc.) per the BAGO architecture.

Listeners must not block. Use threading if you need to do real work.
"""

from __future__ import annotations

import threading
from typing import Callable, Any

Listener = Callable[[str, dict], None]

_lock = threading.Lock()
_listeners: dict[str, list[Listener]] = {}
_wildcard_listeners: list[Listener] = []


def subscribe(event: str, listener: Listener) -> Callable[[], None]:
    """Register a listener for a specific event name (or '*' for all).

    Returns an unsubscribe callable.
    """
    with _lock:
        if event == "*":
            _wildcard_listeners.append(listener)
            target = _wildcard_listeners
        else:
            _listeners.setdefault(event, []).append(listener)
            target = _listeners[event]
    def _unsubscribe() -> None:
        with _lock:
            try:
                target.remove(listener)
            except ValueError:
                pass
    return _unsubscribe


def emit(event: str, payload: dict | None = None) -> int:
    """Fire an event to all matching listeners.

    Returns the number of listeners notified. Exceptions in listeners
    are swallowed (logged via get_logger if available) so one bad
    listener cannot break the bus.
    """
    payload = payload or {}
    notified = 0
    with _lock:
        listeners = list(_listeners.get(event, [])) + list(_wildcard_listeners)
    for listener in listeners:
        try:
            listener(event, payload)
            notified += 1
        except Exception:
            # Use a soft import so this module can be loaded standalone.
            try:
                from structured_log import get_logger
                get_logger().error("event_listener_failed", event=event, listener=getattr(listener, '__name__', repr(listener)))
            except Exception:
                pass
    return notified


def listener_count(event: str | None = None) -> int:
    """Diagnostic: how many listeners are registered for an event (or total)."""
    with _lock:
        if event is None:
            return sum(len(v) for v in _listeners.values()) + len(_wildcard_listeners)
        return len(_listeners.get(event, []))
