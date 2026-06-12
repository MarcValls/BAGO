#!/usr/bin/env python3
"""clean_install_smoke.py — Smoke test de instalación limpia.

Verifica que los módulos críticos de BAGO son importables y que el sistema
puede arrancar desde un directorio temporal sin estado previo.

Usa únicamente módulos de la stdlib y del propio BAGO (sin dependencias externas).

Uso:
    python scripts\\clean_install_smoke.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BAGO_ROOT))
sys.path.insert(0, str(BAGO_ROOT / "bago_core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "api"))


def _check_module(name: str, from_path: str | None = None) -> None:
    """Importa un módulo y falla con mensaje claro si no se puede."""
    import importlib
    try:
        importlib.import_module(name)
    except ImportError as exc:
        raise ImportError(f"módulo crítico no importable: {name} — {exc}") from exc


def test_core_modules_importable() -> None:
    """Los módulos core de BAGO son importables desde un entorno limpio."""
    _check_module("bago_core.install_roles")
    _check_module("bago_core.claim_model")
    _check_module("bago_core.claim_storage")


def test_config_manager_defaults_clean() -> None:
    """ConfigManager arranca con defaults seguros en directorio vacío."""
    sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
    from config_manager import ConfigManager, DEFAULT_CONFIG

    with tempfile.TemporaryDirectory() as td:
        cfg = ConfigManager(base_path=td)
        assert cfg.get("default_provider") == DEFAULT_CONFIG["default_provider"]
        assert cfg.get("features.auto_allow_tools") is False, (
            "auto_allow_tools debe ser False en instalación limpia"
        )


def test_install_roles_empty_state() -> None:
    """load_selection devuelve estado vacío en instalación sin historial."""
    from bago_core.install_roles import load_selection, _empty

    with tempfile.TemporaryDirectory() as td:
        result = load_selection(path=Path(td) / "nonexistent.json")
        expected = _empty()
        assert result["version"] == expected["version"]
        assert isinstance(result["roles"], dict)
        assert len(result["roles"]) == 0


def test_versions_json_readable() -> None:
    """versions.json es legible y contiene la clave 'current'."""
    import json
    path = BAGO_ROOT / "versions.json"
    assert path.exists(), "versions.json no encontrado"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "current" in data, "versions.json no contiene 'current'"
    assert isinstance(data["current"], str) and data["current"]


def test_release_version_txt_readable() -> None:
    """release_version.txt es legible y no está vacío."""
    path = BAGO_ROOT / "release_version.txt"
    assert path.exists(), "release_version.txt no encontrado"
    ver = path.read_text(encoding="utf-8").strip()
    assert ver, "release_version.txt está vacío"


if __name__ == "__main__":
    tests = [
        test_core_modules_importable,
        test_config_manager_defaults_clean,
        test_install_roles_empty_state,
        test_versions_json_readable,
        test_release_version_txt_readable,
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
