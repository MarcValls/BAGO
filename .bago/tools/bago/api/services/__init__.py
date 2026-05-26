"""bago.api.services — Proxies BAGO para providers externos.

Cada proxy expone la misma API BAGO-compatible en su puerto:
  - Ollama local:  <OLLAMA_PORT> (ya existe, no necesita proxy)
  - BAGO orquestador: <BAGO_API_PORT> (server.py)
  - Copilot (GitHub Models): 11436 (copilot.py)
  - Codex (OpenAI):         11437 (codex.py)
  - Ollama Cloud:           11438 (ollama_cloud.py)

Todos hablan el mismo protocolo. n8n o cualquier cliente solo
necesita saber el puerto del provider que quiere.
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

from .copilot import app as copilot_app
from .codex import app as codex_app
from .ollama_cloud import app as ollama_cloud_app
from bago.ollama_runtime import (
    DEFAULT_BAGO_API_PORT,
    DEFAULT_BAGO_CODEX_PORT,
    DEFAULT_BAGO_COPILOT_PORT,
    DEFAULT_BAGO_OLLAMA_CLOUD_PORT,
    default_ollama_port,
    env_port,
)

PORTS = {
    "ollama-local":   default_ollama_port(),  # Ollama nativo
    "bago":           env_port("BAGO_API_PORT", "BAGO_PORT", default=DEFAULT_BAGO_API_PORT),  # Orquestador
    "copilot":        env_port("BAGO_COPILOT_PORT", "BAGO_PORT", default=DEFAULT_BAGO_COPILOT_PORT),  # GitHub Models
    "codex":          env_port("BAGO_CODEX_PORT", "BAGO_PORT", default=DEFAULT_BAGO_CODEX_PORT),  # OpenAI
    "ollama-cloud":   env_port("BAGO_OLLAMA_CLOUD_PORT", "BAGO_PORT", default=DEFAULT_BAGO_OLLAMA_CLOUD_PORT),  # Ollama Cloud
}

__all__ = ["copilot_app", "codex_app", "ollama_cloud_app", "PORTS"]
