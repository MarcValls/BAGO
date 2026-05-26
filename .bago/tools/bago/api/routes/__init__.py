"""bago.api.routes — HTTP route modules."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .chat import router as chat_router
from .generate import router as generate_router
from .embed import router as embed_router
from .models import router as models_router
from .bago import router as bago_router

__all__ = [
    "chat_router", "generate_router", "embed_router",
    "models_router", "bago_router",
]
