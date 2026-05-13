"""
Servidor HTTP para Casino BAGO Mini App.
- Sirve index.html y assets estáticos
- Expone API REST en /api/* para lógica de juego server-side
- Compatible con ngrok (bypass header incluido)
"""

import http.server
import socketserver
import os
import json
import sys
import time
import threading
import urllib.parse

PORT = int(os.getenv("WEBAPP_PORT", 8080))
DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, DIR)

import db

# ─── Rate limiter (in-memory, per UID) ───────────────────────────────────────
_spin_times: dict[int, float] = {}
_spin_lock = threading.Lock()
SPIN_MIN_INTERVAL = 0.8  # segundos mínimos entre giros por usuario

def _check_rate(uid: int) -> bool:
    """Devuelve True si el spin está permitido, False si es demasiado rápido."""
    now = time.monotonic()
    with _spin_lock:
        last = _spin_times.get(uid, 0.0)
        if now - last < SPIN_MIN_INTERVAL:
            return False
        _spin_times[uid] = now
        return True


# ─── Headers CORS + ngrok ─────────────────────────────────────────────────────

COMMON_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, ngrok-skip-browser-warning",
    "Cache-Control": "no-cache",
    "ngrok-skip-browser-warning": "true",
}


class CasinoHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass  # silenciar logs de acceso

    def end_headers(self):
        for k, v in COMMON_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/player":
            self._api_get_player(params)
        elif path == "/api/jackpot":
            self._api_jackpot()
        elif path == "/api/leaderboard":
            self._api_leaderboard()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/spin":
            self._api_spin(body)
        elif path == "/api/daily":
            self._api_daily(body)
        elif path == "/api/ensure":
            self._api_ensure(body)
        elif path == "/api/self-exclude":
            self._api_self_exclude(body)
        elif path == "/api/ton/order":
            self._api_ton_order(body)
        elif path == "/api/ton/confirm":
            self._api_ton_confirm(body)
        elif path == "/api/ton/orders":
            self._api_ton_orders(body)
        else:
            self._json_response(404, {"error": "not_found"})

    # ── API handlers ──────────────────────────────────────────────────────────

    def _api_ensure(self, body: dict):
        uid = self._require_uid(body)
        if uid is None:
            return
        username = str(body.get("username", ""))
        referred_by = body.get("referred_by")
        if referred_by:
            try:
                referred_by = int(referred_by)
            except (ValueError, TypeError):
                referred_by = None
        player = db.ensure_player(uid, username=username, referred_by=referred_by)

        # Bonus por primera conexión de cartera (atómico, solo una vez por usuario)
        wallet_bonus = body.get("wallet_bonus")
        if wallet_bonus and str(wallet_bonus) == "100":
            player = db.apply_wallet_bonus(uid)

        player["jackpot_pool"] = db.get_jackpot()
        self._json_response(200, player)

    def _api_get_player(self, params: dict):
        try:
            uid = int(params.get("uid", [None])[0])
        except (TypeError, ValueError):
            self._json_response(400, {"error": "missing uid"})
            return
        player = db.get_player(uid)
        if player is None:
            self._json_response(404, {"error": "player_not_found"})
            return
        player["jackpot_pool"] = db.get_jackpot()
        self._json_response(200, player)

    def _api_spin(self, body: dict):
        uid = self._require_uid(body)
        if uid is None:
            return
        # Rate limiting anti-spam
        if not _check_rate(uid):
            self._json_response(429, {"error": "too_fast", "retry_after": SPIN_MIN_INTERVAL})
            return
        try:
            bet = int(body.get("bet", 10))
            if bet < 5 or bet > 500:
                raise ValueError
        except (ValueError, TypeError):
            self._json_response(400, {"error": "invalid bet (5-500)"})
            return
        result = db.do_spin(uid, bet)
        self._json_response(200, result)

    def _api_daily(self, body: dict):
        uid = self._require_uid(body)
        if uid is None:
            return
        result = db.claim_daily(uid)
        self._json_response(200, result)

    def _api_self_exclude(self, body: dict):
        uid = self._require_uid(body)
        if uid is None:
            return
        player = db.self_exclude(uid)
        self._json_response(200, {"ok": True, "self_excluded": True, "uid": uid})

    def _api_ton_order(self, body: dict):
        """Crea una orden de compra TON. Devuelve order_id + amount_nanoton."""
        uid = self._require_uid(body)
        if uid is None:
            return
        package_id = str(body.get("package_id", ""))
        if not package_id:
            self._json_response(400, {"error": "missing package_id"})
            return
        operator_wallet = os.getenv("OPERATOR_TON_WALLET", "")
        if not operator_wallet:
            self._json_response(503, {"error": "ton_not_configured"})
            return
        order = db.create_ton_order(uid, package_id)
        if "error" in order:
            self._json_response(400, order)
            return
        order["to_address"] = operator_wallet
        self._json_response(200, order)

    def _api_ton_confirm(self, body: dict):
        """Confirma una orden TON y acredita fichas. Idempotente."""
        order_id = str(body.get("order_id", "")).strip()
        boc = str(body.get("boc", "")).strip()
        if not order_id:
            self._json_response(400, {"error": "missing order_id"})
            return
        result = db.confirm_ton_purchase(order_id, boc)
        if "error" in result:
            self._json_response(400, result)
            return
        self._json_response(200, result)

    def _api_ton_orders(self, body: dict):
        """Historial de órdenes TON del usuario."""
        uid = self._require_uid(body)
        if uid is None:
            return
        orders = db.get_ton_orders(uid)
        self._json_response(200, {"orders": orders})

    def _api_jackpot(self):
        self._json_response(200, {"jackpot_pool": db.get_jackpot()})

    def _api_leaderboard(self):
        self._json_response(200, {"leaderboard": db.get_leaderboard(10)})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _require_uid(self, body: dict) -> int | None:
        try:
            uid = int(body.get("uid"))
            return uid
        except (TypeError, ValueError):
            self._json_response(400, {"error": "missing or invalid uid"})
            return None

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw)
        except Exception:
            return {}

    def _json_response(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ─── Servidor ─────────────────────────────────────────────────────────────────

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def run_server():
    with ReusableTCPServer(("", PORT), CasinoHandler) as httpd:
        print(f"🎰 Casino API+UI en: http://localhost:{PORT}/index.html", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    print(f"{'='*50}")
    print(f"  Casino BAGO — API Server  (port {PORT})")
    print(f"{'='*50}")
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n🛑 Servidor parado.")
