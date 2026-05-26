#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim — validate_manifest merged into validate.py (manifest subcommand)."""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import subprocess, sys
from pathlib import Path

result = subprocess.run(
    [sys.executable, str(Path(__file__).parent / "validate.py"), "manifest"],
    cwd=Path(__file__).parents[2],
)
sys.exit(result.returncode)
