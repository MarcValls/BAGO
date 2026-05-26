#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punto de entrada de ``bago image-studio``.

Si el paquete modular ``image_studio`` no está presente en ``.bago/tools/``,
mostramos una salida controlada en vez de un traceback para que el comando
siga siendo diagnosticable desde la CLI experimental.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import sys
from pathlib import Path

_tools = Path(__file__).resolve().parent
if str(_tools) not in sys.path:
    sys.path.insert(0, str(_tools))


def _missing_package() -> int:
    print("image_studio — paquete modular no disponible en .bago/tools/image_studio/\n")
    print("Uso esperado:")
    print("  bago image-studio --help")
    print("  bago image-studio --ui")
    print("  bago image-studio --type sprite --project <nombre>")
    print("\nEstado:")
    print("  ⚠ Falta el paquete image_studio.cli; restaura el módulo modular para habilitar la herramienta.")
    return 2


try:
    from image_studio.cli import main  # type: ignore  # noqa: E402
except ModuleNotFoundError:
    if __name__ == "__main__":
        raise SystemExit(_missing_package())
    main = None  # type: ignore[assignment]


if __name__ == "__main__":
    if main is None:
        raise SystemExit(2)
    raise SystemExit(main())
