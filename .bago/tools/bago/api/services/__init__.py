"""bago.api.services — Proxies BAGO para providers externos.

Cada proxy expone la misma API BAGO-compatible en su puerto:
  - Ollama local:  11434 (ya existe, no necesita proxy)
  - BAGO orquestador: 11435 (server.py)
  - Copilot (GitHub Models): 11436 (copilot.py)
  - Codex (OpenAI):         11437 (codex.py)
  - Ollama Cloud:           11438 (ollama_cloud.py)

Todos hablan el mismo protocolo. n8n o cualquier cliente solo
necesita saber el puerto del provider que quiere.
"""

from .copilot import app as copilot_app
from .codex import app as codex_app
from .ollama_cloud import app as ollama_cloud_app

PORTS = {
    "ollama-local":   11434,  # Ollama nativo
    "bago":           11435,  # Orquestador
    "copilot":        11436,  # GitHub Models
    "codex":          11437,  # OpenAI
    "ollama-cloud":   11438,  # Ollama Cloud
}

__all__ = ["copilot_app", "codex_app", "ollama_cloud_app", "PORTS"]
