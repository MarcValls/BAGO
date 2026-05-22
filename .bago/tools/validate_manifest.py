#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim — validate_manifest merged into validate.py (manifest subcommand)."""
import subprocess, sys
from pathlib import Path

result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "manifest"],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)
