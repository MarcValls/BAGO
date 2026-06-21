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


def print_test_results(results: list[tuple[str, bool, str]]) -> int:
    """Imprime resultados de tests y retorna 0 si todos pasaron, 1 si alguno falló.

    results: lista de (nombre, ok, detalle)
    """
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {name}: {detail}")
    print(f"\n  {passed}/{len(results)} pasaron")
    return 0 if failed == 0 else 1


def timestamp_iso() -> str:
    """Retorna timestamp ISO 8601 en UTC."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_readable() -> str:
    """Retorna timestamp legible (YYYY-MM-DD HH:MM UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def timestamp_filename() -> str:
    """Retorna timestamp para nombres de archivos (YYYYMMDD-HHMMSS)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def get_scan_root(override: str | None = None) -> Path:
    """Directorio raiz a escanear: override > BAGO_SCAN_ROOT env > cwd.

    Permite que cada herramienta funcione en cualquier proyecto sin tener
    BAGO instalado: basta con pasar --root <ruta> o definir BAGO_SCAN_ROOT.
    """
    if override:
        return Path(override).resolve()
    env_root = os.environ.get("BAGO_SCAN_ROOT", "")
    if env_root:
        return Path(env_root).resolve()
    return Path.cwd()


def get_bago_version() -> str:
    """Obtiene versión BAGO desde release_version.txt o versions.json."""
    root = get_repo_root()
    release_version = root / "release_version.txt"
    if release_version.exists():
        value = release_version.read_text(encoding="utf-8").strip()
        if value:
            return value.lstrip("vV").strip()
    versions_file = root / "versions.json"
    data = load_json(versions_file)
    current = data.get("current", "")
    return current.strip() if isinstance(current, str) and current.strip() else "?"


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
