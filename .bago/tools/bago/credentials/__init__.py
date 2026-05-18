"""bago.credentials — gestión de credenciales y cuentas multi-provider.

Módulos:
    accounts     — AccountManager: almacén de cuentas/tokens (sin UI)
    manager      — CredentialManager: estado, detección y tabla de providers
    login_flows  — LoginFlowsMixin: flujos interactivos /login (UI, subprocess)

Re-exporta las clases públicas para mantener compatibilidad con importaciones
existentes:  from bago.credentials import CredentialManager, AccountManager
"""

from .accounts import AccountManager
from .manager import CredentialManager

__all__ = ["AccountManager", "CredentialManager"]
