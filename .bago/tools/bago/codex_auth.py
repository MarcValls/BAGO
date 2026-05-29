"""Descubrimiento de token Codex/OpenAI CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _is_valid_api_key(key: str) -> bool:
    k = key.strip()
    if len(k) < 8:
        return False
    obvious_invalid = {"ollama", "none", "null", "undefined", "false", "test", "demo", "placeholder"}
    return k.lower() not in obvious_invalid


def _extract_token(data: dict) -> str | None:
    auth = data.get("auth") or {}
    tokens = data.get("tokens") or {}
    for candidate in (
        tokens.get("access_token"),
        tokens.get("accessToken"),
        data.get("access_token"),
        data.get("accessToken"),
        data.get("token"),
        auth.get("access_token"),
        auth.get("accessToken"),
        auth.get("token"),
    ):
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if candidate:
                return candidate
    return None


def codex_access_token() -> str | None:
    try:
        codex_dir = Path.home() / ".codex"
        if not codex_dir.exists():
            return None
        auth_file = codex_dir / "auth.json"
        candidates = [auth_file]
        candidates.extend(f for f in codex_dir.glob("*.json") if f != auth_file)
        for f in candidates:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                token = _extract_token(data) if isinstance(data, dict) else None
                if token:
                    return token
            except Exception:
                continue
    except Exception:
        pass
    return None


def resolve_openai_credential() -> tuple[str | None, str]:
    """Return the preferred OpenAI/Codex credential and its mode.

    Priority:
      1. Codex/ChatGPT OAuth token from ~/.codex
      2. Valid OPENAI_API_KEY from the environment
    """
    token = codex_access_token()
    if token:
        return token, "oauth"

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None, ""
    if _is_valid_api_key(api_key):
        return api_key, "api_key"
    return None, "invalid_api_key"


def resolve_openai_credentials() -> dict:
    """Return both OpenAI/Codex credential sources without collapsing them."""
    oauth_token = codex_access_token()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    api_mode = ""
    if api_key:
        api_mode = "api_key" if _is_valid_api_key(api_key) else "invalid_api_key"
    return {
        "oauth_token": oauth_token,
        "oauth_mode": "oauth" if oauth_token else "",
        "api_key": api_key if api_mode == "api_key" else "",
        "api_mode": api_mode,
    }
