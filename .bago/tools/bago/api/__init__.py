"""bago.api — BAGO HTTP API server.

Compatible con endpoints Ollama + extensiones BAGO (routing, health, escalate).

Usage:
    python -m bago.api.server
    bago serve
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

