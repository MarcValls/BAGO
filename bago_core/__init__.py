"""bago_core — thin wrapper package that exposes bago CLI via console_scripts.

The actual launcher lives at the repo root as ``bago`` (a Python script).
This package bridges pip-installed entrypoints to that launcher.

Install (editable):
    pip install -e .

Then use:
    bago health
    bago status
    bago registry
"""
from __future__ import annotations

__version__ = "3.5.0b1"
