#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bago_instance_manager.py — Gestión de múltiples instalaciones BAGO.

Uso:
  bago list                        → lista instalaciones detectadas
  bago instance register <path> [--name nombre]
  bago instance unregister <nombre>
  bago instance create <nombre> [--from <path>]
  bago instance switch <nombre>  → crea/actualiza wrapper bago<N>
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


if sys.platform == "win32":
    _INSTANCES_FILE = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "BAGO" / "instances.json"
else:
    _INSTANCES_FILE = Path.home() / ".bago" / "instances.json"
_INSTANCES_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load() -> dict:
    if _INSTANCES_FILE.exists():
        try:
            return json.loads(_INSTANCES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save(data: dict) -> None:
    _INSTANCES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _detect_auto() -> dict[str, str]:
    found: dict[str, str] = {}
    candidates = []
    if sys.platform == "win32":
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates += [
            pf / "BAGO",
            Path.home() / "BAGO",
            Path.home() / "Documents" / "BAGO",
            Path.home() / ".bago",
        ]
        # USB
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in range(26):
                if bitmask & (1 << letter):
                    drive = Path(f"{chr(65+letter)}:\\")
                    if (drive / ".bago_portable").exists() and (drive / "bago" / "runtime_contract.json").exists():
                        candidates.append(drive / "bago")
        except Exception:
            pass
    else:
        candidates += [
            Path.home() / "BAGO",
            Path.home() / ".bago",
            Path("/opt/BAGO"),
            Path("/usr/local/BAGO"),
        ]

    for cand in candidates:
        marker = cand / "runtime_contract.json"
        if marker.exists() and str(cand) not in found.values():
            name = cand.name.lower()
            if name == "bago":
                name = "main"
            found[name] = str(cand)
    return found

def cmd_list() -> int:
    registered = _load()
    auto = _detect_auto()
    merged = dict(auto)
    merged.update(registered)

    print("\n  Instalaciones BAGO detectadas:\n")
    print(f"  {'NOMBRE':<12} {'RUTA':<50} {'ORIGEN'}")
    print(f"  {'-'*12} {'-'*50} {'-'*10}")
    for name, path in sorted(merged.items()):
        origin = "registrada" if name in registered else "auto"
        print(f"  {name:<12} {path:<50} {origin}")
    print()
    print("  Comandos:")
    print("    bago instance register <path> [--name nombre]")
    print("    bago instance create <nombre> [--from <path>]")
    print("    bago instance switch <nombre>")
    print()
    return 0

def cmd_register(path: str, name: str | None = None) -> int:
    p = Path(path).resolve()
    if not (p / "runtime_contract.json").exists():
        print(f"[X] No parece una instalacion BAGO: {p}")
        return 1
    data = _load()
    n = name or p.name.lower()
    data[n] = str(p)
    _save(data)
    print(f"[ok] Instalacion '{n}' registrada: {p}")
    return 0

def cmd_unregister(name: str) -> int:
    data = _load()
    if name not in data:
        print(f"[X] '{name}' no esta registrada")
        return 1
    del data[name]
    _save(data)
    print(f"[ok] '{name}' eliminada del registro")
    return 0

def cmd_create(name: str, from_path: str | None = None) -> int:
    if not from_path:
        auto = _detect_auto()
        from_path = auto.get("main") or next(iter(auto.values()), None)
    if not from_path:
        print("[X] No hay instalacion origen. Usa --from <path>")
        return 1
    src = Path(from_path).resolve()
    if not (src / "runtime_contract.json").exists():
        print(f"[X] Origen invalido: {src}")
        return 1

    base = Path.home() / "BAGO" / "instances"
    base.mkdir(parents=True, exist_ok=True)
    dest = base / name
    if dest.exists():
        print(f"[X] Ya existe: {dest}")
        return 1

    print(f"[...] Clonando {src} → {dest}")
    items = [src / ".bago", src / "bago_core", src / "bago.cmd", src / "bago.ps1",
             src / "runtime_contract.json", src / "README.md", src / "CHANGELOG.md"]
    dest.mkdir(parents=True, exist_ok=True)
    for item in items:
        if not item.exists():
            continue
        dst = dest / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
            else:
                shutil.copy2(item, dst)
        except Exception as exc:
            print(f"[!] {item.name}: {exc}")
    data = _load()
    data[name] = str(dest)
    _save(data)
    print(f"[ok] Instancia '{name}' creada en {dest}")
    print(f"[tip] Usa: bago instance switch {name}")
    return 0

def cmd_switch(name: str) -> int:
    data = _load()
    auto = _detect_auto()
    merged = dict(auto)
    merged.update(data)
    if name not in merged:
        print(f"[X] Instancia '{name}' no encontrada. Ejecuta: bago list")
        return 1
    path = Path(merged[name])
    bin_dir = Path.home() / "BAGO" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Crear wrapper bago<N>.ps1
    wrapper = bin_dir / f"bago{name}.ps1"
    wrapper.write_text(
        f"# Auto-generated BAGO instance wrapper for '{name}'\n"
        f"$env:BAGO_INSTANCE = '{name}'\n"
        f"$env:BAGO_INSTANCE_PATH = '{path}'\n"
        f"& '{path / 'bago.ps1'}' @args\n",
        encoding="utf-8",
    )
    # Crear wrapper bago<N>.cmd
    cmd_wrapper = bin_dir / f"bago{name}.cmd"
    cmd_wrapper.write_text(
        f"@echo off\n"
        f"set BAGO_INSTANCE={name}\n"
        f"set BAGO_INSTANCE_PATH={path}\n"
        f"powershell -NoProfile -ExecutionPolicy Bypass -File \"{wrapper}\" %*\n",
        encoding="utf-8",
    )
    print(f"[ok] Wrapper creado: {wrapper}")
    print(f"[tip] Añade al PATH: {bin_dir}")
    print(f"[tip] Usa: bago{name} <comando>")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(prog="bago instance")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="Listar instalaciones")
    p_reg = sub.add_parser("register", help="Registrar instalacion")
    p_reg.add_argument("path")
    p_reg.add_argument("--name", default=None)
    p_unreg = sub.add_parser("unregister", help="Eliminar del registro")
    p_unreg.add_argument("name")
    p_create = sub.add_parser("create", help="Crear nueva instancia")
    p_create.add_argument("name")
    p_create.add_argument("--from", dest="from_path", default=None)
    p_switch = sub.add_parser("switch", help="Crear wrapper para instancia")
    p_switch.add_argument("name")

    args = parser.parse_args()
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "register":
        return cmd_register(args.path, args.name)
    if args.cmd == "unregister":
        return cmd_unregister(args.name)
    if args.cmd == "create":
        return cmd_create(args.name, args.from_path)
    if args.cmd == "switch":
        return cmd_switch(args.name)
    parser.print_help()
    return 0



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
    raise SystemExit(main())