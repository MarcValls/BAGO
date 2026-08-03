#!/usr/bin/env python3
"""
api_bridge.py — BAGO HTTP API Bridge

Servidor HTTP simple para integraciones externas.
Expone endpoints REST para chat, status, providers, y switches.

Uso:
    python api_bridge.py --port 8080 --token my-secret
    python bago_core/cli.py serve --port 8080
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _load_chat_timeout_from_env(default: float) -> float:
    """Lee BAGO_API_CHAT_TIMEOUT (segundos) y lo convierte a float.

    Valores inválidos se ignoran y se devuelve ``default``. Un valor de 0
    desactiva el watchdog (las llamadas pueden colgar — útil solo para
    diagnóstico).
    """
    raw = os.environ.get("BAGO_API_CHAT_TIMEOUT", "")
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value < 0:
        return default
    return value

# Make the repo root + .bago submodules importable. The repo root lets
# `import bago_core.version` resolve (bago_core is a real package).
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))                            # repo root
sys.path.insert(0, str(_REPO_ROOT / "bago_core"))             # direct (legacy)
sys.path.insert(0, str(_REPO_ROOT / ".bago" / "core"))        # session_manager, switch_engine
sys.path.insert(0, str(_REPO_ROOT / ".bago" / "chat"))        # repl_*, renderer, etc.
# LEGACY[API-L001]: direct legacy imports stay only while un-migrated handlers exist.

_CREATED_VERSION = "4.0.0"

try:
    from version import CURRENT as _BAGO_VERSION
except ImportError:
    import json as _json
    _BAGO_VERSION = _json.loads(
        (Path(__file__).resolve().parents[2] / "versions.json").read_text(encoding="utf-8")
    )["current"]

from session_manager import SessionManager
from switch_engine import SwitchEngine
from control_shadow import ControlShadow

from api_auth import BagoAuthMixin, _load_cors_origins_from_env
from api_dispatch import API_PREFIXES as _API_PREFIXES, resolve_get, resolve_post, resolve_router
from api_serializers import json_safe, read_body, send_bytes, send_json
from api_state import resolve_state_root
from rate_limit import get_limiter
from structured_log import get_logger


class BagoAPIHandler(BagoAuthMixin, BaseHTTPRequestHandler):
    """Handler HTTP para la API de BAGO.

    Responsibilities (post-modularization):
      - HTTP plumbing (parse request, write response)
      - Auth + CORS (delegated to BagoAuthMixin)
      - JSON I/O (delegated to api_serializers)
      - Routing (delegated to api_dispatch)

    Handler logic for each domain (status, memory, chat, etc.) lives in
    `handlers_<domain>.py` and is invoked via api_dispatch. The legacy
    `_handle_*` methods on this class are kept as a fallback for endpoints
    that haven't been migrated yet.
    """

    MAX_BODY_BYTES = 1024 * 1024
    api_prefixes = _API_PREFIXES  # used by _is_api_path

    # Timeout por defecto (segundos) para /chat. Se puede sobreescribir con
    # BAGO_API_CHAT_TIMEOUT. Un valor de 0 desactiva el watchdog.
    DEFAULT_CHAT_TIMEOUT_S: float = 120.0

    # Se establece desde fuera antes de iniciar el servidor
    session_mgr: SessionManager | None = None
    switch_engine: SwitchEngine | None = None
    api_token: str = ""
    shadow: ControlShadow | None = None
    static_dir: Path | None = None
    chat_timeout_s: float = 120.0
    # api_prefixes comes from api_dispatch.API_PREFIXES so adding a new
    # route there (e.g. /router) automatically updates _is_api_path.
    # CORS + auth methods come from BagoAuthMixin (api_auth.py).
    # JSON serialization / body parsing delegate to api_serializers so
    # there is a single source of truth. Thin wrappers keep call sites
    # unchanged (self._send_json etc.).

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        send_json(self, status, data)

    def _send_bytes(self, status: int, content_type: str, data: bytes) -> None:
        send_bytes(self, status, content_type, data)

    def _json_safe(self, value: Any) -> Any:
        return json_safe(value)

    def _read_body(self) -> dict[str, Any]:
        body = read_body(self, self.MAX_BODY_BYTES)
        if body.get("_error") == "payload_too_large":
            raise ValueError("Payload demasiado grande")
        return body

    def _is_api_path(self, path: str) -> bool:
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in self.api_prefixes)

    def _serve_static(self, path: str) -> bool:
        if self.static_dir is None:
            return False
        static_root = self.static_dir.resolve()
        relative = path.lstrip("/") or "index.html"
        candidate = (static_root / relative).resolve()
        try:
            candidate.relative_to(static_root)
        except ValueError:
            self._send_json(403, {"error": "Ruta estática inválida"})
            return True

        if candidate.is_file():
            content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            self._send_bytes(200, content_type, candidate.read_bytes())
            return True

        if path in ("", "/") or "." not in Path(relative).name:
            index_file = static_root / "index.html"
            if index_file.is_file():
                self._send_bytes(200, "text/html; charset=utf-8", index_file.read_bytes())
                return True

        return False

    def log_message(self, format: str, *args: Any) -> None:
        # Silenciar logs por defecto; imprimir solo en debug
        if os.environ.get("BAGO_API_DEBUG"):
            sys.stderr.write(f"[API] {format % args}\n")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bago-Token, X-Bago-Channel")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if self._is_api_path(path):
            if not self._check_auth():
                get_logger().warn("auth_failed", path=path, client=self.client_address[0])
                self._send_json(401, {"error": "Unauthorized \u2014 X-Bago-Token requerido"})
                return

            get_logger().info("get_request", path=path)

            # 1. Try the modular dispatch table (handlers_<domain>.py).
            matched, call = resolve_get(self, path)
            if matched:
                call(self)
                return

            # LEGACY[API-L002]: keep fallback only for endpoints not yet migrated.
            # Each branch below calls a _handle_* method defined elsewhere.
            self._send_json(404, {"error": f"Ruta no encontrada: {path}"})
            return

        # API-shaped paths must never fall through to the SPA fallback.
        if path.startswith("/api/") or any(path.startswith(f"{p}/") for p in self.api_prefixes + ("/node",)):
            self._send_json(404, {"error": f"Ruta no encontrada: {path}"})
            return

        if self._serve_static(path):
            return

        self._send_json(404, {"error": f"Ruta no encontrada: {path}"})

    def do_POST(self) -> None:
        if not self._check_auth():
            get_logger().warn("auth_failed", path=self.path, client=self.client_address[0])
            self._send_json(401, {"error": "Unauthorized \u2014 X-Bago-Token requerido"})
            return
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_body()
        except ValueError as exc:
            get_logger().warn("payload_too_large", path=path, error=str(exc))
            self._send_json(413, {"error": str(exc)})
            return

        # Rate-limit check for chat/switch (heavy endpoints)
        if path in ("/chat", "/switch"):
            provider = self.session_mgr.provider if self.session_mgr else "ollama-cloud"
            allowed, detail = get_limiter().check(provider)
            if not allowed:
                get_logger().warn("rate_limited", path=path, provider=provider, detail=detail)
                self._send_json(429, {"error": "Rate limit exceeded", "detail": detail})
                return

        get_logger().info("post_request", path=path, has_body=bool(body))

        # 1. Try the modular dispatch table.
        matched, call = resolve_post(self, path, body)
        if matched:
            call(self, body)
            return

        # Pattern routes (e.g. /router/toggle/<key>).
        matched, call = resolve_router(self, path, body)
        if matched:
            call(self, body)
            return

        self._send_json(404, {"error": f"Ruta no encontrada: {path}"})

    # ── Handlers ─────────────────────────────────────────────────────
    # LEGACY[API-L003]: keep only HTTP plumbing here; migrated endpoints live
    # in handlers_<domain>.py and are wired by api_dispatch.

    def _resolve_state_root(self) -> Path:
        """Resolve the state root from the session manager (mirrors repl.state_root)."""
        return resolve_state_root(self)


class BagoAPIServer:
    """Servidor HTTP API para BAGO."""

    def __init__(
        self,
        session_mgr: SessionManager,
        switch_engine: SwitchEngine,
        port: int = 8080,
        host: str = "127.0.0.1",
        token: str = "",
        static_dir: str | Path | None = None,
    ):
        if host != "127.0.0.1" and not token:
            raise RuntimeError(
                f"No se puede exponer BAGO en {host} sin token de autenticación. "
                "Proporciona --token o usa --host 127.0.0.1."
            )
        self.session_mgr = session_mgr
        self.switch_engine = switch_engine
        self.port = port
        self.host = host
        self.token = token
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        # v0.3: pasar state_root canónico; base_path solo como fallback legacy.
        # session_mgr.state_root existe siempre (ver session_manager.py:210).
        _sm_state_root = getattr(session_mgr, "state_root", None)
        if _sm_state_root is not None:
            self.shadow = ControlShadow(state_root=str(_sm_state_root))
        else:
            self.shadow = ControlShadow(base_path=str(session_mgr.base_path))
        if static_dir:
            candidate = Path(static_dir).resolve()
            self.static_dir = candidate if candidate.exists() else None
        else:
            self.static_dir = None

    def start(self) -> None:
        BagoAPIHandler.session_mgr = self.session_mgr
        BagoAPIHandler.switch_engine = self.switch_engine
        BagoAPIHandler.api_token = self.token
        BagoAPIHandler.shadow = self.shadow
        BagoAPIHandler.static_dir = self.static_dir
        BagoAPIHandler.extra_cors_origins = _load_cors_origins_from_env()
        if BagoAPIHandler.extra_cors_origins:
            print(f"[API] CORS extra origins: {sorted(BagoAPIHandler.extra_cors_origins)}")
        BagoAPIHandler.chat_timeout_s = _load_chat_timeout_from_env(
            BagoAPIHandler.DEFAULT_CHAT_TIMEOUT_S
        )
        print(f"[API] /chat timeout: {BagoAPIHandler.chat_timeout_s:g}s "
              f"(BAGO_API_CHAT_TIMEOUT, 0=desactivado)")
        self._server = ThreadingHTTPServer((self.host, self.port), BagoAPIHandler)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[API] Servidor iniciado en http://{self.host}:{self.port}")
        get_logger().info("server_started", host=self.host, port=self.port, has_token=bool(self.token))
        if self.token:
            print(f"[API] Token requerido: {self.token[:4]}***")
        else:
            print("[API] Sin token — acceso permitido solo desde localhost")
        if self.static_dir:
            print(f"[API] UI React servida desde: {self.static_dir}")

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            print("[API] Servidor detenido.")
            get_logger().info("server_stopped")

    @property
    def running(self) -> bool:
        return self._server is not None


def _run_tests() -> int:
    import tempfile
    import urllib.request
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse
    from session_manager import ADAPTER_REGISTRY

    class MockAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("mock-ui", config)

        def chat(self, messages: list[dict], model: str, **kwargs: Any) -> ProviderResponse:
            last = messages[-1]["content"] if messages else ""
            return ProviderResponse(content=f"echo::{last}", provider=self.provider_name, model_used=model)

        def list_models(self) -> list[ModelInfo]:
            return [
                ModelInfo("mock-model", "mock-model", self.provider_name, 4096, 1024, "test", "local", available=True),
                ModelInfo("offline-model", "offline-model", self.provider_name, 4096, 1024, "test", "local", available=False),
            ]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok", models_available=1)

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

    ADAPTER_REGISTRY["mock-ui"] = MockAdapter
    with tempfile.TemporaryDirectory() as td:
        ui_dist = Path(td) / "ui-dist"
        (ui_dist / "assets").mkdir(parents=True, exist_ok=True)
        (ui_dist / "index.html").write_text("<!doctype html><html><body>bago-ui</body></html>", encoding="utf-8")
        (ui_dist / "assets" / "app.js").write_text("console.log('bago-ui')", encoding="utf-8")
        mgr = SessionManager(base_path=td, provider="mock-ui", model="mock-model")
        try:
            engine = SwitchEngine(mgr.adapters)
            server = BagoAPIServer(mgr, engine, port=0, token="test-token", static_dir=ui_dist)
            server.start()
            base_url = f"http://127.0.0.1:{server.port}"
            headers = {"X-Bago-Token": "test-token", "Content-Type": "application/json", "X-Bago-Channel": "terminal"}

            with urllib.request.urlopen(f"{base_url}/", timeout=5) as resp:
                index_html = resp.read().decode("utf-8")
            assert "bago-ui" in index_html

            with urllib.request.urlopen(f"{base_url}/desktop", timeout=5) as resp:
                desktop_html = resp.read().decode("utf-8")
            assert "bago-ui" in desktop_html

            with urllib.request.urlopen(f"{base_url}/assets/app.js", timeout=5) as resp:
                asset_body = resp.read().decode("utf-8")
            assert "bago-ui" in asset_body

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/status", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                status = json.loads(resp.read().decode("utf-8"))
            assert status["provider"] == "mock-ui"

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/catalog/status", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                catalog_status = json.loads(resp.read().decode("utf-8"))
            # The user's persistent config may override the default; only assert a valid shape.
            assert catalog_status["mode"] in ("all", "available-only")
            assert "production_mode" in catalog_status

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/models/mock-ui", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                models = json.loads(resp.read().decode("utf-8"))
            # Catalog mode may be user-persistent; assert at least the online model is visible.
            assert "mock-model" in models["models"]

            catalog_req = urllib.request.Request(
                f"{base_url}/catalog/config",
                data=json.dumps({"mode": "all"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(catalog_req, timeout=5) as resp:
                catalog = json.loads(resp.read().decode("utf-8"))
            assert catalog["mode"] == "all"

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/models/mock-ui", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                all_models = json.loads(resp.read().decode("utf-8"))
            assert "mock-model" in all_models["models"]
            assert "offline-model" in all_models["models"]

            catalog_req2 = urllib.request.Request(
                f"{base_url}/catalog/config",
                data=json.dumps({"mode": "available-only"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(catalog_req2, timeout=5) as resp:
                catalog2 = json.loads(resp.read().decode("utf-8"))
            assert catalog2["mode"] == "available-only"

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/models/mock-ui", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                filtered_models = json.loads(resp.read().decode("utf-8"))
            assert "mock-model" in filtered_models["models"]
            assert "offline-model" not in filtered_models["models"]

            chat_req = urllib.request.Request(
                f"{base_url}/chat",
                data=json.dumps({"message": "hola"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(chat_req, timeout=5) as resp:
                chat = json.loads(resp.read().decode("utf-8"))
            assert chat["response"] == "echo::hola"

            history_req = urllib.request.Request(f"{base_url}/history", headers={"X-Bago-Token": "test-token"})
            with urllib.request.urlopen(history_req, timeout=5) as resp:
                history = json.loads(resp.read().decode("utf-8"))
            assert history["count"] == 2

            cmd_req = urllib.request.Request(
                f"{base_url}/command",
                data=json.dumps({"command": "/status", "channel": "desktop"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(cmd_req, timeout=5) as resp:
                cmd = json.loads(resp.read().decode("utf-8"))
            assert cmd["ok"] is True
            assert cmd["data"]["provider"] == "mock-ui"
            assert cmd["data"]["model"] == "mock-model"



            sim_req = urllib.request.Request(f"{base_url}/simulation/status", headers={"X-Bago-Token": "test-token"})
            with urllib.request.urlopen(sim_req, timeout=5) as resp:
                sim = json.loads(resp.read().decode("utf-8"))
            assert sim["mode"] == "shadow"

            rl_req = urllib.request.Request(f"{base_url}/rl/status", headers={"X-Bago-Token": "test-token"})
            with urllib.request.urlopen(rl_req, timeout=5) as resp:
                rl_status = json.loads(resp.read().decode("utf-8"))
            assert rl_status["can_execute"] is False

            rl_shadow_req = urllib.request.Request(
                f"{base_url}/rl/shadow",
                data=json.dumps({"enabled": False}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(rl_shadow_req, timeout=5) as resp:
                rl_shadow = json.loads(resp.read().decode("utf-8"))
            assert rl_shadow["mode"] == "off"
            assert rl_shadow["can_execute"] is False

            plan_req = urllib.request.Request(
                f"{base_url}/command",
                data=json.dumps({"command": "/plan demo"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(plan_req, timeout=5) as resp:
                plan = json.loads(resp.read().decode("utf-8"))
            assert "message" in plan
            assert plan["plan"]["task"] == "demo"

            print("api_bridge.py --test: ALL PASS")
        finally:
            if "server" in locals():
                server.stop()
            mgr.close()
            ADAPTER_REGISTRY.pop("mock-ui", None)
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    # Modo standalone
    import argparse
    parser = argparse.ArgumentParser(description=f"BAGO {_BAGO_VERSION} API Bridge")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--token", default="")
    parser.add_argument("--provider", default="ollama-cloud")
    parser.add_argument("--model", default="deepseek-v3.1:671b")
    parser.add_argument("--ui-dist", default="")
    args = parser.parse_args()

    mgr = SessionManager(provider=args.provider, model=args.model)
    from handlers_router import restore_session_model
    restore_session_model(mgr)
    # Auto-allow tool execution so file-write and other tools run without a manual approval step
    mgr.set_tool_approval_policy("always")
    engine = SwitchEngine(mgr.adapters)
    server = BagoAPIServer(mgr, engine, port=args.port, token=args.token, static_dir=args.ui_dist or None)
    server.start()
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
