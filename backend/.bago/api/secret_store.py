"""secret_store.py — cifrado de credenciales con DPAPI en Windows.

BAGO guarda los secretos (API keys, OAuth tokens) cifrados con la
clave del usuario actual del SO (DPAPI). Solo el usuario que los
guardó puede descifrarlos.

En sistemas no-Windows, fallback a archivo con permisos 0600 y XOR
con una clave derivada del hostname + usuario (mejor que nada, no
criptografía real). Documentado en el README.

Estructura en disco:
  ~/.bago/secrets/<provider_id>.bin    -> bytes cifrados con DPAPI

Interfaz:
    store = SecretStore()
    store.set_secret("openai", "sk-...")
    value = store.get_secret("openai")  # str | None
    store.delete_secret("openai")
    keys = store.list_keys()            # list[str]
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Optional


# ─── DPAPI bindings (Windows) ─────────────────────────────────────────

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _dpapi_protect(plaintext: bytes) -> bytes:
    """Cifra con DPAPI usando el contexto del usuario actual."""
    in_blob = _DATA_BLOB(
        cbData=len(plaintext),
        pbData=ctypes.cast(
            ctypes.c_char_p(plaintext),
            ctypes.POINTER(ctypes.c_byte),
        ),
    )
    out_blob = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise OSError("CryptProtectData falló: " + ctypes.FormatError())
    try:
        buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return bytes(buf)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    """Descifra con DPAPI."""
    in_blob = _DATA_BLOB(
        cbData=len(ciphertext),
        pbData=ctypes.cast(
            ctypes.c_char_p(ciphertext),
            ctypes.POINTER(ctypes.c_byte),
        ),
    )
    out_blob = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise OSError("CryptUnprotectData falló: " + ctypes.FormatError())
    try:
        buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return bytes(buf)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


# ─── Fallback no-Windows: cifrado débil con XOR + perms estrictas ────

def _fallback_protect(plaintext: bytes) -> bytes:
    """XOR con hashlib + permisos 0600."""
    import hashlib
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "anon"
    host = os.uname().nodename if hasattr(os, "uname") else "host"
    key = hashlib.sha256(f"{user}@{host}".encode("utf-8")).digest()
    out = bytes(b ^ key[i % len(key)] for i, b in enumerate(plaintext))
    return b"FALLBACK:" + base64.b64encode(out)


def _fallback_unprotect(ciphertext: bytes) -> bytes:
    if not ciphertext.startswith(b"FALLBACK:"):
        raise ValueError("Cifrado no es fallback")
    import hashlib
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "anon"
    host = os.uname().nodename if hasattr(os, "uname") else "host"
    key = hashlib.sha256(f"{user}@{host}".encode("utf-8")).digest()
    enc = base64.b64decode(ciphertext[len(b"FALLBACK:"):])
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(enc))


# ─── API pública ─────────────────────────────────────────────────────

def _secret_dir() -> Path:
    p = Path.home() / ".bago" / "secrets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _key_to_path(key: str) -> Path:
    # Solo [a-z0-9-]
    import re
    safe = re.sub(r"[^a-z0-9-]", "-", key.lower()).strip("-") or "key"
    return _secret_dir() / f"{safe}.bin"


class SecretStore:
    """Wrapper sobre DPAPI. La clave es el provider_id."""

    def set_secret(self, key: str, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("value debe ser str")
        raw = value.encode("utf-8")
        if _is_windows():
            cipher = _dpapi_protect(raw)
        else:
            cipher = _fallback_protect(raw)
        path = _key_to_path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(cipher)
        os.replace(str(tmp), str(path))
        try:
            os.chmod(str(path), 0o600)
        except (OSError, NotImplementedError):
            pass

    def get_secret(self, key: str) -> Optional[str]:
        path = _key_to_path(key)
        if not path.exists():
            return None
        cipher = path.read_bytes()
        try:
            if _is_windows():
                plain = _dpapi_unprotect(cipher)
            else:
                plain = _fallback_unprotect(cipher)
        except Exception:
            # Cifrado corrupto o de otro usuario
            return None
        return plain.decode("utf-8", errors="replace")

    def delete_secret(self, key: str) -> bool:
        path = _key_to_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self) -> list[str]:
        out = []
        for p in _secret_dir().glob("*.bin"):
            if p.stem:
                out.append(p.stem)
        return sorted(out)

    def has_secret(self, key: str) -> bool:
        return _key_to_path(key).exists()


# ─── Singleton (importable directo) ─────────────────────────────────

_default: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _default
    if _default is None:
        _default = SecretStore()
    return _default
