#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim — validate_pack_contents merged into validate.py (contents subcommand)."""
import subprocess, sys
from pathlib import Path

extra = sys.argv[1:]  # pass-through zip path if provided
result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "contents", *extra],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)
