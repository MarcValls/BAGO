#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto de entrada de bago image-studio.
El código real está en E:\\.bago\\tools\\image_studio\\ (paquete modular).
"""
import sys
from pathlib import Path

# Asegura que el directorio tools/ esté en sys.path para importar el paquete
_tools = Path(__file__).resolve().parent
if str(_tools) not in sys.path:
    sys.path.insert(0, str(_tools))

from image_studio.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
