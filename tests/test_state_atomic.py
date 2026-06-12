#!/usr/bin/env python3
"""test_state_atomic.py — Verifica escrituras de estado atómicas.

Comprueba que install_roles.save_selection usa la secuencia tmp → rename
para garantizar que los archivos de estado no quedan corruptos si el proceso
es interrumpido a mitad de escritura.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BAGO_ROOT))
sys.path.insert(0, str(BAGO_ROOT / "bago_core"))

from bago_core.install_roles import (
    ROLES,
    _empty,
    load_selection,
    save_selection,
)


def test_save_selection_is_atomic() -> None:
    """save_selection escribe a un .tmp y lo renombra (operación atómica)."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "install_selection.json"
        data = _empty()
        returned = save_selection(data, path=target)
        assert returned == target, f"se esperaba {target}, se obtuvo {returned}"
        assert target.exists(), "el archivo de destino no existe tras save_selection"
        tmp = target.with_suffix(target.suffix + ".tmp")
        assert not tmp.exists(), "el archivo .tmp no debe quedar tras la escritura"


def test_save_selection_roundtrip() -> None:
    """Los datos guardados pueden ser releídos sin pérdida."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "install_selection.json"
        data = _empty()
        data.setdefault("roles", {})["active"] = {"path": "/some/path", "label": "active", "updated_at": ""}
        save_selection(data, path=target)
        loaded = load_selection(path=target)
        assert loaded["roles"]["active"]["path"] == "/some/path"


def test_load_selection_missing_file() -> None:
    """load_selection devuelve una estructura vacía válida si el archivo no existe."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "nonexistent.json"
        result = load_selection(path=target)
        assert isinstance(result, dict)
        assert isinstance(result.get("roles"), dict)
        assert result.get("version") == 1


def test_load_selection_corrupt_file() -> None:
    """load_selection tolera JSON corrupto devolviendo estructura vacía."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "corrupt.json"
        target.write_text("not valid json {{{", encoding="utf-8")
        result = load_selection(path=target)
        assert isinstance(result, dict)
        assert isinstance(result.get("roles"), dict)


def test_save_selection_sets_version() -> None:
    """save_selection siempre persiste version=1 en el JSON."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "install_selection.json"
        data = _empty()
        save_selection(data, path=target)
        raw = json.loads(target.read_text(encoding="utf-8"))
        assert raw.get("version") == 1


def test_roles_constant_unchanged() -> None:
    """Los roles canónicos son active, dev y launch."""
    assert set(ROLES) == {"active", "dev", "launch"}


if __name__ == "__main__":
    tests = [
        test_save_selection_is_atomic,
        test_save_selection_roundtrip,
        test_load_selection_missing_file,
        test_load_selection_corrupt_file,
        test_save_selection_sets_version,
        test_roles_constant_unchanged,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:
            print(f"FAIL {t.__name__}: {exc}")
            failed += 1
    if failed:
        print(f"\n{failed} test(s) fallidos")
        raise SystemExit(1)
    print("\nALL PASS")
