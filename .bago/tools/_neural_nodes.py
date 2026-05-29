from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso
"""_neural_nodes.py — Comandos CLI cliente del BAGO Neural Bus."""
import json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _neural_bus import DEFAULT_BUS_URL, DEFAULT_PORT, TOKEN_FILE

# ── Colors ─────────────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty() and sys.platform != "win32"

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t

OK   = lambda t: _c("1;32", t)   # noqa: E731
WARN = lambda t: _c("1;33", t)   # noqa: E731
ERR  = lambda t: _c("1;31", t)   # noqa: E731
BOLD = lambda t: _c("1", t)      # noqa: E731
DIM  = lambda t: _c("2", t)      # noqa: E731
CYAN = lambda t: _c("1;36", t)   # noqa: E731

# ── CLI commands ───────────────────────────────────────────────────────────────

def _load_token(token_file: Optional[str] = None) -> str:
    """Load token from file or TOKEN_FILE."""
    path = Path(token_file) if token_file else TOKEN_FILE
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _make_headers(token: str) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Bago-Token"] = token
    return h


def cmd_status(bus_url: str, token: str) -> int:
    import urllib.request
    try:
        req = urllib.request.Request(f"{bus_url}/", headers=_make_headers(token))
        with urllib.request.urlopen(req, timeout=3) as resp:
            info = json.loads(resp.read())
        print(f"  {OK('●')} BAGO Neural Bus activo en {bus_url}")
        print(f"  Nodos: {info.get('nodes', 0)}")
        print(f"  Eventos en buffer: {info.get('events_buffered', 0)}")
        return 0
    except Exception:
        print(f"  {ERR('●')} Bus no disponible en {bus_url}")
        print(f"  Inicia con: bago neural serve")
        return 1


def cmd_nodes(bus_url: str, token: str) -> int:
    import urllib.request
    try:
        req = urllib.request.Request(f"{bus_url}/nodes", headers=_make_headers(token))
        with urllib.request.urlopen(req, timeout=5) as resp:
            nodes = json.loads(resp.read())
    except Exception as e:
        print(f"  {ERR('✗')} {e}")
        return 1

    if not nodes:
        print("  Sin nodos registrados.")
        return 0

    print(f"\n  🧠 BAGO Neural Bus — {len(nodes)} nodos\n")
    for nid, info in sorted(nodes.items()):
        role = info.get("role", "node")
        status = info.get("status", "?")
        icon = OK("●") if status == "active" else WARN("●")
        caps = ", ".join(info.get("capabilities", []))
        age = info.get("age_seconds", "?")
        print(f"  {icon} {BOLD(nid):30s}  [{role:12s}]  age={age}s")
        if caps:
            print(f"    {'':30s}  caps: {caps}")
    print()
    return 0


def cmd_emit(bus_url: str, token: str, topic: str, payload_str: str,
             from_node: str = "cli", to: str = "*") -> int:
    import urllib.request
    try:
        payload = json.loads(payload_str) if payload_str.strip().startswith("{") else {"text": payload_str}
    except json.JSONDecodeError:
        payload = {"text": payload_str}

    data = json.dumps({
        "from": from_node, "topic": topic, "payload": payload, "to": to,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{bus_url}/emit", data=data, headers=_make_headers(token), method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print(f"  {OK('✓')} [{topic}] → event_id={result.get('event_id', '?')}")
        return 0
    except Exception as e:
        print(f"  {ERR('✗')} {e}")
        return 1


def cmd_tail(bus_url: str, token: str, topic_filter: str = "*") -> int:
    import urllib.request
    url = f"{bus_url}/stream?topic={topic_filter}&node=cli_tail"
    print(f"  🧠 Neural Bus tail [{topic_filter}]  (Ctrl+C para parar)\n")
    try:
        req = urllib.request.Request(url, headers={**_make_headers(token), "Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=None) as resp:
            for line_bytes in resp:
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if '"type": "connected"' in raw:
                    print(f"  {DIM('→')} Conectado\n")
                    continue
                try:
                    ev = json.loads(raw)
                    ts   = ev.get("ts", "")[-8:] or "?"
                    frm  = ev.get("from", "?")
                    top  = ev.get("topic", "?")
                    pay  = ev.get("payload", {})
                    print(f"  {DIM(ts)}  {CYAN(frm[:18]):22s}  {BOLD(top):30s}  {str(pay)[:60]}")
                except Exception:
                    print(f"  {raw[:100]}")
    except KeyboardInterrupt:
        print("\n  Stopped.")
        return 0
    except Exception as e:
        print(f"  {ERR('✗')} {e}")
        return 1


def cmd_map(bus_url: str, token: str) -> int:
    import urllib.request
    try:
        req = urllib.request.Request(f"{bus_url}/map", headers=_make_headers(token))
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(resp.read().decode("utf-8"))
        return 0
    except Exception as e:
        print(f"  {ERR('✗')} Bus no disponible: {e}")
        return 1
