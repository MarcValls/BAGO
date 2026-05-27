#!/usr/bin/env python3
"""Wrapper CLI para detectar modelos accesibles por proveedor."""

from __future__ import annotations

import sys

from bago.model_registry import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

