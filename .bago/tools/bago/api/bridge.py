"""bago.api.bridge — Puente entre el chat BAGO y la API HTTP.

Cuando BAGO se ejecuta en modo 'api' (bago launch --api o bago serve activo),
el REPL envía mensajes a localhost:11435 en vez de importar los módulos Python.
Así el orquestador, fallbacks, quality guards y proxies se usan por igual
desde chat, n8n, curl o cualquier cliente.

Modos de operación:
  - 'direct' (default): usa llm/orchestrator.py directamente (comportamiento actual)
  - 'api': envía HTTP a localhost:11435
  - 'hybrid': intenta API primero, cae a directo si no hay servidor
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Optional

# ─── Config ────────────────────────────────────────────────────────────────────

BAGO_API_URL = os.environ.get("BAGO_API_URL", "http://127.0.0.1:11435")
API_TIMEOUT = int(os.environ.get("BAGO_API_TIMEOUT", "120"))

# Detección automática: si el servidor está vivo, usar API
_auto_mode: Optional[str] = None


def detect_mode() -> str:
    """Detecta si el servidor API está disponible y devuelve el modo."""
    global _auto_mode
    if _auto_mode is not None:
        return _auto_mode

    try:
        req = urllib.request.Request(f"{BAGO_API_URL}/api/version", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            if data.get("bago_version"):
                _auto_mode = "api"
                return "api"
    except Exception:
        pass

    _auto_mode = "direct"
    return "direct"


def set_mode(mode: str) -> None:
    """Fuerza el modo de operación: 'api', 'direct', 'hybrid'."""
    global _auto_mode
    _auto_mode = mode


def get_mode() -> str:
    """Devuelve el modo actual (resolviendo 'hybrid')."""
    if _auto_mode == "hybrid":
        return detect_mode()
    if _auto_mode is not None:
        return _auto_mode
    return detect_mode()


# ─── API calls ─────────────────────────────────────────────────────────────────

def api_chat(messages: list[dict], model: str = "", provider: str = "",
             system: str = "", quality_guard: bool = True,
             context_escalation: bool = True, max_switches: int = 3,
             options: dict = None) -> dict:
    """Envía un mensaje de chat a la API BAGO.

    Devuelve dict con: content, model, provider, switches, route_reason.
    """
    payload = {
        "model": model,
        "messages": messages,
        "system": system,
        "quality_guard": quality_guard,
        "context_escalation": context_escalation,
        "max_switches": max_switches,
        "stream": False,
    }
    if provider:
        payload["provider"] = provider
    if options:
        payload["options"] = options

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BAGO_API_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"BAGO API error {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"BAGO API unreachable: {e.reason}")

    msg = result.get("message", {})
    return {
        "content": msg.get("content", ""),
        "model": result.get("model", model),
        "provider": result.get("provider", provider),
        "switches": result.get("switches", 0),
        "original_model": result.get("original_model", ""),
        "original_provider": result.get("original_provider", ""),
        "route_reason": result.get("route_reason", ""),
        "eval_count": result.get("eval_count", 0),
        "total_duration": result.get("total_duration", 0),
    }


def api_route(prompt: str, model: str = "", provider: str = "") -> dict:
    """Preview del routing sin ejecutar la llamada."""
    payload = {"prompt": prompt, "model": model, "provider": provider}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BAGO_API_URL}/api/route",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def api_health() -> dict:
    """Health check del servidor API."""
    req = urllib.request.Request(f"{BAGO_API_URL}/api/health", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"score": 0, "error": str(e)}


def api_tags() -> dict:
    """Lista modelos disponibles via API."""
    req = urllib.request.Request(f"{BAGO_API_URL}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"models": []}


def api_services() -> dict:
    """Lista servicios (proxies) disponibles via API."""
    req = urllib.request.Request(f"{BAGO_API_URL}/api/services", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


# ─── Bridge: chat que decide API vs directo ──────────────────────────────────

def chat_bridge(session, user_input: str, *, history_input: str = None) -> str:
    """Punto de entrada unificado: usa API si está disponible, directo si no.

    Compatible con la firma de bago.llm.orchestrator.chat():
      chat(session, user_input, history_input=...)

    Devuelve el texto de la respuesta (igual que el orchestrator directo).
    """
    mode = get_mode()

    if mode == "api":
        return _chat_via_api(session, user_input, history_input=history_input)

    if mode == "direct":
        return _chat_direct(session, user_input, history_input=history_input)

    # hybrid: intenta API, cae a directo
    try:
        result = _chat_via_api(session, user_input, history_input=history_input)
        return result
    except Exception:
        return _chat_direct(session, user_input, history_input=history_input)


def _chat_via_api(session, user_input: str, *, history_input: str = None) -> str:
    """Chat via API HTTP."""
    # Build messages from session history
    messages = []
    for msg in session.history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    # Add new user message
    messages.append({"role": "user", "content": user_input})

    result = api_chat(
        messages=messages,
        model=session.model_name or "",
        provider=session.provider or "",
        quality_guard=getattr(session, "quality_guard", True),
        context_escalation=getattr(session, "context_escalation", True),
        max_switches=getattr(session, "max_switches", 3),
    )

    # Update session state from API response
    if result.get("provider"):
        session.provider = result["provider"]
    if result.get("model"):
        session.model_name = result["model"]
    session.switches += result.get("switches", 0)
    session.last_route = {
        "mode": "api",
        "provider": result.get("provider", ""),
        "model": result.get("model", ""),
        "reason": result.get("route_reason", "api-bridge"),
    }
    session.record_tokens(
        result.get("provider", ""),
        result.get("model", ""),
        result.get("eval_count", 0) or 0,
        0,  # API doesn't return prompt tokens separately in this path
    )

    history_msg = history_input if history_input is not None else user_input
    session.history.append({"role": "user", "content": history_msg})
    session.history.append({"role": "assistant", "content": result.get("content", "")})

    return result.get("content", "")


def _chat_direct(session, user_input: str, *, history_input: str = None) -> str:
    """Chat directo via llm/orchestrator (comportamiento actual)."""
    from bago.llm.orchestrator import chat
    return chat(session, user_input, history_input=history_input)
