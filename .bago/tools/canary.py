#!/usr/bin/env python3
"""Thin wrapper para bago_canary — permite llamar como módulo BAGO."""
import sys
from pathlib import Path

cwd = Path(__file__).resolve().parent
sys.path.insert(0, str(cwd))
from bago_canary import main

if __name__ == "__main__":
    sys.exit(main() or 0)
