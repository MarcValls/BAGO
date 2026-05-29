#!/usr/bin/env python3
"""bago_node.py — BAGO Node Connector

Librería cliente para conectar cualquier herramienta BAGO al Neural Bus.
Sin dependencias externas — usa solo stdlib.

Uso básico:

    from bago_node import BusNode

    node = BusNode(
        "mi_herramienta",
        role="tool",
        capabilities=["code-analysis", "python"],
    )
    if node.connect():
        node.emit("tool.result", {"score": 95, "issues": []})

    # Escuchar eventos entrantes (blocking)
    @node.on("user.message")
    def handle_msg(event):
        text = event["payload"].get("text", "")
        # Correlate response to the original request
        node.emit(
            "user.response",
            {"text": f"Procesado: {text}"},
            reply_to=event.get("from"),
            correlation_id=event.get("correlation_id"),
        )

    node.run()   # blocking loop

Integración rápida (sin estado, fire-and-forget):

    from bago_node import quick_emit
    quick_emit("tool.result", {"file": "main.py", "issues": 3}, from_node="my_linter")

Roles estándar:
  input       → recibe mensajes de usuario (Telegram, WhatsApp, CLI)
  output      → envía respuestas al usuario
  processing  → transforma o enruta mensajes (intent_router, LLM)
  memory      → almacena y provee contexto (bago_context, personality)
  tool        → ejecuta análisis o acciones (scanners, linters)
  monitor     → observa dispositivos o servicios (lenovo, tablet, opencloud)
  hub         → interfaz web (bago_hub)
  supervisor  → orquesta otros nodos (neural_router, orchestrator)
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import sys
import threading
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ── Defaults ───────────────────────────────────────────────────────────────────
DEFAULT_BUS_URL   = "http://localhost:6789"
HEARTBEAT_INTERVAL = 30   # seconds
RECONNECT_DELAY    = 5    # seconds before SSE reconnect

# Token auto-discovery: same file as the bus writes
_TOOLS_DIR  = Path(__file__).resolve().parent
_BAGO_ROOT  = _TOOLS_DIR.parent
_STATE_DIR  = _BAGO_ROOT / "state"
_TOKEN_FILE = _STATE_DIR / "neural_token.txt"


def _load_token(bus_url: str = DEFAULT_BUS_URL) -> str:
    """Load the shared auth token (same file the bus creates)."""
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text(encoding="utf-8").strip()
    return ""


def _make_headers(token: str) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Bago-Token"] = token
    return h


# ── Fire-and-forget helper ─────────────────────────────────────────────────────

def quick_emit(
    topic: str,
    payload: dict,
    from_node: str = "unknown",
    to: str = "*",
    bus_url: str = DEFAULT_BUS_URL,
    correlation_id: Optional[str] = None,
    priority: int = 1,
) -> bool:
    """Emit an event without maintaining a persistent node connection.

    Returns True if the bus accepted the event, False otherwise.
    Never raises — safe to call from any tool as a one-liner.
    """
    token = _load_token(bus_url)
    data: dict = {
        "from": from_node,
        "topic": topic,
        "payload": payload,
        "to": to,
        "priority": priority,
    }
    if correlation_id:
        data["correlation_id"] = correlation_id

    body = json.dumps(data).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{bus_url}/emit",
            data=body,
            headers=_make_headers(token),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            result = json.loads(resp.read())
            return bool(result.get("ok"))
    except Exception:
        return False


# ── BusNode class ──────────────────────────────────────────────────────────────

class BusNode:
    """A BAGO node that connects to the Neural Bus.

    Lifecycle:
      1. Instantiate with node_id, role, capabilities
      2. Call connect() to register with the bus
      3. Register handlers with @node.on("topic.*")
      4. Call run() to start the event loop (blocking)
         OR call start_background() for non-blocking background thread

    Thread safety:
      - emit() is thread-safe
      - Handlers are called from the SSE listener thread
      - Use locks inside handlers if they share mutable state
    """

    def __init__(
        self,
        node_id: str,
        role: str = "node",
        capabilities: Optional[List[str]] = None,
        platform: str = "",
        bus_url: str = DEFAULT_BUS_URL,
        auto_heartbeat: bool = True,
    ) -> None:
        self.node_id     = node_id
        self.role        = role
        self.capabilities = capabilities or []
        self.platform    = platform
        self.bus_url     = bus_url
        self.auto_heartbeat = auto_heartbeat

        self._token: str = _load_token(bus_url)
        self._handlers: Dict[str, List[Callable]] = {}
        self._running: bool = False
        self._connected: bool = False
        self._hb_thread: Optional[threading.Thread] = None
        self._stream_thread: Optional[threading.Thread] = None

    # ── Internal HTTP helpers ──────────────────────────────────────────────────

    def _post(self, path: str, data: dict, timeout: int = 5) -> Optional[dict]:
        body = json.dumps(data).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self.bus_url}{path}",
                data=body,
                headers=_make_headers(self._token),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    # ── Public API ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Register with the bus. Returns True on success."""
        self._token = _load_token(self.bus_url)  # refresh token
        result = self._post("/register", {
            "node_id":      self.node_id,
            "role":         self.role,
            "capabilities": self.capabilities,
            "platform":     self.platform,
        })
        if result and result.get("ok"):
            self._running   = True
            self._connected = True
            if self.auto_heartbeat:
                self._hb_thread = threading.Thread(
                    target=self._heartbeat_loop, daemon=True, name=f"bago-hb-{self.node_id}"
                )
                self._hb_thread.start()
            return True
        return False

    def disconnect(self) -> None:
        """Gracefully disconnect from the bus."""
        self._running   = False
        self._connected = False
        self.emit("system.node_down", {"node_id": self.node_id, "reason": "graceful_disconnect"})

    def emit(
        self,
        topic: str,
        payload: dict,
        to: str = "*",
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        priority: int = 1,
    ) -> bool:
        """Publish an event to the bus. Thread-safe. Returns True on success."""
        data: dict = {
            "from":     self.node_id,
            "topic":    topic,
            "payload":  payload,
            "to":       to,
            "priority": priority,
        }
        if correlation_id:
            data["correlation_id"] = correlation_id
        if reply_to:
            data["reply_to"] = reply_to
        result = self._post("/emit", data)
        return result is not None and result.get("ok", False)

    def on(self, topic_pattern: str) -> Callable:
        """Decorator: register a handler for a topic pattern.

        Example:
            @node.on("user.message")
            def handle(event):
                print(event["payload"])

        Patterns:
            "user.message"  → exact match
            "user.*"        → user.message, user.response, user.context, …
            "*"             → all events
        """
        def decorator(fn: Callable) -> Callable:
            self._handlers.setdefault(topic_pattern, []).append(fn)
            return fn
        return decorator

    def subscribe(self, topic_pattern: str, callback: Callable) -> None:
        """Programmatic subscribe (alternative to @node.on decorator)."""
        self._handlers.setdefault(topic_pattern, []).append(callback)

    def run(self, block: bool = True) -> None:
        """Start the event listener.

        If block=True (default): runs until KeyboardInterrupt or disconnect().
        If block=False: starts a background thread and returns immediately.
        """
        if not self._connected:
            self.connect()

        self._stream_thread = threading.Thread(
            target=self._stream_loop,
            daemon=True,
            name=f"bago-stream-{self.node_id}",
        )
        self._stream_thread.start()

        if block:
            try:
                while self._running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.disconnect()

    def start_background(self) -> None:
        """Non-blocking: start the event listener in a daemon thread."""
        self.run(block=False)

    def wait_for(self, topic_pattern: str, timeout: float = 30.0) -> Optional[dict]:
        """Block until an event matching topic_pattern arrives, or timeout.

        Returns the event dict, or None on timeout.
        Useful for synchronous request/response patterns.
        """
        import queue as _q
        result_q: _q.Queue = _q.Queue(maxsize=1)

        def _capture(event: dict) -> None:
            try:
                result_q.put_nowait(event)
            except _q.Full:
                pass

        self.subscribe(topic_pattern, _capture)
        try:
            return result_q.get(timeout=timeout)
        except _q.Empty:
            return None

    # ── Internal loops ─────────────────────────────────────────────────────────

    def _heartbeat_loop(self) -> None:
        while self._running:
            self._post("/heartbeat", {"node_id": self.node_id})
            time.sleep(HEARTBEAT_INTERVAL)

    def _stream_loop(self) -> None:
        """Connect to SSE stream and dispatch events to handlers."""
        url = f"{self.bus_url}/stream?node={self.node_id}"
        headers = {**_make_headers(self._token), "Accept": "text/event-stream"}

        while self._running:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=None) as resp:
                    for line_bytes in resp:
                        if not self._running:
                            return
                        try:
                            line = line_bytes.decode("utf-8", errors="replace").rstrip()
                        except Exception:
                            continue
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        # Skip heartbeat pings
                        if raw.strip() in ('{"type": "connected"}', ': heartbeat'):
                            continue
                        try:
                            event = json.loads(raw)
                            self._dispatch(event)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                if self._running:
                    time.sleep(RECONNECT_DELAY)

    def _dispatch(self, event: dict) -> None:
        """Route an incoming event to matching handlers."""
        topic = event.get("topic", "")
        to    = event.get("to", "*")

        # Only process events directed to us or broadcast
        if to != "*" and to != self.node_id:
            return

        for pattern, handlers in list(self._handlers.items()):
            if self._topic_matches(pattern, topic):
                for handler in handlers:
                    try:
                        handler(event)
                    except Exception as exc:
                        print(
                            f"  [BusNode:{self.node_id}] Handler '{handler.__name__}' error: {exc}",
                            file=sys.stderr,
                        )

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic == prefix or topic.startswith(prefix + ".")
        return pattern == topic


