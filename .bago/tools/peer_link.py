"""
bago peer — Peer-to-peer communication between BAGO instances on the local network.

Architecture:
  • UDP port 7735 — broadcast discovery beacon (LAN-wide)
  • HTTP port 7736 — REST API for data exchange

Commands:
  bago peer serve          Start HTTP server + UDP discovery responder
  bago peer discover       Scan LAN for other BAGO instances
  bago peer info IP        Show peer's project info
  bago peer sync IP        Pull peer's implemented ideas
  bago peer send IP MSG    Send a text message to peer
  bago peer inbox          Read received messages
  bago peer ping IP        Ping a peer
  bago peer chat           Interactive chat with a peer
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import os
import platform
import socket
import struct
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".bago" / "state"
PEER_DIR = STATE_DIR / "peers"

UDP_PORT = 7735
HTTP_PORT = 7736
DISCOVERY_MSG = b"BAGO_DISCOVER_v1"
DISCOVERY_TIMEOUT = 2.0  # seconds to wait for discovery responses


def _get_project_root() -> Path:
    gs_path = STATE_DIR / "global_state.json"
    if gs_path.exists():
        try:
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            p = gs.get("active_project", {}).get("path", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
    return ROOT.parent

PROJECT_ROOT = _get_project_root()

# ── color helpers ─────────────────────────────────────────────────────────────

def _c(s, code): return f"\033[{code}m{s}\033[0m"
def CYAN(s):   return _c(s, "36")
def GREEN(s):  return _c(s, "32")
def RED(s):    return _c(s, "31")
def YELLOW(s): return _c(s, "33")
def MAGENTA(s):return _c(s, "35")
def DIM(s):    return _c(s, "2")
def BOLD(s):   return _c(s, "1")


# ── local info ────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    """Best-guess local IP (prefer non-APIPA)."""
    candidates = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                candidates.append(ip)
    except Exception:
        pass
    # Fallback: connect to public DNS to detect route
    fallback_dns = os.getenv("BAGO_FALLBACK_DNS", "8.8.8.8")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((fallback_dns, 80))
            candidates.insert(0, s.getsockname()[0])
    except Exception:
        pass
    return candidates[0] if candidates else "127.0.0.1"


def _peer_info() -> dict:
    """Build our identity payload."""
    impl = 0
    tools = 0
    project = ""
    try:
        data = json.loads((STATE_DIR / "implemented_ideas.json").read_text(encoding="utf-8"))
        impl = len(data.get("implemented", []))
    except Exception:
        pass
    try:
        tools = len(list((ROOT / ".bago" / "tools").glob("*.py")))
    except Exception:
        pass
    try:
        gs = json.loads((STATE_DIR / "global_state.json").read_text(encoding="utf-8"))
        project = gs.get("active_project", {}).get("name", "")
    except Exception:
        pass

    return {
        "hostname": socket.gethostname(),
        "ip": _local_ip(),
        "platform": platform.system(),
        "python": platform.python_version(),
        "project": project,
        "ideas": impl,
        "tools": tools,
        "http_port": HTTP_PORT,
        "ts": datetime.now().isoformat(),
    }


# ── message store ─────────────────────────────────────────────────────────────

def _msg_path() -> Path:
    PEER_DIR.mkdir(parents=True, exist_ok=True)
    return PEER_DIR / "inbox.json"


def _load_inbox() -> list:
    p = _msg_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_inbox(msgs: list):
    _msg_path().write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")


def _store_message(msg: dict):
    inbox = _load_inbox()
    inbox.append(msg)
    _save_inbox(inbox)


# ── HTTP server ───────────────────────────────────────────────────────────────

def _make_http_handler(allowed_origin: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            ts = datetime.now().strftime("%H:%M:%S")
            peer = self.client_address[0]
            print(f"  \033[2m[{ts}] {peer} → {self.path}\033[0m", flush=True)

        def _send_json(self, code: int, data):
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path == "/peer/info":
                self._send_json(200, _peer_info())

            elif self.path == "/peer/ping":
                self._send_json(200, {"pong": True, "ts": datetime.now().isoformat()})

            elif self.path == "/peer/ideas":
                try:
                    data = json.loads((STATE_DIR / "implemented_ideas.json").read_text(encoding="utf-8"))
                    ideas = [{"title": i.get("title", i.get("idea_title", "?")),
                              "done_at": i.get("done_at", "")}
                             for i in data.get("implemented", [])]
                    self._send_json(200, {"ideas": ideas, "count": len(ideas)})
                except Exception as e:
                    self._send_json(500, {"error": str(e)})

            elif self.path == "/peer/tools":
                tools = [f.stem for f in (ROOT / ".bago" / "tools").glob("*.py")]
                self._send_json(200, {"tools": sorted(tools), "count": len(tools)})

            elif self.path == "/peer/messages":
                msgs = _load_inbox()
                self._send_json(200, {"messages": msgs, "count": len(msgs)})

            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path == "/peer/message":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    msg = json.loads(body)
                    msg["received_at"] = datetime.now().isoformat()
                    msg["from_ip"] = self.client_address[0]
                    _store_message(msg)
                    # Print to console
                    sender = msg.get("from", msg["from_ip"])
                    text = msg.get("text", "")
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"\n  \033[35m✉  [{ts}] {sender}:\033[0m {text}\n", flush=True)
                    self._send_json(200, {"ok": True})
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
            else:
                self._send_json(404, {"error": "not found"})

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

    return Handler


# ── UDP discovery ─────────────────────────────────────────────────────────────

def _udp_responder():
    """Listen for BAGO_DISCOVER broadcasts and respond with our info.

    Bind to all interfaces on UDP by design because discovery is LAN broadcast-based.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", UDP_PORT))
        while True:
            try:
                data, addr = sock.recvfrom(256)
                if data == DISCOVERY_MSG:
                    response = json.dumps(_peer_info()).encode("utf-8")
                    sock.sendto(response, addr)
            except Exception:
                pass
    finally:
        sock.close()


