#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DEPRECATED shim — use `python tools/validate.py manifest` directly.

Este archivo se conserva temporalmente para compatibilidad con scripts
antiguos. Se eliminará en BAGO 3.6."""

result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "manifest"],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)
