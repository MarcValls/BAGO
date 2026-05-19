"""bago.llm.errors — Excepciones y detección de errores LLM/provider."""

import re as _re

# ── Excepción de modelo no disponible ─────────────────────────────────────────

class OllamaNoModelAvailable(RuntimeError):
    """Se lanza cuando no hay ningún modelo Ollama disponible y la cadena de
    fallback (local → copilot → codex) se ha agotado por completo.
    El bucle del REPL la captura y redirige a la pantalla de instalación."""
    def __init__(self, missing: str, tried: list[str]):
        self.missing = missing
        self.tried   = tried
        super().__init__(
            f"Modelo '{missing}' no instalado. "
            f"Alternativas intentadas: {', '.join(tried) or 'ninguna'}."
        )


# ── Context overflow ───────────────────────────────────────────────────────────

_CTX_KEYWORDS = (
    "context", "token", "length exceeded", "too long", "maximum context",
    "context_length", "context window", "max_tokens", "sequence length",
    "input is too long", "prompt is too long", "reduce your prompt",
)

def _is_ctx_overflow(exc) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in _CTX_KEYWORDS)


# ── Errores Ollama ─────────────────────────────────────────────────────────────

_OLLAMA_UNREACHABLE_SIGNALS = (
    "connection refused", "cannot connect", "failed to connect",
    "connectionrefused", "remotedisconnected", "apiconnectionerror",
    "connect call failed", "cannot connect to host",
)

def _is_ollama_model_not_found(exc) -> "tuple[bool, str]":
    """Detecta 'OllamaException: model X not found'. Devuelve (True, model_name)."""
    msg = str(exc)
    low = msg.lower()
    if "not found" in low and ("ollama" in low or "model" in low):
        m = _re.search(r"model ['\"]?([a-zA-Z0-9_.:\-/]+)['\"]? not found", msg, _re.IGNORECASE)
        model_name = m.group(1) if m else ""
        return True, model_name
    return False, ""

def _is_ollama_unreachable(exc, *, model: str = "") -> bool:
    """Detecta que Ollama no está corriendo o no es alcanzable.

    audit-8: ya no exige 'ollama' en el mensaje de error — un ConnectionRefused
    puro sobre un modelo ollama:// también se trata como Ollama inalcanzable.
    """
    low = str(exc).lower()
    conn_fail = any(sig in low for sig in _OLLAMA_UNREACHABLE_SIGNALS)
    if not conn_fail:
        return False
    # Contexto Ollama: mención explícita O el modelo inicia con 'ollama/'
    return "ollama" in low or model.startswith("ollama/")


# ── Errores providers cloud ────────────────────────────────────────────────────

_CLOUD_AUTH_SIGNALS = (
    "authenticationerror", "401", "unauthorized", "invalid token",
    "authentication failed", "auth_error", "invalid_api_key",
    "permissiondeniederror", "permission denied", "forbidden",
    "invalid credentials",
)
_CLOUD_CONN_SIGNALS = (
    "connection timed out", "timed out", "connecttimeout",
    "read timed out", "remotedisconnected", "servicesunavailable",
    "503", "502", "overloaded", "apiconnectionerror",
)

def _is_cloud_auth_error(exc) -> bool:
    """Detecta errores de autenticación en providers cloud (no Ollama)."""
    low = str(exc).lower()
    if "ollama" in low:
        return False
    return any(sig in low for sig in _CLOUD_AUTH_SIGNALS)

def _is_cloud_connection_error(exc) -> bool:
    """Detecta errores de conexión/timeout en providers cloud (no Ollama)."""
    low = str(exc).lower()
    if "ollama" in low:
        return False
    if "not found" in low and "model" in low:
        return False
    return any(sig in low for sig in _CLOUD_CONN_SIGNALS)
