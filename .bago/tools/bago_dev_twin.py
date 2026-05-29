#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_dev_twin.py — Interfaz de desarrollador BAGO con dos paneles en una ventana.

Este módulo es ahora un thin-wrapper sobre el paquete dev_twin para mantener
compatibilidad con scripts y tests existentes.

Uso:
    python .bago/tools/bago_dev_twin.py
"""
from dev_twin import TwinDevWindow, main, BAGO_ROOT, IS_WIN, _append_text, _run_in_pane

if __name__ == "__main__":
    main()
