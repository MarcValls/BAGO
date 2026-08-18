"""blacklist_models.py — Blocklist de modelos por máquina (no global).

Cada instalación de BAGO puede tener su propio conjunto de modelos
excluidos. Por ejemplo, una máquina con poca RAM puede querer bloquear
los modelos de 30B+ que otro nodo más potente sí permite.

Archivo: <state root canónico>/model_blacklist.json.
La ruta ~/.bago/state se conserva solo como fallback de lectura legacy.

Formato:
    {
      "version": 1,
      "models": ["qwen3.6:latest", "llama3.2:1b"],
      "reasons": {
        "qwen3.6:latest": "temperature=1, presence_penalty=1.5 → diverge",
        "llama3.2:1b": "degenerate en español sin fine-tune"
      },
      "auto_blocked_on_first_run": true
    }

El archivo se crea la primera vez con defaults sensatos derivados del
benchmark local. Después es editable por el usuario.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from bago_core.user_state_paths import state_read_candidates, state_root


# Razones por las que bloqueamos por defecto. NO son verdades absolutas:
# si en otra máquina esos modelos funcionan bien, el usuario los puede
# quitar. Aquí solo reflejamos lo que el benchmark local demostró.
_DEFAULT_REASONS: dict[str, str] = {
    "qwen3.6:latest": (
        "Modelfile con temperature=1, presence_penalty=1.5, min_p=0: "
        "divergió en benchmark local (240s timeout, salida vacía)."
    ),
    "llama3.2:1b": (
        "1B params: degenera a gibberish (ratio letras <0.30) en prompts "
        "largos. Subir a 3b o usar bago-llama32-bago-persona."
    ),
    "bago-eyes:latest": (
        "Modelo de visión: no responde a chat de texto. Usar solo desde "
        "el flujo /vision."
    ),
    "minicpm-v:latest": (
        "Modelo de visión: no responde a chat de texto. Usar solo desde "
        "el flujo /vision."
    ),
}


def _state_dir() -> Path:
    """Resolve the canonical mutable state directory."""
    return state_root()


def _blacklist_path() -> Path:
    return _state_dir() / "model_blacklist.json"


def _blacklist_read_paths() -> tuple[Path, ...]:
    return state_read_candidates("model_blacklist.json")


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass
        raise


def _ensure_file() -> dict:
    """Lee la blocklist, creándola con defaults si no existe.

    Devuelve SIEMPRE el dict completo, incluso si el archivo se acaba de
    crear. Si el archivo existía pero no tenía la clave `models`, lo
    completa sin pisar lo que el usuario ya tenía.
    """
    path = _blacklist_path()
    data: dict = {}
    for candidate in _blacklist_read_paths():
        data = _read(candidate)
        if data:
            break
    if not data:
        data = {
            "version": 1,
            "models": sorted(_DEFAULT_REASONS.keys()),
            "reasons": dict(_DEFAULT_REASONS),
            "auto_blocked_on_first_run": True,
        }
        _write_atomic(path, data)
        return data
    if "models" not in data or not isinstance(data.get("models"), list):
        data["models"] = []
    if "reasons" not in data or not isinstance(data.get("reasons"), dict):
        data["reasons"] = {}
    data.setdefault("version", 1)
    return data


def is_blacklisted(model_name: str) -> bool:
    if not model_name:
        return False
    data = _ensure_file()
    return model_name in data.get("models", [])


def filter_available(models: Iterable[str]) -> list[str]:
    """Devuelve solo los modelos NO bloqueados, preservando orden y únicos."""
    bl = set(_ensure_file().get("models", []))
    out: list[str] = []
    seen: set[str] = set()
    for m in models:
        if not isinstance(m, str) or not m or m in seen:
            continue
        if m in bl:
            continue
        seen.add(m)
        out.append(m)
    return out


def get_blacklist() -> dict:
    """Snapshot completo: {version, models: [...], reasons: {name: reason}}."""
    return _ensure_file()


def add(model_name: str, reason: str = "") -> dict:
    if not model_name:
        raise ValueError("model_name requerido")
    data = _ensure_file()
    models = list(data.get("models", []))
    if model_name not in models:
        models.append(model_name)
    reasons = dict(data.get("reasons", {}))
    if reason:
        reasons[model_name] = reason
    elif model_name not in reasons:
        reasons[model_name] = "Añadido manualmente"
    data["models"] = sorted(models)
    data["reasons"] = reasons
    data["auto_blocked_on_first_run"] = False
    _write_atomic(_blacklist_path(), data)
    return data


def remove(model_name: str) -> dict:
    data = _ensure_file()
    models = [m for m in data.get("models", []) if m != model_name]
    reasons = dict(data.get("reasons", {}))
    reasons.pop(model_name, None)
    data["models"] = sorted(models)
    data["reasons"] = reasons
    data["auto_blocked_on_first_run"] = False
    _write_atomic(_blacklist_path(), data)
    return data


def reset_to_defaults() -> dict:
    """Restaurar la blocklist a los defaults del benchmark local."""
    data = {
        "version": 1,
        "models": sorted(_DEFAULT_REASONS.keys()),
        "reasons": dict(_DEFAULT_REASONS),
        "auto_blocked_on_first_run": True,
    }
    _write_atomic(_blacklist_path(), data)
    return data
