#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim — validate_pack merged into validate.py (pack subcommand)."""
import subprocess, sys
from pathlib import Path

result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "pack"],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)
