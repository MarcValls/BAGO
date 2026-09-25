#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
credential_manager.py — BAGO 4.1.5 Credential Manager

Almacena y recupera credenciales de providers (API keys, tokens, URLs).
Las guarda en `.bago/credentials.json` con permisos restrictivos.

Soporta fallback a variables de entorno con prefijo BAGO_.
"""

from __future__ import annotations

import json
import os
import sys
import base64
from ctypes import POINTER, Structure, byref, cast, create_string_buffer, wintypes
try:
    from ctypes import windll  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Windows-only API
    windll = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import state_read_candidates
from state_paths import resolve_state_root

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

_PROVIDER_API_KEY_ALIASES = {
    ("ollama-cloud", "OLLAMA_CLOUD_KEY"),
    ("copilot", "GITHUB_TOKEN"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("codex", "OPENAI_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("opencode", "OPENCODE_API_KEY"),
}


def _secret_store_key(provider: str, key: str) -> str:
    return f"providers/{provider}/api_key" if (provider, key) in _PROVIDER_API_KEY_ALIASES else f"providers/{provider}/{key}"


class _DATA_BLOB(Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", POINTER(wintypes.BYTE))]


def _load_install_config(base_path: Path) -> dict[str, Any]:
    path = base_path / "install_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _blob_from_bytes(data: bytes) -> _DATA_BLOB:
    buf = create_string_buffer(data if data else b"\x00", max(1, len(data)))
    blob = _DATA_BLOB(len(data), cast(buf, POINTER(wintypes.BYTE)))
    blob._buffer = buf  # type: ignore[attr-defined]
    return blob


def _bytes_from_blob(blob: _DATA_BLOB) -> bytes:
    if not blob.cbData or not blob.pbData:
        return b""
    return bytes(bytearray(blob.pbData[i] for i in range(blob.cbData)))


def _dpapi_protect(plain_text: str, entropy: str = "BAGO") -> str:
    if sys.platform != "win32" or windll is None:
        raise OSError("DPAPI encryption is only available on Windows")
    data_in = _blob_from_bytes(plain_text.encode("utf-8"))
    entropy_blob = _blob_from_bytes(entropy.encode("utf-8"))
    out_blob = _DATA_BLOB()
    if not windll.crypt32.CryptProtectData(byref(data_in), None, byref(entropy_blob), None, None, 0, byref(out_blob)):
        raise OSError("CryptProtectData failed")
    try:
        return json.dumps({
            "format": "bago-encrypted-v1",
            "scope": "CurrentUser",
            "payload": base64.b64encode(_bytes_from_blob(out_blob)).decode("ascii"),
        })
    finally:
        windll.kernel32.LocalFree(out_blob.pbData)


def _decode_payload(value: str) -> bytes:
    try:
        return base64.b64decode(value)
    except Exception:
        return bytes.fromhex(value)


def _dpapi_unprotect(container: dict[str, Any], entropy: str = "BAGO") -> str:
    if sys.platform != "win32" or windll is None:
        raise OSError("DPAPI decryption is only available on Windows")
    payload = _decode_payload(container.get("payload", ""))
    data_in = _blob_from_bytes(payload)
    entropy_blob = _blob_from_bytes(entropy.encode("utf-8"))
    out_blob = _DATA_BLOB()
    if not windll.crypt32.CryptUnprotectData(byref(data_in), None, byref(entropy_blob), None, None, 0, byref(out_blob)):
        raise OSError("CryptUnprotectData failed")
    try:
        return _bytes_from_blob(out_blob).decode("utf-8")
    finally:
        windll.kernel32.LocalFree(out_blob.pbData)


class CredentialManager:
    """Gestiona `.bago/credentials.json`."""

    def __init__(self, base_path: str | None = None, state_root: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        self.config_dir = resolve_state_root(state_root)
        self.install_config = _load_install_config(self.base_path)
        store_cfg = self.install_config.get("credentials", {})
        self.store_mode = str(store_cfg.get("mode", "legacy")).lower()
        self.store_encrypted = bool(store_cfg.get("encrypted", False) or self.store_mode in {"persistent", "external"})
        store_path = store_cfg.get("path") or ""
        if store_path:
            self.cred_path = Path(store_path)
        elif self.store_mode == "session":
            self.cred_path = self.config_dir / "session-credentials.json"
        else:
            self.cred_path = self.config_dir / "credentials.json"
        self._data: dict[str, dict[str, str]] = {}
        self._session_manager: Any = None
        self._load()

    def bind_session_manager(self, manager: Any) -> None:
        """Bind writes to the active session's canonical execution authority."""
        self._session_manager = manager

    def _load(self) -> None:
        legacy_path = self.base_path / ".bago" / ("session-credentials.json" if self.store_mode == "session" else "credentials.json")
        candidates = [self.cred_path, *state_read_candidates("credentials.json"), legacy_path]
        source_path = next((path for path in dict.fromkeys(candidates) if path.exists()), self.cred_path)
        if source_path.exists():
            try:
                raw = source_path.read_text(encoding="utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("format") == "bago-encrypted-v1":
                    self._data = json.loads(_dpapi_unprotect(parsed))
                else:
                    self._data = parsed if isinstance(parsed, dict) else {}
            except Exception:
                self._data = {}
        else:
            self._data = {}
        # Import into this process only. Persisting during construction bypasses
        # the user's explicit credential-write authorization boundary.
        self._auto_import_env()

    def _auto_import_env(self) -> None:
        """Importa automáticamente credenciales desde env vars si no existen localmente."""
        for provider, mapping in CREDENTIAL_SCHEMA.items():
            for env_var, desc in mapping.items():
                val = os.environ.get(env_var)
                if val and provider not in self._data:
                    self._data[provider] = {}
                if val and env_var not in (self._data.get(provider) or {}):
                    self._data.setdefault(provider, {})[env_var] = val
        # Environment credentials remain process-local until explicitly saved.

    def _save(self) -> None:
        raise RuntimeError("La persistencia legacy de credenciales está deshabilitada; use credential.write.")

    def _execute_secret_write(self, provider: str, key: str, operation: str, value: str = "") -> bool:
        from credential_manager import CREDENTIAL_SCHEMA
        manager = self._session_manager
        if manager is None or key not in CREDENTIAL_SCHEMA.get(provider, {}):
            raise RuntimeError("Escritura de credenciales requiere SessionManager y una clave registrada.")
        from execution_request import build_execution_request, stable_digest
        from bago_core.cli_execution import execute_cli_effect

        config_getter = getattr(getattr(manager, "config", None), "provider_config", None)
        if not callable(config_getter):
            raise RuntimeError("No hay configuración autoritativa del proveedor.")
        request = build_execution_request(
            effect_id="credential.write", actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="cli.credentials",
            target={
                "resource": "provider_credential", "operation": operation,
                "provider": provider, "key": "api_key" if (provider, key) in _PROVIDER_API_KEY_ALIASES else key,
                "configuration_digest": stable_digest(config_getter(provider)),
                "configuration_patch": {},
            },
            arguments={"value": value} if operation == "set" else {},
            scope="persistent",
        )
        result, _authorization = execute_cli_effect(
            request,
            confirmation_text=f"{operation} {provider}/{key} (secreto guardado en SecretStore)",
            manager=manager,
        )
        return bool(result.get("changed", False)) if operation == "delete" and isinstance(result, dict) else True

    def get(self, provider: str, key: str, default: str = "") -> str:
        """Obtiene credencial. Fallback: archivo -> env var -> default."""
        # The canonical SecretStore wins over retained legacy read-only data.
        val = ""
        if key in CREDENTIAL_SCHEMA.get(provider, {}):
            try:
                from bago_core.secrets import get_secret_store
                val = get_secret_store().get_secret(_secret_store_key(provider, key)) or ""
            except (ImportError, OSError, RuntimeError):
                val = ""
            if val:
                return val
        # Legacy credential files remain readable but are no longer writable.
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
        """Persiste a través de credential.write y su aprobación interactiva."""
        if self.store_mode == "session":
            self._data.setdefault(provider, {})[key] = str(value)
            return
        self._execute_secret_write(provider, key, "set", str(value))
        self._data.setdefault(provider, {})[key] = str(value)

    def delete(self, provider: str, key: str) -> bool:
        """Elimina un secreto canónico; legacy files quedan solo lectura."""
        if self.store_mode == "session":
            values = self._data.get(provider, {})
            if key not in values:
                return False
            del values[key]
            if not values:
                del self._data[provider]
            return True
        try:
            from bago_core.secrets import get_secret_store
            exists = bool(get_secret_store().get_secret(_secret_store_key(provider, key)))
        except (ImportError, OSError, RuntimeError):
            exists = False
        if exists and self._execute_secret_write(provider, key, "delete"):
            if provider in self._data and key in self._data[provider]:
                del self._data[provider][key]
                if not self._data[provider]:
                    del self._data[provider]
            return True
        # A cached legacy value cannot be removed without rewriting an
        # ungoverned legacy file, so report no deletion instead of claiming it.
        if provider in self._data and key in self._data[provider]:
            return False
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
        result = {k: dict(v) for k, v in self._data.items()}
        for provider, keys in CREDENTIAL_SCHEMA.items():
            for key in keys:
                value = self.get(provider, key)
                if value:
                    result.setdefault(provider, {})[key] = value
        return result


# ── Quick test ──────────────────────────────────────────────────────

def _run_tests() -> int:
    import tempfile
    # Limpiar env vars de prueba
    for provider, mapping in CREDENTIAL_SCHEMA.items():
        for key in mapping:
            if key in os.environ:
                del os.environ[key]

    with tempfile.TemporaryDirectory() as td:
        state_root = Path(td) / "state"
        old_state = os.environ.get("BAGO_STATE_ROOT")
        os.environ["BAGO_STATE_ROOT"] = str(state_root)
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
        if old_state is None:
            os.environ.pop("BAGO_STATE_ROOT", None)
        else:
            os.environ["BAGO_STATE_ROOT"] = old_state
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
