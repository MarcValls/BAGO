from __future__ import annotations

"""Fuente de verdad del servicio OpenAI/Codex.

Separa claramente dos superficies:
- OpenAI API key
- ChatGPT Plus / Codex login

Devuelve estado estructurado para que health, status y routing no infieran
por su cuenta.
"""
import sys
from pathlib import Path

import os
from typing import Any

from .codex_auth import codex_access_token


_OPENAI_VIA_API = {"api", "api_key", "openai_api", "openai_api_key"}
_OPENAI_VIA_PLUS = {
    "chatgpt_plus",
    "chatgpt-login",
    "chatgpt_login",
    "chatgptlogin",
    "codex_login",
    "codex-login",
    "codexlogin",
    "plus",
}


def _normalize_via(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _is_valid_api_key(key: str) -> bool:
    k = str(key or "").strip()
    if len(k) < 8:
        return False
    obvious_invalid = {"ollama", "none", "null", "undefined", "false", "test", "demo", "placeholder"}
    return k.lower() not in obvious_invalid


def _creds_dict(creds: Any) -> dict:
    if isinstance(creds, dict):
        return creds
    return getattr(creds, "_creds", {}) or {}


def _openai_api_key(creds: Any = None) -> tuple[str, str]:
    env_key = os.environ.get("OPENAI_API_KEY", "")
    if _is_valid_api_key(env_key):
        return env_key, "env"

    data = _creds_dict(creds)
    for k in ("OPENAI_API_KEY", "openai_api_key", "openai", "api_key"):
        val = data.get(k, "")
        if isinstance(val, str) and _is_valid_api_key(val):
            return val, f"creds:{k}"
    return "", ""


def openai_service_state(creds: Any = None) -> dict:
    """Estado consolidado de OpenAI/Codex.

    `api_ok` y `chatgpt_plus_ok` son independientes. `ok` es el OR de ambas.
    `preferred_source` prioriza API sobre ChatGPT Plus si las dos existen.
    """
    data = _creds_dict(creds)
    via = _normalize_via(data.get("openai_via"))
    via_source = "api" if via in _OPENAI_VIA_API else "chatgpt_plus" if via in _OPENAI_VIA_PLUS else None
    api_key, api_source = _openai_api_key(data)
    plus_token = codex_access_token()

    api_ok = bool(api_key)
    chatgpt_plus_ok = bool(plus_token)
    preferred_source = "api" if api_ok else "chatgpt_plus" if chatgpt_plus_ok else None
    channel = "openai_api" if api_ok else "chatgpt_plus" if chatgpt_plus_ok else "openai_api"

    if api_ok and chatgpt_plus_ok:
        detail = "OpenAI API key configurada | ChatGPT Plus login detectado"
        auth_detail = "API key + ChatGPT Plus login"
        quota_detail = "billing API separado de ChatGPT Plus"
    elif api_ok:
        detail = "API key configurada | cuota API no verificada"
        auth_detail = "OpenAI API key configurada"
        quota_detail = "cuota/billing se confirma en la llamada real"
    elif chatgpt_plus_ok:
        detail = "ChatGPT Plus login | no es credito API"
        auth_detail = "ChatGPT Plus / Codex login"
        quota_detail = "login ChatGPT Plus separado de OpenAI API billing"
    else:
        detail = "sin OPENAI_API_KEY ni login ChatGPT Plus"
        auth_detail = "sin OpenAI API key ni ChatGPT Plus login"
        quota_detail = "no comprobada sin auth"

    return {
        "ok": api_ok or chatgpt_plus_ok,
        "api_ok": api_ok,
        "chatgpt_plus_ok": chatgpt_plus_ok,
        "preferred_source": preferred_source,
        "channel": channel,
        "detail": detail,
        "auth": "api_key" if api_ok else "chatgpt_plus" if chatgpt_plus_ok else "none",
        "auth_ok": api_ok or chatgpt_plus_ok,
        "auth_detail": auth_detail,
        "quota_ok": None,
        "quota_detail": quota_detail,
        "via": via,
        "via_source": via_source,
        "api_source": api_source,
    }


def openai_service_token(creds: Any = None) -> tuple[str | None, str]:
    """Devuelve el token activo y la fuente elegida.

    Prioridad: API key > ChatGPT Plus / Codex login.
    """
    state = openai_service_state(creds)
    if state["api_ok"]:
        return _openai_api_key(creds)[0], "api"
    if state["chatgpt_plus_ok"]:
        return codex_access_token(), "chatgpt_plus"
    return None, "none"


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
