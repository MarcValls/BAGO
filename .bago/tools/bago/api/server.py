"""bago.api.server — FastAPI server for BAGO API.

Compatible con endpoints Ollama + extensiones BAGO (routing, health, escalate).

Usage:
    python -m bago.api.server              # default port <BAGO_API_PORT>
    python -m bago.api.server --port <PORT>   # custom port
    bago serve                              # via CLI
"""

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

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import (
    chat_router, generate_router, embed_router,
    models_router, bago_router,
)
from .models.schemas import VersionResponse
from bago.cwd import get_user_cwd
from bago.ollama_runtime import (
    DEFAULT_BAGO_API_PORT,
    DEFAULT_BAGO_COPILOT_PORT,
    DEFAULT_BAGO_CODEX_PORT,
    DEFAULT_BAGO_OLLAMA_CLOUD_PORT,
    DEFAULT_BAGO_TELEGRAM_PORT,
    DEFAULT_BAGO_UTOPIA_PORT,
    default_ollama_base_url,
    default_ollama_port,
    env_port,
)

# ─── Port map ─────────────────────────────────────────────────────────────────

BAGO_API_PORT = env_port("BAGO_API_PORT", "BAGO_PORT", default=DEFAULT_BAGO_API_PORT)
BAGO_COPILOT_PORT = env_port("BAGO_COPILOT_PORT", "BAGO_PORT", default=DEFAULT_BAGO_COPILOT_PORT)
BAGO_CODEX_PORT = env_port("BAGO_CODEX_PORT", "BAGO_PORT", default=DEFAULT_BAGO_CODEX_PORT)
BAGO_OLLAMA_CLOUD_PORT = env_port("BAGO_OLLAMA_CLOUD_PORT", "BAGO_PORT", default=DEFAULT_BAGO_OLLAMA_CLOUD_PORT)
BAGO_TELEGRAM_PORT = env_port("BAGO_TELEGRAM_PORT", "BAGO_PORT", default=DEFAULT_BAGO_TELEGRAM_PORT)
BAGO_UTOPIA_PORT = env_port("BAGO_UTOPIA_PORT", "BAGO_PORT", default=DEFAULT_BAGO_UTOPIA_PORT)

SERVICE_PORTS = {
    "ollama-local":   default_ollama_port(),  # Ollama nativo
    "bago":           BAGO_API_PORT,  # Este servidor
    "copilot":        BAGO_COPILOT_PORT,  # GitHub Models proxy
    "codex":          BAGO_CODEX_PORT,  # OpenAI proxy
    "ollama-cloud":   BAGO_OLLAMA_CLOUD_PORT,  # Ollama Cloud proxy
    "telegram-bot":   BAGO_TELEGRAM_PORT,  # Bot Telegram
    "utopia-bot":     BAGO_UTOPIA_PORT,  # Cliente Utopia
}


# ─── BagoAdapter: puente entre API y el framework existente ──────────────────

