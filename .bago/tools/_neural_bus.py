#!/usr/bin/env python3
from __future__ import annotations
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

"""_neural_bus.py — Transporte y estado del BAGO Neural Bus."""
import json, os, queue, sys, time, threading, uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set

from bago.ollama_runtime import DEFAULT_BAGO_HUB_PORT

# ── Paths ──────────────────────────────────────────────────────────────────────
TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = Path(os.environ.get("BAGO_NEURAL_STATE_DIR", str(BAGO_ROOT / "state")))
STATE_DIR.mkdir(parents=True, exist_ok=True)

BUS_LOG        = STATE_DIR / "neural_bus.jsonl"
NODE_REGISTRY  = STATE_DIR / "neural_nodes.json"
BUS_PID        = STATE_DIR / "neural_bus.pid"
TOKEN_FILE     = STATE_DIR / "neural_token.txt"

DEFAULT_PORT     = int(os.environ.get("BAGO_NEURAL_PORT", 6789))
DEFAULT_BUS_URL  = os.environ.get("BAGO_NEURAL_URL", f"http://localhost:{DEFAULT_PORT}")
MAX_BUFFER       = int(os.environ.get("BAGO_NEURAL_MAX_BUFFER", 1000))
MAX_SUBSCRIBERS  = int(os.environ.get("BAGO_NEURAL_MAX_SUBS", 50))
HEARTBEAT_TTL    = int(os.environ.get("BAGO_NEURAL_HEARTBEAT_TTL", 120))
SUBSCRIBER_QUEUE = int(os.environ.get("BAGO_NEURAL_QUEUE_SIZE", 200))
# CORS origin: default allows bago_hub on 7860 but configurable for any port
_CORS_ORIGIN     = os.environ.get("BAGO_HUB_ORIGIN", f"http://localhost:{os.environ.get('BAGO_HUB_PORT', DEFAULT_BAGO_HUB_PORT)}")

# Durable topics (persisted to JSONL)
DURABLE_TOPICS = {
    "user.message", "user.response",
    "tool.request", "tool.result",
    "llm.request", "llm.response", "llm.tool_suggestion",
    "workflow.started", "workflow.completed", "workflow.failed",
    "system.node_up", "system.node_down", "system.bus_up",
}

# ── Auth token ─────────────────────────────────────────────────────────────────

