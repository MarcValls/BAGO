#!/usr/bin/env python3
"""
credential_manager.py — BAGO 4.0 Credential Manager

Almacena y recupera credenciales de providers (API keys, tokens, URLs).
Las guarda en `.bago/credentials.json` con permisos restrictivos.

Soporta fallback a variables de entorno con prefijo BAGO_.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# Mapeo: provider -> (env_var, descripción)
CREDENTIAL_SCHEMA: dict[str, dict[str, str]] = {
    "ollama-local": {
        "OLLAMA_HOST": "URL base de Ollama local (default: http://127.0.0.1:11434)",
    },
    "ollama-cloud": {
        "OLLAMA_CLOUD_URL": "URL base del endpoint remoto",
        "OLLAMA_CLOUD_KEY": "API key opcional (Bearer token)",
    },
    "copilot": {
        "GITHUB_TOKEN": "Token de GitHub (gh auth token o personal access token)",
    },
    "anthropic": {
        "ANTHROPIC_API_KEY": "API key de Anthropic (Claude)",
    },
    "codex": {
        "OPENAI_API_KEY": "API key de OpenAI",
        "OPENAI_ORG_ID": "ID de organización OpenAI (opcional)",
    },
    "openrouter": {
        "OPENROUTER_API_KEY": "API key de OpenRouter",
        "OPENROUTER_HTTP_REFERER": "Referer HTTP para rankings (opcional)",
    },
    "opencode": {
        "OPENCODE_API_KEY": "API key de OpenCode",
        "OPENCODE_BASE_URL": "URL base del proxy OpenCode",
    },
}


class CredentialManager:
    """Gestiona `.bago/credentials.json`."""

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        self.config_dir = self.base_path / ".bago"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cred_path = self.config_dir / "credentials.json"
        self._data: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self.cred_path.exists():
            try:
                self._data = json.loads(self.cred_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}
        else:
            self._data = {}
        # Auto-migrate from env vars on first run
        self._auto_import_env()

    def _auto_import_env(self) -> None:
        """Importa automáticamente credenciales desde env vars si no existen localmente."""
        dirty = False
        for provider, mapping in CREDENTIAL_SCHEMA.items():
            for env_var, desc in mapping.items():
                val = os.environ.get(env_var)
                if val and provider not in self._data:
                    self._data[provider] = {}
                if val and env_var not in (self._data.get(provider) or {}):
                    self._data.setdefault(provider, {})[env_var] = val
                    dirty = True
        if dirty:
            self._save()

    def _save(self) -> None:
        self.cred_path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        # Intentar permisos restrictivos (no crítico si falla en Windows)
        try:
            os.chmod(self.cred_path, 0o600)
        except (OSError, AttributeError):
            pass

    def get(self, provider: str, key: str, default: str = "") -> str:
        """Obtiene credencial. Fallback: archivo -> env var -> default."""
        # 1. Archivo local
        val = self._data.get(provider, {}).get(key, "")
        if val:
            return val
        # 2. Variable de entorno
        val = os.environ.get(key, "")
        if val:
            return val
        # 3. Fallback BAGO_provider_key
        bago_key = f"BAGO_{provider.upper().replace('-', '_')}_{key}"
        val = os.environ.get(bago_key, "")
        if val:
            return val
        return default

    def set(self, provider: str, key: str, value: str) -> None:
        """Guarda credencial en archivo local."""
        self._data.setdefault(provider, {})[key] = value
        self._save()

    def delete(self, provider: str, key: str) -> bool:
        """Elimina credencial del archivo local."""
        if provider in self._data and key in self._data[provider]:
            del self._data[provider][key]
            if not self._data[provider]:
                del self._data[provider]
            self._save()
            return True
        return False

    def list_for_provider(self, provider: str) -> dict[str, str]:
        """Lista credenciales almacenadas para un provider."""
        return dict(self._data.get(provider, {}))

    def is_configured(self, provider: str) -> bool:
        """Verifica si un provider tiene al menos una credencial configurada."""
        schema = CREDENTIAL_SCHEMA.get(provider, {})
        for key in schema:
            if self.get(provider, key):
                return True
        return False

    def required_keys(self, provider: str) -> list[str]:
        """Devuelve las claves requeridas según el schema."""
        return list(CREDENTIAL_SCHEMA.get(provider, {}).keys())

    def describe_key(self, provider: str, key: str) -> str:
        return CREDENTIAL_SCHEMA.get(provider, {}).get(key, "")

    def all_providers(self) -> dict[str, dict[str, str]]:
        return {k: dict(v) for k, v in self._data.items()}


# ── Quick test ──────────────────────────────────────────────────────

def _run_tests() -> int:
    import tempfile
    # Limpiar env vars de prueba
    for provider, mapping in CREDENTIAL_SCHEMA.items():
        for key in mapping:
            if key in os.environ:
                del os.environ[key]

    with tempfile.TemporaryDirectory() as td:
        cm = CredentialManager(base_path=td)
        assert not cm.is_configured("anthropic")
        cm.set("anthropic", "ANTHROPIC_API_KEY", "sk-test-123")
        assert cm.is_configured("anthropic")
        assert cm.get("anthropic", "ANTHROPIC_API_KEY") == "sk-test-123"
        cm.delete("anthropic", "ANTHROPIC_API_KEY")
        assert not cm.is_configured("anthropic")
        # Test env fallback
        os.environ["OPENROUTER_API_KEY"] = "sk-or-456"
        cm2 = CredentialManager(base_path=td)
        assert cm2.get("openrouter", "OPENROUTER_API_KEY") == "sk-or-456"
        print("credential_manager.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
