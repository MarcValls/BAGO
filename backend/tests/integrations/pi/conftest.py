"""conftest.py para tests/integrations/pi.

Hace que `import integrations.pi` funcione tanto cuando los tests se
ejecutan desde la raíz del repo (sin instalar el paquete) como cuando
se ejecutan vía `pytest` con `rootdir=backend`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # .../backend
BAGO_ROOT = REPO_ROOT / ".bago"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(BAGO_ROOT))