def _get_or_create_token() -> str:
    """Return the shared local auth token (auto-generated if missing)."""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    token = uuid.uuid4().hex
    TOKEN_FILE.write_text(token, encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    return token


_TOKEN: str = ""  # populated in start_server()


def _check_auth(headers) -> bool:
    """Validate X-Bago-Token header. Skip auth if token is empty (dev mode)."""
    if not _TOKEN:
        return True
    provided = headers.get("X-Bago-Token", "") or headers.get("x-bago-token", "")
    return provided == _TOKEN

# ── Core state (in-memory) ─────────────────────────────────────────────────────

_lock = threading.RLock()
_events_buffer: List[dict] = []
_subscribers: Dict[str, Set[Callable]] = defaultdict(set)  # topic_pattern → callbacks
_nodes: Dict[str, dict] = {}  # node_id → info dict

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _make_event(
    from_node: str,
    topic: str,
    payload: dict,
    to: str = "*",
    correlation_id: Optional[str] = None,
    reply_to: Optional[str] = None,
    durable: Optional[bool] = None,
    priority: int = 1,
) -> dict:
    if durable is None:
        # Auto-detect durability based on topic prefix
        durable = any(topic == t or topic.startswith(t + ".") for t in DURABLE_TOPICS)
    ev: dict = {
        "id": uuid.uuid4().hex[:8],
        "ts": _now_iso(),
        "from": from_node,
        "to": to,
        "topic": topic,
        "payload": payload,
        "durable": durable,
        "priority": priority,
    }
    if correlation_id:
        ev["correlation_id"] = correlation_id
    if reply_to:
        ev["reply_to"] = reply_to
    return ev


def _append_to_log(event: dict) -> None:
    try:
        with open(BUS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _store_event(event: dict) -> None:
    with _lock:
        _events_buffer.append(event)
        if len(_events_buffer) > MAX_BUFFER:
            _events_buffer.pop(0)
    if event.get("durable", False):
        _append_to_log(event)


def _topic_matches(pattern: str, topic: str) -> bool:
    """Glob match: 'user.*' matches 'user.message'; '*' matches all."""
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return topic == prefix or topic.startswith(prefix + ".")
    return pattern == topic


def emit_event(
    from_node: str,
    topic: str,
    payload: dict,
    to: str = "*",
    correlation_id: Optional[str] = None,
    reply_to: Optional[str] = None,
    durable: Optional[bool] = None,
    priority: int = 1,
) -> dict:
    event = _make_event(from_node, topic, payload, to, correlation_id, reply_to, durable, priority)
    _store_event(event)
    _broadcast_to_subscribers(event)
    return event


def _broadcast_to_subscribers(event: dict) -> None:
    """Send event to all matching subscriber queues (non-blocking)."""
    topic = event["topic"]
    # Build a snapshot of matching callbacks under lock, then call without lock
    to_notify: List[Callable] = []
    with _lock:
        for pattern, subs in _subscribers.items():
            if _topic_matches(pattern, topic):
                to_notify.extend(list(subs))  # copy set to list
    for callback in to_notify:
        try:
            callback(event)
        except Exception:
            pass


def register_node(node_id: str, info: dict) -> None:
    with _lock:
        _nodes[node_id] = {
            **info,
            "node_id": node_id,
            "registered_at": _now_iso(),
            "last_seen": _now_iso(),
            "status": "active",
        }
    _save_registry()
    emit_event("bus", "system.node_up", {"node_id": node_id, **info})


def heartbeat_node(node_id: str) -> None:
    with _lock:
        if node_id in _nodes:
            _nodes[node_id]["last_seen"] = _now_iso()
            _nodes[node_id]["status"] = "active"


def get_nodes() -> dict:
    """Return a snapshot of all registered nodes with freshness status."""
    now = time.time()
    with _lock:
        result = {}
        for nid, info in _nodes.items():
            entry = dict(info)
            last_ts = info.get("last_seen", "")
            if last_ts:
                try:
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                    age = now - last_dt.timestamp()
                    entry["age_seconds"] = round(age)
                    if age > HEARTBEAT_TTL:
                        entry["status"] = "stale"
                except Exception:
                    pass
            result[nid] = entry
    return result


def get_recent_events(
    since_id: Optional[str] = None,
    topic_filter: Optional[str] = None,
    limit: int = 100,
) -> list:
    with _lock:
        events = list(_events_buffer)

    if since_id:
        found = False
        result = []
        for e in events:
            if found:
                result.append(e)
            if e["id"] == since_id:
                found = True
        events = result

    if topic_filter:
        events = [e for e in events if _topic_matches(topic_filter, e["topic"])]

    return events[-limit:]


def _save_registry() -> None:
    try:
        with _lock:
            data = dict(_nodes)
        NODE_REGISTRY.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass

# ── Stale node watchdog ─────────────────────────────────────────────────────────

def _stale_watchdog() -> None:
    """Background thread: marks nodes as stale if heartbeat missing."""
    while True:
        time.sleep(60)
        now = time.time()
        stale = []
        with _lock:
            for nid, info in _nodes.items():
                last_ts = info.get("last_seen", "")
                if last_ts:
                    try:
                        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                        age = now - last_dt.timestamp()
                        if age > HEARTBEAT_TTL and info.get("status") != "stale":
                            _nodes[nid]["status"] = "stale"
                            stale.append(nid)
                    except Exception:
                        pass
        for nid in stale:
            emit_event("bus", "system.node_stale", {"node_id": nid, "reason": "heartbeat_timeout"})

# ── HTTP Handler ───────────────────────────────────────────────────────────────

class _BusHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access log

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", _CORS_ORIGIN)
        self.end_headers()
        self.wfile.write(body)

    def _send_err(self, msg: str, status: int = 400) -> None:
        self._send_json({"error": msg}, status)

    def _read_body(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            pass
        return {}

    def _require_auth(self) -> bool:
        if not _check_auth(self.headers):
            self._send_json({"error": "Unauthorized — X-Bago-Token required"}, status=401)
            return False
        return True

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", _CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bago-Token")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        raw_query = self.path[len(path) + 1:] if "?" in self.path else ""
        params: dict = {}
        for part in raw_query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v

        if path == "/":
            self._send_json({
                "name": "BAGO Neural Bus",
                "version": "1.0",
                "status": "running",
                "port": DEFAULT_PORT,
                "nodes": len(get_nodes()),
                "events_buffered": len(_events_buffer),
                "log": str(BUS_LOG),
            })

        elif path == "/nodes":
            self._send_json(get_nodes())

        elif path == "/events":
            since = params.get("since")
            topic = params.get("topic")
            limit = min(int(params.get("limit", 100)), 500)
            self._send_json({
                "events": get_recent_events(since_id=since, topic_filter=topic, limit=limit),
            })

        elif path == "/stream":
            # SSE — keep connection alive
            node_id = params.get("node", "stream_client")
            topic_filter = params.get("topic", "*")

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", _CORS_ORIGIN)
            self.end_headers()

            # Check subscriber limit
            with _lock:
                total_subs = sum(len(s) for s in _subscribers.values())
            if total_subs >= MAX_SUBSCRIBERS:
                try:
                    self.wfile.write(b"data: {\"error\": \"max_subscribers_reached\"}\n\n")
                    self.wfile.flush()
                except Exception:
                    pass
                return

            q: queue.Queue = queue.Queue(maxsize=SUBSCRIBER_QUEUE)

            def on_event(event: dict) -> None:
                # Respect directed messages
                to = event.get("to", "*")
                if to != "*" and to != node_id:
                    return
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass  # drop on overflow — non-critical

            with _lock:
                _subscribers[topic_filter].add(on_event)

            try:
                self.wfile.write(b"data: {\"type\": \"connected\"}\n\n")
                self.wfile.flush()

                while True:
                    try:
                        event = q.get(timeout=20)
                        data = json.dumps(event, ensure_ascii=False, default=str)
                        msg = f"data: {data}\n\n".encode("utf-8")
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        # heartbeat comment to keep connection alive
                        try:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, OSError):
                            break
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with _lock:
                    _subscribers[topic_filter].discard(on_event)

        elif path == "/map":
            nodes = get_nodes()
            lines = ["# BAGO Neural Network Map", ""]
            lines.append(f"Nodos conectados: {len(nodes)}")
            lines.append(f"Eventos en buffer: {len(_events_buffer)}")
            lines.append("")

            # Node list
            for nid, info in nodes.items():
                role = info.get("role", "node")
                status = info.get("status", "?")
                icon = "🟢" if status == "active" else "🟡"
                caps = info.get("capabilities", [])
                cap_str = f"  [{', '.join(caps)}]" if caps else ""
                lines.append(f"  {icon} {nid:25s} ({role}){cap_str}")
            lines.append("")

            # Mermaid diagram
            lines.append("```mermaid")
            lines.append("graph LR")
            lines.append('  bus["🧠 BAGO\\nNeural Bus"]')
            lines.append('  style bus fill:#1a1a2e,stroke:#4da8ff,color:#4da8ff')

            role_colors = {
                "input": "#2d4a2d",
                "output": "#4a2d2d",
                "processing": "#2d2d4a",
                "memory": "#4a3d2d",
                "tool": "#3d4a2d",
                "monitor": "#4a2d4a",
            }
            for nid, info in nodes.items():
                role = info.get("role", "node")
                color = role_colors.get(role, "#1a1a2e")
                safe_id = nid.replace("-", "_").replace(".", "_")
                lines.append(
                    f'  {safe_id}["{nid}\\n{role}"]'
                    f'  style {safe_id} fill:{color},stroke:#555,color:#ccc'
                )
                lines.append(f"  {safe_id} <--> bus")
            lines.append("```")

            body = "\n".join(lines).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self._send_err(f"Unknown path: {path}", 404)

    def do_POST(self):
        if not self._require_auth():
            return

        path = self.path.split("?")[0]
        body = self._read_body() or {}

        if path == "/emit":
            from_node = body.get("from", "unknown")
            topic = body.get("topic", "")
            payload = body.get("payload", {})
            to = body.get("to", "*")
            corr = body.get("correlation_id")
            reply_to = body.get("reply_to")
            durable = body.get("durable")
            priority = body.get("priority", 1)

            if not topic:
                self._send_err("topic is required")
                return
            if not isinstance(payload, dict):
                self._send_err("payload must be a JSON object")
                return

            event = emit_event(from_node, topic, payload, to, corr, reply_to, durable, priority)
            self._send_json({"ok": True, "event_id": event["id"], "ts": event["ts"]})

        elif path == "/register":
            node_id = body.get("node_id", "")
            if not node_id:
                self._send_err("node_id is required")
                return
            info = {k: v for k, v in body.items() if k != "node_id"}
            register_node(node_id, info)
            self._send_json({"ok": True, "node_id": node_id})

        elif path == "/heartbeat":
            node_id = body.get("node_id", "")
            if not node_id:
                self._send_err("node_id is required")
                return
            heartbeat_node(node_id)
            self._send_json({"ok": True, "ts": _now_iso()})

        else:
            self._send_err(f"Unknown path: {path}", 404)

# ── Server ─────────────────────────────────────────────────────────────────────

class _ThreadingBusServer(HTTPServer):
    """HTTPServer variant that spawns a thread per request."""

    def process_request(self, request, client_address):
        t = threading.Thread(
            target=self._process_request_thread,
            args=(request, client_address),
            daemon=True,
        )
        t.start()

    def _process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def start_server(port: int = DEFAULT_PORT) -> None:
    global _TOKEN
    _TOKEN = _get_or_create_token()

    server = _ThreadingBusServer(("127.0.0.1", port), _BusHandler)
    server.allow_reuse_address = True

    # Write PID
    BUS_PID.write_text(str(os.getpid()), encoding="utf-8")

    # Start stale watchdog
    wd = threading.Thread(target=_stale_watchdog, daemon=True)
    wd.start()

    # Emit startup event
    startup = _make_event("bus", "system.bus_up", {
        "port": port, "pid": os.getpid(), "log": str(BUS_LOG),
        "token_file": str(TOKEN_FILE),
    }, durable=True)
    _store_event(startup)

    print(f"  🧠 BAGO Neural Bus v1.0")
    print(f"  ● HTTP      http://127.0.0.1:{port}/")
    print(f"  ● SSE       http://127.0.0.1:{port}/stream")
    print(f"  ● Nodes     http://127.0.0.1:{port}/nodes")
    print(f"  ● Map       http://127.0.0.1:{port}/map")
    print(f"  ● Log       {BUS_LOG}")
    print(f"  ● Token     {TOKEN_FILE}")
    print(f"  (Ctrl+C para detener)\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  🛑 Neural Bus detenido.")
    finally:
        BUS_PID.unlink(missing_ok=True)
        server.server_close()


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())

