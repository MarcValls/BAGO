#!/usr/bin/env python3
"""verify_release_drift.py — Verifica consistencia de versiones entre archivos de release.

Comprueba que ``release_version.txt`` y ``versions.json`` están alineados.
Sale con código 0 si todo está en orden, 1 si hay deriva de versión.

Uso:
    python scripts\\verify_release_drift.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_release_version_txt() -> str:
    path = REPO_ROOT / "release_version.txt"
    if not path.exists():
        raise FileNotFoundError(f"release_version.txt no encontrado en {REPO_ROOT}")
    return path.read_text(encoding="utf-8").strip()


def _read_versions_json_current() -> str:
    path = REPO_ROOT / "versions.json"
    if not path.exists():
        raise FileNotFoundError(f"versions.json no encontrado en {REPO_ROOT}")
    data = json.loads(path.read_text(encoding="utf-8"))
    current = data.get("current")
    if not current:
        raise ValueError("versions.json no contiene clave 'current'")
    return current


def main() -> int:
    errors: list[str] = []

    try:
        txt_ver = _read_release_version_txt()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    try:
        json_ver = _read_versions_json_current()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    if txt_ver != json_ver:
        errors.append(
            f"release_version.txt={txt_ver!r} != versions.json.current={json_ver!r}"
        )

    if errors:
        print("release:DRIFT")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"release:ok (version={txt_ver})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
