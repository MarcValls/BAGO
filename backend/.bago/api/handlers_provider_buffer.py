#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers_provider_buffer.py -- Provider buffer management endpoints.

Implementa:
  GET  /provider/buffer/status       -> lista modelos cargados
  POST /provider/buffer/prepare      -> prepara/carga un modelo
  POST /provider/buffer/unload       -> descarga modelos (uno o todos)
  POST /provider/buffer/unload/<name> -> descarga un modelo especifico

CANON[PB-001]: Mantener compatibilidad con el cliente frontend que
utiliza OperationalTools.tsx para gestionar el buffer de modelos.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


# Estado en memoria del buffer. Persiste durante la sesion del backend.
_BUFFER_STATE: dict[str, dict[str, Any]] = {}
_BUFFER_DIR = Path(os.environ.get("BAGO_BUFFER_DIR", os.path.join(os.path.expanduser("~"), ".bago", "buffer")))
_BUFFER_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> float:
    return time.time()


def _expire_old() -> None:
    """Elimina entradas expiradas (TTL 1h por defecto)."""
    now = _now()
    expired = [name for name, info in _BUFFER_STATE.items() if info.get("expires_at", 0) < now]
    for name in expired:
        _BUFFER_STATE.pop(name, None)


def _read_body(handler) -> dict[str, Any]:
    """Lee el body JSON del request."""
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body_bytes = handler.rfile.read(length)
        return json.loads(body_bytes.decode("utf-8", errors="replace"))
    except Exception:
        return {}


def handle_status(handler) -> None:
    """GET /provider/buffer/status - lista modelos en buffer."""
    _expire_old()
    handler._send_json(200, {
        "ok": True,
        "loaded": list(_BUFFER_STATE.values()),
        "count": len(_BUFFER_STATE),
        "ttl_seconds": 3600,
    })


def handle_prepare(handler) -> None:
    """POST /provider/buffer/prepare - carga un modelo al buffer."""
    body = _read_body(handler)
    model = (body.get("model") or "").strip()
    policy = body.get("policy", "default")

    if not model:
        handler._send_json(400, {"ok": False, "error": "model requerido"})
        return

    # Simula la carga (en produccion haria una llamada al provider)
    entry = {
        "name": model,
        "policy": policy,
        "size_gb": round(len(model) * 0.1 + 1.5, 2),  # tamanyo simulado
        "loaded_at": _now(),
        "expires_at": _now() + 3600,  # 1 hora
    }
    _BUFFER_STATE[model] = entry

    handler._send_json(200, {
        "ok": True,
        "model": model,
        "policy": policy,
        "size_gb": entry["size_gb"],
        "expires_at": entry["expires_at"],
    })


def handle_unload(handler, model_name: str = None) -> None:
    """POST /provider/buffer/unload - descarga modelos del buffer."""
    _expire_old()

    if model_name:
        # Descarga un modelo especifico
        if model_name in _BUFFER_STATE:
            _BUFFER_STATE.pop(model_name)
            handler._send_json(200, {"ok": True, "unloaded": [model_name]})
        else:
            handler._send_json(404, {"ok": False, "error": f"Modelo {model_name} no esta en buffer"})
    else:
        # Descarga todos
        unloaded = list(_BUFFER_STATE.keys())
        _BUFFER_STATE.clear()
        handler._send_json(200, {"ok": True, "unloaded": unloaded, "count": len(unloaded)})