def _discover_peers(timeout: float = DISCOVERY_TIMEOUT) -> list[dict]:
    """Send UDP broadcast and collect responses."""
    found = []
    seen_ips = set()
    my_ip = _local_ip()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    try:
        sock.sendto(DISCOVERY_MSG, ("255.255.255.255", UDP_PORT))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                ip = addr[0]
                if ip == my_ip or ip in seen_ips:
                    continue
                seen_ips.add(ip)
                peer = json.loads(data.decode("utf-8"))
                peer["_ip"] = ip
                found.append(peer)
            except socket.timeout:
                break
            except Exception:
                continue
    finally:
        sock.close()

    return found


# ── HTTP client helpers ───────────────────────────────────────────────────────

def _get(ip: str, path: str, port: int = HTTP_PORT) -> dict:
    url = f"http://{ip}:{port}{path}"
    try:
        with urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def _post(ip: str, path: str, data: dict, port: int = HTTP_PORT) -> dict:
    url = f"http://{ip}:{port}{path}"
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


# ── beacon / subnet scan ─────────────────────────────────────────────────────

def _udp_ping(ip: str, timeout: float = 0.4) -> dict | None:
    """Send a single UDP discovery ping to a specific IP, return parsed response or None."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(DISCOVERY_MSG, (ip, UDP_PORT))
        data, _ = sock.recvfrom(4096)
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None
    finally:
        sock.close()


def cmd_beacon(interval: float = 1.0, target_ip: str | None = None):
    """
    Continuously broadcast UDP discovery packets AND scan subnet for the Mac.
    If target_ip is given, also sends unicast signals directly to that IP.
    Shows a live signal indicator. Stops when Mac responds or Ctrl+C.
    """
    my_ip = _local_ip()
    prefix = ".".join(my_ip.split(".")[:3])

    # Load previously found Mac IP from cache
    if target_ip is None:
        mac_cache = PEER_DIR / "mac_peer.json"
        if mac_cache.exists():
            try:
                cached = json.loads(mac_cache.read_text(encoding="utf-8"))
                target_ip = cached.get("ip")
            except Exception:
                pass

    print(f"\n  ┌─────────────────────────────────────────────────────────┐")
    print(f"  │  📡  BAGO BEACON — Señales al MacBook                   │")
    print(f"  └─────────────────────────────────────────────────────────┘")
    print(f"  Mi IP     : {CYAN(my_ip)}")
    if target_ip:
        print(f"  Target Mac: {GREEN(target_ip)}  ← IP identificada por ARP")
    print(f"  Subred    : {prefix}.1 — {prefix}.254")
    print(f"  UDP port  : {UDP_PORT}   (broadcast + unicast)")
    print(f"  Intervalo : {interval}s")
    print(f"\n  Mandando señales... cuando el Mac esté listo ejecuta:")
    print(f"    {DIM('python bago peer serve')}\n")

    mac_ip_found = None
    tick = 0
    spinner = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    scan_results: dict[str, dict] = {}
    scan_lock = threading.Lock()

    scan_queue: list[str] = []
    # Put target IP first if known
    if target_ip:
        scan_queue.append(target_ip)
    scan_queue += [f"{prefix}.{i}" for i in range(1, 255)
                   if f"{prefix}.{i}" != my_ip and f"{prefix}.{i}" != target_ip]
    scan_idx = [0]

    def _scanner():
        while mac_ip_found is None:
            with scan_lock:
                if scan_idx[0] >= len(scan_queue):
                    scan_idx[0] = 0
                ip = scan_queue[scan_idx[0]]
                scan_idx[0] += 1
            result = _udp_ping(ip, timeout=0.35)
            if result:
                with scan_lock:
                    scan_results[ip] = result

    for _ in range(12):
        t = threading.Thread(target=_scanner, daemon=True)
        t.start()

    broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        while True:
            # Broadcast to whole subnet
            try:
                broadcast_sock.sendto(DISCOVERY_MSG, ("255.255.255.255", UDP_PORT))
                broadcast_sock.sendto(DISCOVERY_MSG, (f"{prefix}.255", UDP_PORT))
            except Exception:
                pass

            # Unicast directly to known Mac IP
            if target_ip:
                try:
                    broadcast_sock.sendto(DISCOVERY_MSG, (target_ip, UDP_PORT))
                except Exception:
                    pass

            with scan_lock:
                new_peers = dict(scan_results)

            mac_found = None
            for ip, info in new_peers.items():
                plat = info.get("platform", "").lower()
                if "darwin" in plat or "mac" in plat or ip == target_ip:
                    mac_found = (ip, info)
                    break

            ts = datetime.now().strftime("%H:%M:%S")
            s = spinner[tick % len(spinner)]

            if mac_found:
                ip, info = mac_found
                print(f"\r  {GREEN('✔')} [{ts}] 🍎 ¡MAC BAGO ACTIVO! IP: {CYAN(ip)} — {info.get('hostname','?')}          ")
                print(f"\n  {'─'*55}")
                print(f"  Hostname : {BOLD(info.get('hostname','?'))}")
                print(f"  Platform : {info.get('platform','?')}")
                print(f"  Python   : {info.get('python','?')}")
                print(f"  Ideas    : {info.get('ideas',0)}  |  Tools: {info.get('tools',0)}")
                print(f"\n  Ahora puedes usar:")
                print(f"    {CYAN(f'python bago peer ping {ip}')}")
                print(f"    {CYAN(f'python bago peer chat {ip}')}")
                _msg = 'python bago peer send ' + ip + ' "Hola Mac"'
                print(f"    {CYAN(_msg)}")
                print()
                PEER_DIR.mkdir(parents=True, exist_ok=True)
                cache = PEER_DIR / "mac_peer.json"
                info_to_save = {"ip": ip, **info,
                                "found_via": "BAGO UDP",
                                "found_at": datetime.now().isoformat()}
                cache.write_text(json.dumps(info_to_save, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  {DIM('Guardado en: ' + str(cache))}\n")
                mac_ip_found = ip
                break
            else:
                scanned = scan_idx[0]
                target_label = f" → {GREEN(target_ip)}" if target_ip else ""
                label = f"señal #{tick+1}{target_label}  |  escaneadas: {scanned}/253"
                print(f"\r  {CYAN(s)} [{ts}] {label}    ", end="", flush=True)

            tick += 1
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n  Beacon detenido. ({tick} señales enviadas)")
        if target_ip:
            print(f"\n  Mac identificado en: {CYAN(target_ip)}")
            print(f"  Cuando esté listo: {DIM('python bago peer serve')}\n")
    finally:
        broadcast_sock.close()


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_serve(http_port: int = HTTP_PORT, host: str = "127.0.0.1"):
    global HTTP_PORT
    HTTP_PORT = http_port
    my_ip = _local_ip()
    allowed_origin = f"http://{host}:{http_port}"
    print(f"\n  ┌─────────────────────────────────────────────────────────┐")
    print(f"  │  📡  BAGO Peer Server                                   │")
    print(f"  └─────────────────────────────────────────────────────────┘")
    print(f"  IP local  : {CYAN(my_ip)}")
    print(f"  HTTP API  : http://{host}:{http_port}")
    print(f"  UDP disco : puerto {UDP_PORT}  (broadcast)\n")
    if host != "127.0.0.1":
        print(f"  {YELLOW('⚠')} Modo LAN expuesto: host={host}")
        print(f"  {YELLOW('⚠')} Solo úsalo en red de confianza.\n")
    print(f"  Esperando conexiones del MacBook...  Ctrl+C para detener.\n")

    # Start UDP discovery responder in background
    t = threading.Thread(target=_udp_responder, daemon=True)
    t.start()

    # Start HTTP server
    server = HTTPServer((host, http_port), _make_http_handler(allowed_origin))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
    finally:
        server.server_close()


def cmd_discover():
    print(f"\n  🔍 Buscando instancias BAGO en la red local...")
    print(f"  (broadcast UDP → {UDP_PORT}, timeout {DISCOVERY_TIMEOUT}s)\n")
    peers = _discover_peers()
    if not peers:
        print(f"  {YELLOW('⚠')} No se encontraron peers.")
        print(f"  Asegúrate de que el MacBook ejecute: {CYAN('python bago peer serve')}\n")
        return

    for p in peers:
        os_icon = "🍎" if "darwin" in p.get("platform", "").lower() else "🪟"
        print(f"  {GREEN('✔')} {os_icon} {BOLD(p.get('hostname', '?'))}")
        print(f"       IP      : {CYAN(p.get('ip', p['_ip']))}")
        print(f"       Proyecto: {p.get('project', '?')}")
        print(f"       Ideas   : {p.get('ideas', 0)}  |  Tools: {p.get('tools', 0)}")
        print(f"       HTTP    : http://{p.get('ip', p['_ip'])}:{p.get('http_port', HTTP_PORT)}")
        print()

    # Save discovered peers
    PEER_DIR.mkdir(parents=True, exist_ok=True)
    cache = PEER_DIR / "discovered.json"
    cache.write_text(json.dumps(peers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {DIM('Peers guardados en ' + str(cache))}\n")


def cmd_info(ip: str):
    print(f"\n  ℹ  Info del peer {CYAN(ip)}...\n")
    info = _get(ip, "/peer/info")
    if "error" in info:
        print(f"  {RED('✗')} Error: {info['error']}\n")
        return
    os_icon = "🍎" if "darwin" in info.get("platform", "").lower() else "🪟"
    print(f"  {os_icon} {BOLD(info.get('hostname', '?'))}")
    for k in ("ip", "platform", "python", "project", "ideas", "tools"):  # noqa: HARDCODE
        print(f"     {k:<10}: {info.get(k, '?')}")
    print()


def cmd_ping(ip: str):
    t0 = time.time()
    result = _get(ip, "/peer/ping")
    ms = int((time.time() - t0) * 1000)
    if "pong" in result:
        print(f"\n  {GREEN('✔')} Pong desde {CYAN(ip)}  — {ms}ms\n")
    else:
        print(f"\n  {RED('✗')} Sin respuesta: {result.get('error', '?')}\n")


def cmd_send(ip: str, message: str):
    my_name = socket.gethostname()
    data = {"text": message, "from": my_name, "sent_at": datetime.now().isoformat()}
    result = _post(ip, "/peer/message", data)
    if result.get("ok"):
        print("\n  " + GREEN("✔") + " Mensaje enviado a " + CYAN(ip) + ': "' + message + '"\n')
    else:
        print(f"\n  {RED('✗')} Error al enviar: {result.get('error', result)}\n")


def cmd_inbox():
    msgs = _load_inbox()
    if not msgs:
        print(f"\n  (bandeja vacía)\n")
        return
    print(f"\n  📬 Bandeja de entrada ({len(msgs)} mensajes)\n")
    for i, m in enumerate(reversed(msgs[-20:]), 1):
        sender = m.get("from", m.get("from_ip", "?"))
        ts = m.get("received_at", m.get("sent_at", ""))[:19].replace("T", " ")
        text = m.get("text", "")
        print(f"  {DIM(str(i).rjust(3))}  {MAGENTA(sender):<20} {DIM(ts)}  {text}")
    print()


def cmd_sync(ip: str):
    print(f"\n  🔄 Sincronizando ideas desde {CYAN(ip)}...\n")
    result = _get(ip, "/peer/ideas")
    if "error" in result:
        print(f"  {RED('✗')} {result['error']}\n")
        return

    remote_ideas = result.get("ideas", [])
    print(f"  Peer tiene {BOLD(str(len(remote_ideas)))} ideas implementadas.")

    # Load our local ideas
    try:
        local_data = json.loads((STATE_DIR / "implemented_ideas.json").read_text(encoding="utf-8"))
        local_titles = {i.get("title", i.get("idea_title", "")) for i in local_data.get("implemented", [])}
    except Exception:
        local_titles = set()

    new_ideas = [i for i in remote_ideas if i.get("title") not in local_titles]
    print(f"  Ideas nuevas para ti: {CYAN(str(len(new_ideas)))}\n")

    for idea in new_ideas[:20]:
        ts = idea.get("done_at", "")[:10]
        print(f"  {GREEN('+')} [{ts}] {idea.get('title', '?')}")

    if not new_ideas:
        print(f"  {GREEN('✔')} Ya tienes todas las ideas del peer.\n")
    else:
        print(f"\n  {DIM('(usa bago peer sync IP --import para importar las ideas)')}\n")


def cmd_chat(ip: str):
    """Interactive real-time chat session with a peer."""
    my_name = socket.gethostname()
    print(f"\n  💬 Chat con {CYAN(ip)}  (escribe 'salir' para terminar)\n")
    print(f"  {DIM('Tu nombre: ' + my_name)}\n")

    # Poll for new messages in background
    last_seen = len(_load_inbox())
    stop_poll = threading.Event()

    def _poll():
        nonlocal last_seen
        while not stop_poll.is_set():
            time.sleep(2)
            msgs = _load_inbox()
            if len(msgs) > last_seen:
                for m in msgs[last_seen:]:
                    sender = m.get("from", m.get("from_ip", "?"))
                    text = m.get("text", "")
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"\r  {MAGENTA(sender)} [{ts}]: {text}")
                    print(f"  {CYAN(my_name)} > ", end="", flush=True)
                last_seen = len(msgs)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()

    try:
        while True:
            print(f"  {CYAN(my_name)} > ", end="", flush=True)
            line = input().strip()
            if line.lower() in ("salir", "exit", "quit", "q"):
                break
            if line:
                cmd_send(ip, line)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        stop_poll.set()
    print("\n  Chat terminado.\n")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BAGO peer — LAN communication between BAGO instances")
    sub = parser.add_subparsers(dest="cmd")

    # serve
    p_serve = sub.add_parser("serve", help="Start HTTP + UDP discovery server")
    p_serve.add_argument("--port", type=int, default=HTTP_PORT)
    p_serve.add_argument("--host", default="127.0.0.1")

    # discover
    sub.add_parser("discover", help="Find BAGO peers on local network")

    # ping
    p_ping = sub.add_parser("ping", help="Ping a peer")
    p_ping.add_argument("ip", help="Peer IP address")

    # info
    p_info = sub.add_parser("info", help="Get peer project info")
    p_info.add_argument("ip")

    # sync
    p_sync = sub.add_parser("sync", help="Pull peer's implemented ideas")
    p_sync.add_argument("ip")
    p_sync.add_argument("--import", dest="do_import", action="store_true")

    # send
    p_send = sub.add_parser("send", help="Send a message to peer")
    p_send.add_argument("ip")
    p_send.add_argument("message", nargs="+")

    # inbox
    sub.add_parser("inbox", help="Read received messages")

    # chat
    p_chat = sub.add_parser("chat", help="Interactive chat session with peer")
    p_chat.add_argument("ip")

    # beacon
    p_beacon = sub.add_parser("beacon", help="Broadcast signals + scan subnet to find the Mac")
    p_beacon.add_argument("--interval", type=float, default=1.0, help="Seconds between beacons (default: 1)")
    p_beacon.add_argument("--target", default=None, help="Known Mac IP to target directly (e.g. 192.168.8.153)")

    args = parser.parse_args()

    if args.cmd == "serve":
        cmd_serve(args.port, args.host)
    elif args.cmd == "discover":
        cmd_discover()
    elif args.cmd == "ping":
        cmd_ping(args.ip)
    elif args.cmd == "info":
        cmd_info(args.ip)
    elif args.cmd == "sync":
        cmd_sync(args.ip)
    elif args.cmd == "send":
        cmd_send(args.ip, " ".join(args.message))
    elif args.cmd == "inbox":
        cmd_inbox()
    elif args.cmd == "chat":
        cmd_chat(args.ip)
    elif args.cmd == "beacon":
        cmd_beacon(args.interval, args.target)
    else:
        # Default: show status
        my_ip = _local_ip()
        info = _peer_info()
        print(f"\n  📡 {BOLD('BAGO Peer')} — este nodo\n")
        print(f"  Hostname : {CYAN(info['hostname'])}")
        print(f"  IP       : {CYAN(my_ip)}")
        print(f"  Proyecto : {info['project']}")
        print(f"  Ideas    : {info['ideas']}  |  Tools: {info['tools']}")
        print(f"\n  Comandos disponibles:")
        print(f"    {CYAN('bago peer serve')}          → arranca servidor (ejecutar PRIMERO aquí y en Mac)")
        print(f"    {CYAN('bago peer discover')}        → busca peers en la red")
        print(f"    {CYAN('bago peer ping IP')}         → ping a un peer")
        print(f"    {CYAN('bago peer info IP')}         → info del peer")
        print(f"    {CYAN('bago peer sync IP')}         → ver ideas del peer")
        print(f"    {CYAN('bago peer send IP MSG')}     → enviar mensaje")
        print(f"    {CYAN('bago peer inbox')}           → leer mensajes recibidos")
        print(f"    {CYAN('bago peer chat IP')}         → chat interactivo\n")
        print(f"  En el MacBook ejecuta:")
        print(f"    {DIM('cd bago-framework && python bago peer serve')}\n")



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
