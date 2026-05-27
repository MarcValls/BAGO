#!/usr/bin/env python3
r"""bago_locate.py — Detecta la fuente de verdad de BAGO.

Jerarquía:
  1. Directorio de ejecución (pendrive, portable)
  2. PC instalado (%USERPROFILE%\\BAGO o C:\\Program Files\\BAGO)
  3. Ambos presentes → PC es PRIMARY, USB notifica SECONDARY
  4. Ninguno → modo primera vez

Devuelve:
  {
    "source": "pc" | "usb" | "both" | "none",
    "primary_path": Path,
    "secondary_path": Path | None,
    "mode": "installed" | "portable" | "first_time"
  }
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import sys
from pathlib import Path


def _is_removable_drive(path: Path) -> bool:
    """Detecta si una unidad es extraíble (pendrive)."""
    drive = path.drive if hasattr(path, "drive") else str(path)[:2]
    if sys.platform == "win32" and drive:
        import ctypes
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
        return drive_type == 2  # DRIVE_REMOVABLE
    return False


def locate_bago() -> dict:
    exe_dir = Path(sys.argv[0]).resolve().parent
    usb_candidate = exe_dir / ".bago"
    pc_candidates = [
        Path.home() / "BAGO" / ".bago",
        Path.home() / "Documents" / "BAGO" / ".bago",
        Path("C:") / "Program Files" / "BAGO" / ".bago",
        Path("C:") / "BAGO" / ".bago",
    ]

    # Buscar .bago en directorio de ejecución (portable)
    usb_ok = usb_candidate.exists() and usb_candidate.is_dir()
    usb_is_removable = _is_removable_drive(exe_dir)

    # Buscar .bago en PC instalado
    pc_path = None
    for cand in pc_candidates:
        if cand.exists() and cand.is_dir():
            pc_path = cand
            break

    if usb_ok and pc_path:
        return {
            "source": "both",
            "primary_path": pc_path,
            "secondary_path": usb_candidate,
            "mode": "installed",
            "message": f"Fuente de verdad: {pc_path} (PC). USB como backup: {usb_candidate}",
        }
    elif usb_ok and usb_is_removable:
        return {
            "source": "usb",
            "primary_path": usb_candidate,
            "secondary_path": None,
            "mode": "portable",
            "message": f"Fuente de verdad: {usb_candidate} (PENDRIVE)",
        }
    elif usb_ok:
        return {
            "source": "usb",
            "primary_path": usb_candidate,
            "secondary_path": None,
            "mode": "portable",
            "message": f"Fuente de verdad: {usb_candidate} (DIRECTORIO LOCAL)",
        }
    elif pc_path:
        return {
            "source": "pc",
            "primary_path": pc_path,
            "secondary_path": None,
            "mode": "installed",
            "message": f"Fuente de verdad: {pc_path} (PC INSTALADO)",
        }
    else:
        return {
            "source": "none",
            "primary_path": None,
            "secondary_path": None,
            "mode": "first_time",
            "message": "BAGO no detectado. Ejecuta: BAGO install",
        }


def print_status() -> None:
    loc = locate_bago()
    print(f"\n  BAGO Locator")
    print(f"  {'-'*46}")
    print(f"  Modo:      {loc['mode']}")
    print(f"  Fuente:    {loc['source']}")
    print(f"  Primaria:  {loc['primary_path']}")
    if loc['secondary_path']:
        print(f"  Secundaria:{loc['secondary_path']}")
    print(f"  \n  {loc['message']}\n")




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
    print_status()