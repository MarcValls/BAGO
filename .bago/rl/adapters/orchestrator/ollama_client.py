# -*- coding: utf-8 -*-
"""ollama_client.py — Wrapper mínimo de la API chat de Ollama local."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def chat(model: str, messages: list[dict], tools: list[dict] | None = None, timeout: int = 60) -> dict:
    """Envía chat request a Ollama local y devuelve la respuesta parseada."""
    url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        }
    }
    if tools:
        payload["tools"] = tools

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
