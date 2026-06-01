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

import dataclasses
import json
import mimetypes
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bago_core"))

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
from commands import execute as execute_command
from control_shadow import ControlShadow
from rl_bridge import RLBridge


class BagoAPIHandler(BaseHTTPRequestHandler):
    """Handler HTTP para la API de BAGO."""

    # Se establece desde fuera antes de iniciar el servidor
    session_mgr: SessionManager | None = None
    switch_engine: SwitchEngine | None = None
    api_token: str = ""
    shadow: ControlShadow | None = None
    static_dir: Path | None = None
    api_prefixes = (
        "/status",
        "/session",
        "/history",
        "/providers",
        "/menu",
        "/models",
        "/chat",
        "/command",
        "/switch",
        "/catalog",
        "/simulation",
        "/rl",
    )

    @staticmethod
    def _cors_origin_allowed(origin: str) -> bool:
        if not origin:
            return False
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and parsed.hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if self._cors_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bago-Token, X-Bago-Channel")
        self.end_headers()
        self.wfile.write(json.dumps(self._json_safe(data), ensure_ascii=False).encode("utf-8"))

    def _send_bytes(self, status: int, content_type: str, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_safe(self, value: Any) -> Any:
        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [self._json_safe(v) for v in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            data = self.rfile.read(length).decode("utf-8")
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                pass
        return {}

    def _check_auth(self) -> bool:
        if not self.api_token:
            return True
        token = self.headers.get("X-Bago-Token", "")
        return token == self.api_token

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
                self._send_json(401, {"error": "Unauthorized — X-Bago-Token requerido"})
                return

            if path == "/status":
                self._handle_status()
            elif path == "/session":
                self._handle_session()
            elif path == "/history":
                self._handle_history()
            elif path == "/providers":
                self._handle_providers()
            elif path == "/menu":
                self._handle_menu()
            elif path == "/catalog/status":
                self._handle_catalog_status()
            elif path == "/simulation/status":
                self._handle_simulation_status()
            elif path == "/simulation/events":
                self._handle_simulation_events()
            elif path == "/rl/status":
                self._handle_rl_status()
            elif path.startswith("/models/"):
                provider = path.split("/")[-1]
                self._handle_models(provider)
            else:
                self._send_json(404, {"error": f"Ruta no encontrada: {path}"})
            return

        if self._serve_static(path):
            return

        self._send_json(404, {"error": f"Ruta no encontrada: {path}"})

    def do_POST(self) -> None:
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized — X-Bago-Token requerido"})
            return
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/chat":
            self._handle_chat(body)
        elif path == "/command":
            self._handle_command(body)
        elif path == "/switch":
            self._handle_switch(body)
        elif path == "/catalog/config":
            self._handle_catalog_config(body)
        elif path == "/simulation/config":
            self._handle_simulation_config(body)
        elif path == "/rl/shadow":
            self._handle_rl_shadow(body)
        else:
            self._send_json(404, {"error": f"Ruta no encontrada: {path}"})

    # ── Handlers ─────────────────────────────────────────────────────

    def _handle_status(self) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        self._send_json(200, mgr.status())

    def _handle_session(self) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        self._send_json(200, {
            "session_id": mgr.session_id,
            "provider": mgr.provider,
            "model": mgr.model,
            "status": mgr.status(),
            "active_agent": mgr.agent_gateway.active.name,
            "tool_calling": mgr.config.get("features.tool_calling", False),
            "model_catalog_mode": mgr.config.get("model_catalog.mode", "all"),
        })

    def _handle_history(self) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        history = mgr.store.get_history()
        self._send_json(200, {
            "session_id": mgr.session_id,
            "messages": history,
            "count": len(history),
        })

    def _handle_providers(self) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        providers = mgr.available_providers()
        self._send_json(200, {"providers": providers, "mode": mgr.config.get("model_catalog.mode", "all")})

    def _handle_menu(self) -> None:
        try:
            from repl import MENU_SECTIONS
        except Exception as exc:  # pragma: no cover - import defensivo
            # Culpa tecnica: responsable=import de MENU_SECTIONS; causa=ruta/paquete;
            # prevencion=fallback vacio para no romper la UI.
            self._send_json(200, {"sections": [], "error": f"menu no disponible: {exc}"})
            return
        self._send_json(200, {"sections": MENU_SECTIONS})

    def _handle_models(self, provider: str) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        catalog = mgr.list_model_catalog(provider)
        self._send_json(200, {
            "provider": provider,
            "mode": mgr.config.get("model_catalog.mode", "all"),
            "models": [item["id"] for item in catalog],
            "items": catalog,
        })

    def _handle_catalog_status(self) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        self._send_json(200, {
            "mode": mgr.config.get("model_catalog.mode", "all"),
            "production_mode": mgr.config.get("model_catalog.production_mode", "available-only"),
        })

    def _handle_catalog_config(self, body: dict[str, Any]) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        mode = str(body.get("mode", "")).strip()
        if mode not in ("all", "available-only"):
            self._send_json(400, {"error": "Modo inválido. Usa all|available-only"})
            return
        mgr.config.set("model_catalog.mode", mode)
        mgr._providers_cache = None
        self._send_json(200, {
            "ok": True,
            "mode": mode,
            "production_mode": mgr.config.get("model_catalog.production_mode", "available-only"),
        })

    def _channel(self, body: dict[str, Any]) -> str:
        return str(body.get("channel") or self.headers.get("X-Bago-Channel") or "api")

    def _record_shadow(
        self,
        *,
        action_kind: str,
        channel: str,
        payload: dict[str, Any],
        pre_state: dict[str, Any],
        post_state: dict[str, Any],
        result: dict[str, Any],
        elapsed_ms: float,
    ) -> None:
        if self.shadow is None or self.session_mgr is None:
            return
        try:
            self.shadow.log_event(
                mgr=self.session_mgr,
                channel=channel,
                action_kind=action_kind,
                payload=payload,
                pre_state=pre_state,
                post_state=post_state,
                result=result,
                elapsed_ms=elapsed_ms,
            )
        except Exception:
            return

    def _handle_chat(self, body: dict[str, Any]) -> None:
        mgr = self.session_mgr
        if mgr is None:
            self._send_json(503, {"error": "SessionManager no disponible"})
            return
        message = body.get("message", "")
        if not message:
            self._send_json(400, {"error": "Campo 'message' requerido"})
            return
        channel = self._channel(body)
        pre_state = mgr.status()
        started = time.time()
        try:
            response = mgr.send(message)
            payload = {
                "ok": True,
                "response": response,
                "session_id": mgr.session_id,
                "provider": mgr.provider,
                "model": mgr.model,
                "history_count": len(mgr.store.get_history()),
            }
            self._record_shadow(
                action_kind="chat",
                channel=channel,
                payload={"message": message},
                pre_state=pre_state,
                post_state=mgr.status(),
                result=payload,
                elapsed_ms=(time.time() - started) * 1000,
            )
            self._send_json(200, payload)
        except Exception as exc:
            payload = {"ok": False, "error": str(exc)}
            self._record_shadow(
                action_kind="chat",
                channel=channel,
                payload={"message": message},
                pre_state=pre_state,
                post_state=mgr.status(),
                result=payload,
                elapsed_ms=(time.time() - started) * 1000,
            )
            self._send_json(500, payload)

    def _handle_command(self, body: dict[str, Any]) -> None:
        mgr = self.session_mgr
        engine = self.switch_engine
        if mgr is None or engine is None:
            self._send_json(503, {"error": "SessionManager/SwitchEngine no disponible"})
            return
        command_line = str(body.get("command", "")).strip()
        if not command_line:
            self._send_json(400, {"error": "Campo 'command' requerido"})
            return
        if not command_line.startswith("/"):
            command_line = "/" + command_line
        channel = self._channel(body)
        pre_state = mgr.status()
        started = time.time()
        result = execute_command(command_line, mgr, engine)
        payload = {
            "ok": bool(result.get("ok")),
            "message": result.get("message", ""),
            "action": result.get("action"),
            "session_id": mgr.session_id,
            "provider": mgr.provider,
            "model": mgr.model,
            "data": self._json_safe(result.get("data", result.get("result"))),
            "plan": self._json_safe(result.get("plan")),
        }
        self._record_shadow(
            action_kind="command",
            channel=channel,
            payload={"command": command_line},
            pre_state=pre_state,
            post_state=mgr.status(),
            result=payload,
            elapsed_ms=(time.time() - started) * 1000,
        )
        self._send_json(200 if payload["ok"] else 400, payload)

    def _handle_switch(self, body: dict[str, Any]) -> None:
        mgr = self.session_mgr
        engine = self.switch_engine
        if mgr is None or engine is None:
            self._send_json(503, {"error": "SessionManager/SwitchEngine no disponible"})
            return
        provider = body.get("provider", "")
        model = body.get("model")
        force = body.get("force", False)
        if not provider:
            self._send_json(400, {"error": "Campo 'provider' requerido"})
            return
        channel = self._channel(body)
        pre_state = mgr.status()
        started = time.time()
        try:
            result = engine.execute(mgr, provider, model, force=force)
            payload = {
                "ok": result.ok,
                "message": result.message,
                "provider": mgr.provider,
                "model": mgr.model,
            }
            self._record_shadow(
                action_kind="switch",
                channel=channel,
                payload={"provider": provider, "model": model, "force": force},
                pre_state=pre_state,
                post_state=mgr.status(),
                result=payload,
                elapsed_ms=(time.time() - started) * 1000,
            )
            self._send_json(200 if result.ok else 400, payload)
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _handle_simulation_status(self) -> None:
        shadow = self.shadow
        if shadow is None:
            self._send_json(503, {"error": "ControlShadow no disponible"})
            return
        self._send_json(200, shadow.status())

    def _handle_simulation_events(self) -> None:
        shadow = self.shadow
        if shadow is None:
            self._send_json(503, {"error": "ControlShadow no disponible"})
            return
        self._send_json(200, {"events": shadow.recent_events()})

    def _handle_simulation_config(self, body: dict[str, Any]) -> None:
        shadow = self.shadow
        if shadow is None:
            self._send_json(503, {"error": "ControlShadow no disponible"})
            return
        try:
            status = shadow.configure(enabled=body.get("enabled"), mode=body.get("mode"))
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, status)

    def _rl_bridge(self) -> RLBridge | None:
        mgr = self.session_mgr
        if mgr is None:
            return None
        return RLBridge(mgr.base_path)

    def _handle_rl_status(self) -> None:
        bridge = self._rl_bridge()
        if bridge is None:
            self._send_json(503, {"error": "RLBridge no disponible"})
            return
        self._send_json(200, bridge.status())

    def _handle_rl_shadow(self, body: dict[str, Any]) -> None:
        bridge = self._rl_bridge()
        if bridge is None:
            self._send_json(503, {"error": "RLBridge no disponible"})
            return
        enabled = bool(body.get("enabled", True))
        self._send_json(200, bridge.shadow(enabled))


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
        self._server = HTTPServer((self.host, self.port), BagoAPIHandler)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[API] Servidor iniciado en http://{self.host}:{self.port}")
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
            assert catalog_status["mode"] == "all"

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/models/mock-ui", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                models = json.loads(resp.read().decode("utf-8"))
            assert "offline-model" in models["models"]

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

            catalog_req = urllib.request.Request(
                f"{base_url}/catalog/config",
                data=json.dumps({"mode": "available-only"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(catalog_req, timeout=5) as resp:
                catalog = json.loads(resp.read().decode("utf-8"))
            assert catalog["mode"] == "available-only"

            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/models/mock-ui", headers={"X-Bago-Token": "test-token"}), timeout=5) as resp:
                filtered_models = json.loads(resp.read().decode("utf-8"))
            assert "mock-model" in filtered_models["models"]
            assert "offline-model" not in filtered_models["models"]

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
    parser.add_argument("--provider", default="ollama-local")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--ui-dist", default="")
    args = parser.parse_args()

    mgr = SessionManager(provider=args.provider, model=args.model)
    engine = SwitchEngine(mgr.adapters)
    server = BagoAPIServer(mgr, engine, port=args.port, token=args.token, static_dir=args.ui_dist or None)
    server.start()
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
