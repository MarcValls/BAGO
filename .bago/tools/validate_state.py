#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim — validate_state merged into validate.py (state subcommand)."""
import subprocess, sys
from pathlib import Path

result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "state"],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)