class BagoAdapter:
    """Adapta la API HTTP al orquestador BAGO existente.

    Carga providers, routing, catalog y session desde el filesystem
    (.bago/state/) y delega al stack llm/ ya existente.
    """

    def __init__(self, bago_dir: Optional[Path] = None):
        self.bago_dir = bago_dir or self._find_bago_dir()
        self._providers: dict = {}
        self._routing: dict = {}
        self._catalog: list = []
        self._sessions: dict = {}
        self._version: str = "?"

        # Import constants to find paths
        sys.path.insert(0, str(self.bago_dir / "tools"))
        try:
            from bago.constants import BAGO_VERSION, PROVIDERS_FILE, ROUTING_FILE
            self._version = BAGO_VERSION
            self._providers_file = PROVIDERS_FILE
            self._routing_file = ROUTING_FILE
        except ImportError:
            self._version = "?"
            self._providers_file = self.bago_dir / ".bago" / "state" / "model_providers.json"
            self._routing_file = self.bago_dir / ".bago" / "state" / "model_routing.json"

        self._load_config()

    # ── Config loading ────────────────────────────────────────────────────

    def _find_bago_dir(self) -> Path:
        cwd = get_user_cwd()
        for candidate in [cwd, cwd.parent]:
            if (candidate / ".bago").is_dir() or (candidate / "bago_core").is_dir():
                return candidate
        for drive in "DEFGH":
            p = Path(f"{drive}:")
            if (p / ".bago").is_dir():
                return p
        return get_user_cwd()

    def _load_config(self):
        try:
            self._providers = json.loads(self._providers_file.read_text(encoding="utf-8-sig")).get("providers", {})
        except Exception:
            self._providers = {}

        try:
            self._routing = json.loads(self._routing_file.read_text(encoding="utf-8-sig"))
        except Exception:
            self._routing = {"rules": [], "fallback": {}}

        try:
            from bago.model_catalog import CATALOG
            self._catalog = CATALOG
        except ImportError:
            self._catalog = []

    # ── Public interface ──────────────────────────────────────────────────

    @property
    def version(self) -> str:
        return self._version

    @property
    def default_model(self) -> str:
        fb = self._routing.get("fallback", {})
        return fb.get("model", "qwen25-coder")

    @property
    def default_embedding_model(self) -> str:
        return "nomic-embed-text"

    def providers(self) -> dict:
        return self._providers

    def catalog(self) -> list:
        return self._catalog

    def route(self, prompt: str, model: str = "", provider: str = "") -> dict:
        """Route a prompt to the best provider/model using BAGO routing rules."""
        try:
            from bago.providers import route_by_task
            result = route_by_task(prompt, self._routing, self._providers, current_provider=provider or None)
            if isinstance(result, tuple) and len(result) >= 2:
                return {"provider": result[2], "model": result[0],
                        "wire_name": result[1], "reason": "auto-routed"}
        except ImportError:
            pass

        rules = self._routing.get("rules", [])
        best = None
        best_hits = 0
        tl = prompt.lower()
        for rule in rules:
            hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in tl)
            if hits > best_hits:
                best_hits = hits
                best = rule
        if best:
            return {"provider": best.get("provider", ""),
                    "model": best.get("model", ""),
                    "wire_name": self._providers.get(best.get("provider", ""), {}).get("models", {}).get(best.get("model", ""), {}).get("wire_name", best.get("model", "")),
                    "reason": best.get("reason", "keyword-match"),
                    "rule_id": best.get("id", "")}

        fb = self._routing.get("fallback", {})
        fb_provider = fb.get("provider", "ollama-local")
        fb_model = fb.get("model", "qwen25-coder")
        fb_wire = self._providers.get(fb_provider, {}).get("models", {}).get(fb_model, {}).get("wire_name", fb_model)
        return {"provider": fb_provider,
                "model": fb_model,
                "wire_name": fb_wire,
                "reason": "fallback"}
    def fallback_chain(self, model: str) -> list[dict]:
        """Build fallback chain for a model."""
        chain = []
        local_models = self._providers.get("ollama-local", {}).get("models", {})
        for name in local_models:
            if name != model:
                chain.append({"provider": "ollama-local", "model": name})

        for prov in ("copilot", "codex", "ollama-cloud"):
            prov_models = self._providers.get(prov, {}).get("models", {})
            for name in prov_models:
                chain.append({"provider": prov, "model": name})

        return chain[:5]

    def check_provider(self, name: str) -> bool:
        """Check if a provider is reachable.

        For proxies, checks the local port. For local Ollama, checks the configured Ollama base URL.
        For cloud, checks env vars.
        """
        # Local proxies — check if port is alive
        if name in SERVICE_PORTS and name != "bago":
            port = SERVICE_PORTS[name]
            return self._check_port("127.0.0.1", port)

        if name == "ollama-local":
            return self._check_port("127.0.0.1", SERVICE_PORTS["ollama-local"])

        if name in ("copilot", "codex"):
            # Prefer local proxy, fall back to env var
            port = SERVICE_PORTS.get(name, 0)
            if self._check_port("127.0.0.1", port):
                return True
            return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))

        if name == "ollama-cloud":
            port = SERVICE_PORTS.get("ollama-cloud", 0)
            if self._check_port("127.0.0.1", port):
                return True
            return bool(os.environ.get("OLLAMA_API_KEY"))

        return False

    @staticmethod
    def _check_port(host: str, port: int) -> bool:
        """Check if a TCP port is responding."""
        import socket
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def provider_port(self, name: str) -> int:
        """Return the port for a provider proxy."""
        return SERVICE_PORTS.get(name, 0)

    def call_provider(self, provider: str, endpoint: str, payload: dict, method: str = "POST") -> dict:
        """Call a provider proxy via HTTP. Returns the JSON response."""
        port = SERVICE_PORTS.get(provider)
        if not port:
            raise ValueError(f"No proxy port for provider '{provider}'")

        url = f"http://127.0.0.1:{port}{endpoint}"
        data = json.dumps(payload).encode() if method == "POST" else None
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except Exception as e:
            raise RuntimeError(f"Provider {provider} error: {e}")

    def chat(self, messages: list, model: str = "", provider: str = "",
             quality_guard: bool = True, context_escalation: bool = True,
             max_switches: int = 3, options: dict = None) -> dict:
        """Execute a chat call. Routes to provider proxy if running, else uses LLM stack."""
        # Resolve wire_name for model
        # Resolve wire_name for model (skip if model already looks like wire_name)
        if ":" in str(model):
            wire_model = model  # Already a wire_name like "llama3.2:3b"
        else:
            prov_data = self._providers.get(provider, {})
            model_data = prov_data.get("models", {}).get(model, {})
            wire_model = model_data.get("wire_name", model)

        # Special case: ollama-local calls native Ollama directly
        if provider == "ollama-local":
            try:
                import urllib.request
                payload = {
                    "model": wire_model,
                    "messages": messages,
                    "stream": False,
                }
                if options:
                    payload["options"] = options
                data = json.dumps(payload).encode()
                req = urllib.request.Request(
                    f"{default_ollama_base_url()}/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read())
                if isinstance(result, dict) and "message" in result:
                    content = result["message"].get("content", "")
                else:
                    content = ""
                return {
                    "content": content,
                    "model": result.get("model", model),
                    "provider": "ollama-local",
                    "switches": 0,
                    "original_model": model,
                    "original_provider": "ollama-local",
                    "route_reason": "ollama-native",
                }
            except Exception as e:
                pass  # Fall through to LLM stack

        # Try provider proxy first
        port = SERVICE_PORTS.get(provider)
        if port and self._check_port("127.0.0.1", port):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "quality_guard": quality_guard,
                    "stream": False,
                }
                if options:
                    payload["options"] = options
                result = self.call_provider(provider, "/api/chat", payload)
                return {
                    "content": result.get("message", {}).get("content", ""),
                    "model": result.get("model", model),
                    "provider": result.get("provider", provider),
                    "switches": result.get("switches", 0),
                    "original_model": model,
                    "original_provider": provider,
                    "route_reason": result.get("route_reason", "proxy"),
                }
            except Exception:
                pass  # Fall through to LLM stack

        # Try BAGO LLM stack
        try:
            from bago.llm.orchestrator import chat
            from bago.session import Session

            sess = Session()
            if provider:
                sess.provider = provider
            if model:
                sess.model_name = model
            sess.quality_guard = quality_guard
            sess.context_escalation = context_escalation
            sess.max_switches = max_switches

            result_text = chat(messages, session=sess)
            return {
                "content": result_text,
                "model": getattr(sess, "model_name", model),
                "provider": getattr(sess, "provider", provider),
                "switches": getattr(sess, "switches", 0),
                "original_model": model,
                "original_provider": provider,
                "route_reason": getattr(sess, "last_route", {}).get("reason", ""),
            }
        except ImportError:
            return self._chat_litellm(messages, model, provider, options)

    def _chat_litellm(self, messages, model, provider, options):
        """Direct LiteLLM call when orchestrator is not available."""
        try:
            import litellm
            wire = self._resolve_wire(model, provider)
            r = litellm.completion(model=wire, messages=messages, **(options or {}))
            return {
                "content": r.choices[0].message.content,
                "model": model,
                "provider": provider,
                "switches": 0,
            }
        except Exception as e:
            return {"content": f"Error: {e}", "model": model, "provider": provider}

    def _resolve_wire(self, model: str, provider: str) -> str:
        # Resolve wire_name for model (skip if model already looks like wire_name)
        if ":" in str(model):
            wire_model = model  # Already a wire_name like "llama3.2:3b"
        else:
            prov_data = self._providers.get(provider, {})
            model_data = prov_data.get("models", {}).get(model, {})
            wire_model = model_data.get("wire_name", model)
        prov_data = self._providers.get(provider, {})
        model_data = prov_data.get("models", {}).get(model, {})
        return model_data.get("wire_name", f"ollama/{model}")

    def embed(self, model: str, input, options: dict = None) -> dict:
        """Generate embeddings via Ollama."""
        import urllib.request
        import json as _json
        data = _json.dumps({"model": model, "input": input, **(options or {})}).encode()
        req = urllib.request.Request(
            f"{default_ollama_base_url()}/api/embed",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            r = urllib.request.urlopen(req, timeout=30)
            return _json.loads(r.read())
        except Exception as e:
            return {"embeddings": [], "error": str(e)}

    def escalate(self, session_id: str = "", target_provider: str = "",
                 target_model: str = "") -> dict:
        if not target_provider:
            for prov in ("codex", "copilot", "ollama-cloud"):
                if self.check_provider(prov):
                    target_provider = prov
                    break
        if not target_model and target_provider:
            prov_data = self._providers.get(target_provider, {})
            models = prov_data.get("models", {})
            if models:
                target_model = next(iter(models))
        return {"provider": target_provider, "model": target_model,
                "reason": "manual-escalation"}

    def create_session(self, model: str = "", provider: str = "",
                       system: str = "") -> dict:
        sid = str(uuid.uuid4())[:8]
        route_info = self.route(system or "hello", model=model, provider=provider)
        return {
            "id": sid,
            "provider": route_info["provider"],
            "model": route_info["model"],
            "switches": 0,
            "message_count": 0,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def running_models(self) -> dict:
        """List currently loaded models: Ollama ps + proxy health."""
        import urllib.request
        import json as _json

        result = {"models": []}

        # Ollama local
        try:
            r = urllib.request.urlopen(f"{default_ollama_base_url()}/api/ps", timeout=3)
            ollama_ps = _json.loads(r.read())
            result["models"].extend(ollama_ps.get("models", []))
        except Exception:
            pass

        # Check proxy liveness
        for name, port in SERVICE_PORTS.items():
            if name == "bago":
                continue
            alive = self._check_port("127.0.0.1", port)
            if alive:
                try:
                    r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
                    health = _json.loads(r.read())
                    result["models"].append({
                        "name": name,
                        "provider": name,
                        "port": port,
                        "available": health.get("available", True),
                    })
                except Exception:
                    result["models"].append({"name": name, "provider": name, "port": port, "available": True})

        return result


# ─── Global adapter ──────────────────────────────────────────────────────────

_adapter: Optional[BagoAdapter] = None


def get_bago() -> BagoAdapter:
    global _adapter
    if _adapter is None:
        _adapter = BagoAdapter()
    return _adapter


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="BAGO API",
    description="Orquestador de IA — compatible con Ollama + extensiones BAGO",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat_router)
app.include_router(generate_router)
app.include_router(embed_router)
app.include_router(models_router)
app.include_router(bago_router)


@app.get("/api/version", response_model=VersionResponse)
async def version():
    bago = get_bago()
    ollama_ver = ""
    try:
        import urllib.request, json as _json
        r = urllib.request.urlopen(f"{default_ollama_base_url()}/api/version", timeout=3)
        ollama_ver = _json.loads(r.read()).get("version", "")
    except Exception:
        pass
    return VersionResponse(
        bago_version=bago.version,
        api_version="1.0.0",
        ollama_version=ollama_ver,
    )


@app.get("/")
async def root():
    return {
        "name": "BAGO API",
        "version": "1.0.0",
        "docs": "/docs",
        "services": SERVICE_PORTS,
    }


@app.get("/api/services")
async def services():
    """Lista todos los servicios BAGO y su estado."""
    bago = get_bago()
    result = {}
    for name, port in SERVICE_PORTS.items():
        alive = bago._check_port("127.0.0.1", port) if name != "bago" else True
        result[name] = {"port": port, "available": alive, "url": f"http://127.0.0.1:{port}"}
    return result


# ─── CLI entrypoint ──────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="BAGO API Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=BAGO_API_PORT)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "bago.api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
