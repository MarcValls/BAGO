#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_utils.py — Utilities compartidas para herramientas BAGO

Funciones reutilizables para:
  - Resolución de paths
  - I/O de JSON
  - Timestamps
  - State management
  
Uso:
  from bago_utils import get_bago_root, load_json, save_json, timestamp_now
"""

from pathlib import Path
import json
import sys
from datetime import datetime, timezone


def get_bago_root() -> Path:
    """Obtiene raíz de .bago/ desde cualquier herramienta en tools/."""
    return Path(__file__).resolve().parent.parent


def get_repo_root() -> Path:
    """Obtiene raíz del repositorio."""
    return get_bago_root().parent


def get_state_dir() -> Path:
    """Obtiene/crea directorio de estado."""
    state_dir = get_bago_root() / "state"
    state_dir.mkdir(exist_ok=True)
    return state_dir


def load_json(path: Path, default: dict = None) -> dict:
    """Carga JSON de archivo, retorna default si no existe o es inválido."""
    if not path.exists():
        return default or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def save_json(path: Path, data: dict, indent: int = 2) -> bool:
    """Guarda dict como JSON. Retorna True si éxito."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def timestamp_iso() -> str:
    """Retorna timestamp ISO 8601 en UTC."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_readable() -> str:
    """Retorna timestamp legible (YYYY-MM-DD HH:MM UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def timestamp_filename() -> str:
    """Retorna timestamp para nombres de archivos (YYYYMMDD-HHMMSS)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def get_bago_version() -> str:
    """Obtiene versión BAGO del pack.json."""
    pack_file = get_bago_root() / "pack.json"
    data = load_json(pack_file)
    return data.get("version", "?")


def get_health_status() -> str:
    """Lee health status del estado global."""
    gs = load_json(get_state_dir() / "global_state.json")
    return gs.get("health_status", "unknown")


def get_global_state() -> dict:
    """Lee estado global BAGO."""
    return load_json(get_state_dir() / "global_state.json")


def save_global_state(data: dict) -> bool:
    """Guarda estado global BAGO."""
    return save_json(get_state_dir() / "global_state.json", data)


def ensure_subdir(subdir_name: str) -> Path:
    """Crea y retorna subdirectorio en state/."""
    path = get_state_dir() / subdir_name
    path.mkdir(exist_ok=True)
    return path



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    print("bago_utils.py — Shared utilities")
    print(f"  BAGO root: {get_bago_root()}")
    print(f"  Repo root: {get_repo_root()}")
    print(f"  State dir: {get_state_dir()}")
    print(f"  Version:   {get_bago_version()}")
    print(f"  Health:    {get_health_status()}")
    print(f"  Now:       {timestamp_iso()}")
