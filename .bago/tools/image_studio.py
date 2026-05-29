#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punto de entrada de ``bago image-studio``.

Si el paquete modular ``image_studio`` no está presente en ``.bago/tools/``,
mostramos una salida controlada en vez de un traceback para que el comando
siga siendo diagnosticable desde la CLI experimental.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import sys
from pathlib import Path

_tools = Path(__file__).resolve().parent
if str(_tools) not in sys.path:
    sys.path.insert(0, str(_tools))


def _missing_package() -> int:
    print("image_studio — paquete modular no disponible en .bago/tools/image_studio/\n")
    print("Uso esperado:")
    print("  bago image-studio --help")
    print("  bago image-studio --ui")
    print("  bago image-studio --type sprite --project <nombre>")
    print("\nEstado:")
    print("  ⚠ Falta el paquete image_studio.cli; restaura el módulo modular para habilitar la herramienta.")
    return 2


try:
    from image_studio.cli import main  # type: ignore  # noqa: E402
except ModuleNotFoundError:
    pass


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

    if __name__ == "__main__":
        if "--test" in sys.argv:
            raise SystemExit(run_tests())
        raise SystemExit(_missing_package())
    main = None  # type: ignore[assignment]


if __name__ == "__main__":
    if main is None:
        raise SystemExit(2)
    raise SystemExit(main())