#!/usr/bin/env python3
"""bago_config.py — Helper para leer configuraciones externas de BAGO.

Provee load_config(name, fallback) que lee .bago/state/config/{name}.json
con manejo de errores elegante — nunca rompe el script que lo usa.

Uso:
    from bago_config import load_config
    rules = load_config("scan_config", fallback={"exclude_dirs": []})
    python3 bago_config.py --list   # lista configs disponibles
    python3 bago_config.py --test   # self-tests
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "state" / "config"


def load_config(name: str, fallback: object = None) -> object:
    """Lee .bago/state/config/{name}.json y devuelve su contenido.

    Si el archivo no existe o tiene JSON inválido, devuelve `fallback`.
    Nunca lanza excepción — diseñado para usarse en scripts críticos.
    """
    path = _CONFIG_DIR / f"{name}.json"
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def config_path(name: str) -> Path:
    """Devuelve el Path absoluto a .bago/state/config/{name}.json."""
    return _CONFIG_DIR / f"{name}.json"


def save_config(name: str, data: object) -> bool:
    """Guarda data en .bago/state/config/{name}.json.

    Devuelve True si tuvo éxito, False si falló.
    """
    path = _CONFIG_DIR / f"{name}.json"
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def _cmd_list() -> None:
    if not _CONFIG_DIR.exists():
        print("  (directorio .bago/state/config/ no existe)")
        return
    files = sorted(_CONFIG_DIR.glob("*.json"))
    if not files:
        print("  (sin configs)")
        return
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            top_keys = list(data.keys())[:3] if isinstance(data, dict) else ["(array)"]
            print(f"  {f.name:<35} claves: {top_keys}")
        except Exception:
            print(f"  {f.name:<35} (JSON inválido)")


def _self_test() -> None:
    """Autotest mínimo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"

    result = load_config("__nonexistent__", fallback={"ok": True})
    assert result == {"ok": True}, f"fallback falló: {result}"

    result_none = load_config("__nonexistent__")
    assert result_none is None, f"fallback None falló: {result_none}"

    print("  3/3 tests pasaron")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--test" in args:
        _self_test()
        raise SystemExit(0)
    if "--list" in args or not args:
        print("\n  BAGO · Configs externas disponibles")
        print("  " + "─" * 44)
        _cmd_list()
        print()
        raise SystemExit(0)