# ── Self-test ──────────────────────────────────────────────────────────────────

def _self_test() -> int:
    results = []

    # Test 1: quick_emit returns False when bus not running (expected)
    ok1 = not quick_emit("test.event", {"data": 1}, from_node="test", bus_url="http://127.0.0.1:6789")
    results.append(("quick_emit_false_when_no_bus", ok1, "bus offline → False expected"))

    # Test 2: BusNode instantiation
    node = BusNode("test_node_1", role="test", capabilities=["a", "b"])
    ok2 = node.node_id == "test_node_1" and node.role == "test" and len(node.capabilities) == 2
    results.append(("busnode_instantiation", ok2, f"id={node.node_id}"))

    # Test 3: topic_matches
    cases = [
        ("*",        "anything",     True),
        ("user.*",   "user.message", True),
        ("user.*",   "tool.result",  False),
        ("user.*",   "user",         True),
        ("tool.req", "tool.req",     True),
        ("tool.req", "tool.result",  False),
    ]
    ok3 = all(BusNode._topic_matches(p, t) == exp for p, t, exp in cases)
    results.append(("topic_matches", ok3, f"{len(cases)} cases"))

    # Test 4: on() decorator registers handler
    node2 = BusNode("test_node_2")
    calls = []

    @node2.on("user.message")
    def handle(ev):
        calls.append(ev)

    node2._dispatch({"topic": "user.message", "to": "*", "payload": {"x": 1}})
    ok4 = len(calls) == 1 and calls[0]["payload"]["x"] == 1
    results.append(("on_decorator", ok4, f"calls={len(calls)}"))

    # Test 5: on() ignores non-matching events
    node2._dispatch({"topic": "tool.result", "to": "*", "payload": {}})
    ok5 = len(calls) == 1  # still 1
    results.append(("no_dispatch_wrong_topic", ok5, f"calls={len(calls)}"))

    # Test 6: directed event — wrong target ignored
    calls2 = []

    @node2.on("*")
    def handle_all(ev):
        calls2.append(ev)

    node2._dispatch({"topic": "user.message", "to": "other_node", "payload": {}})
    ok6 = len(calls2) == 0
    results.append(("directed_event_filtered", ok6, f"calls={len(calls2)}"))

    # Test 7: directed event — correct target received
    node2._dispatch({"topic": "user.message", "to": "test_node_2", "payload": {}})
    ok7 = len(calls2) == 1
    results.append(("directed_event_received", ok7, f"calls={len(calls2)}"))

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  BAGO Node Connector — Self-tests ({passed}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}  {detail}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
