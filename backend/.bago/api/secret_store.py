"""Compatibility facade for the backend-owned secret store.

The implementation and canonical storage live in :mod:`bago_core.secrets`.
This façade preserves the legacy import path and its injectable platform probe
without creating a second secret-storage authority.
"""

from bago_core import secrets as _secrets


_fallback_protect = _secrets._fallback_protect
_fallback_unprotect = _secrets._fallback_unprotect


def _is_windows() -> bool:
    return _secrets._is_windows()


class SecretStore(_secrets.SecretStore):
    def _platform_is_windows(self) -> bool:
        return _is_windows()


_default: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _default
    if _default is None:
        _default = SecretStore()
    return _default


__all__ = ["SecretStore", "get_secret_store"]
