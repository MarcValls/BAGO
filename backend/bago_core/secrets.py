"""Backend-owned secret storage.

API surfaces may call this module, but the session kernel never imports an
HTTP/API implementation to resolve secrets.
"""

from __future__ import annotations

import base64
import ctypes
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from bago_core.user_state_paths import secrets_root, user_read_candidates


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_protect(plaintext: bytes) -> bytes:
    source = _DATA_BLOB(len(plaintext), ctypes.cast(ctypes.c_char_p(plaintext), ctypes.POINTER(ctypes.c_byte)))
    target = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError("CryptProtectData falló: " + ctypes.FormatError())
    try:
        return bytes(ctypes.string_at(target.pbData, target.cbData))
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    source = _DATA_BLOB(len(ciphertext), ctypes.cast(ctypes.c_char_p(ciphertext), ctypes.POINTER(ctypes.c_byte)))
    target = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError("CryptUnprotectData falló: " + ctypes.FormatError())
    try:
        return bytes(ctypes.string_at(target.pbData, target.cbData))
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def _fallback_key() -> bytes:
    import hashlib

    user = os.environ.get("USER") or os.environ.get("USERNAME") or "anon"
    host = os.uname().nodename if hasattr(os, "uname") else "host"
    return hashlib.sha256(f"{user}@{host}".encode("utf-8")).digest()


def _fallback_protect(plaintext: bytes) -> bytes:
    key = _fallback_key()
    encrypted = bytes(value ^ key[index % len(key)] for index, value in enumerate(plaintext))
    return b"FALLBACK:" + base64.b64encode(encrypted)


def _fallback_unprotect(ciphertext: bytes) -> bytes:
    if not ciphertext.startswith(b"FALLBACK:"):
        raise ValueError("Cifrado no es fallback")
    key = _fallback_key()
    encrypted = base64.b64decode(ciphertext[len(b"FALLBACK:") :])
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(encrypted))


def _secret_dir(*, create: bool = True) -> Path:
    path = secrets_root()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _safe_key_name(key: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "-", key.lower()).strip("-") or "key"
    return f"{safe}.bin"


def _key_to_path(key: str, *, create: bool = True) -> Path:
    return _secret_dir(create=create) / _safe_key_name(key)


def _key_read_candidates(key: str) -> tuple[Path, ...]:
    return user_read_candidates(Path("secrets") / _safe_key_name(key))


class SecretStore:
    """OS-bound secret store owned by the backend kernel."""

    def _platform_is_windows(self) -> bool:
        """Keep platform selection overridable for compatibility facades/tests."""
        return _is_windows()

    def set_secret(self, key: str, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("value debe ser str")
        raw = value.encode("utf-8")
        cipher = _dpapi_protect(raw) if self._platform_is_windows() else _fallback_protect(raw)
        path = _key_to_path(key, create=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(cipher)
        os.replace(str(temporary), str(path))
        try:
            os.chmod(str(path), 0o600)
        except (OSError, NotImplementedError):
            pass

    def get_secret(self, key: str) -> Optional[str]:
        for path in _key_read_candidates(key):
            if not path.exists():
                continue
            cipher = path.read_bytes()
            try:
                plain = _dpapi_unprotect(cipher) if self._platform_is_windows() else _fallback_unprotect(cipher)
            except Exception:
                continue
            return plain.decode("utf-8", errors="replace")
        return None

    def delete_secret(self, key: str) -> bool:
        path = _key_to_path(key, create=False)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self) -> list[str]:
        keys: set[str] = set()
        for directory in user_read_candidates("secrets"):
            if not directory.is_dir():
                continue
            for path in directory.glob("*.bin"):
                if path.stem:
                    keys.add(path.stem)
        return sorted(keys)

    def has_secret(self, key: str) -> bool:
        return any(path.exists() for path in _key_read_candidates(key))


_default: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _default
    if _default is None:
        _default = SecretStore()
    return _default
