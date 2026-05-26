"""bago.credentials — gestión de credenciales y cuentas multi-provider.

Módulos:
    accounts     — AccountManager: almacén de cuentas/tokens (sin UI)
    manager      — CredentialManager: estado, detección y tabla de providers
    login_flows  — LoginFlowsMixin: flujos interactivos /login (UI, subprocess)

Re-exporta las clases públicas para mantener compatibilidad con importaciones
existentes:  from bago.credentials import CredentialManager, AccountManager
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .accounts import AccountManager
from .manager import CredentialManager

__all__ = ["AccountManager", "CredentialManager"]
