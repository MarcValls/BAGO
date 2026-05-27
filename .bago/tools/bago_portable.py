#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bago_portable.py -- BAGO Portable: crea, detecta y sincroniza instalaciones en pen drive."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

def GREEN(s):  return f"\033[32m{s}\033[0m"
def RED(s):    return f"\033[31m{s}\033[0m"
def CYAN(s):   return f"\033[36m{s}\033[0m"
def YELLOW(s): return f"\033[33m{s}\033[0m"
def DIM(s):    return f"\033[2m{s}\033[0m"
def BOLD(s):   return f"\033[1m{s}\033[0m"

THIS_FILE   = Path(__file__).resolve()
TOOLS_DIR   = THIS_FILE.parent
BAGO_ROOT   = TOOLS_DIR.parent
STATE_DIR   = BAGO_ROOT / "state"

_ACTIVE_INSTALL = None

def _find_active_install():
    global _ACTIVE_INSTALL
    if _ACTIVE_INSTALL:
        return _ACTIVE_INSTALL
    cand = TOOLS_DIR.parent.parent
    if (cand / "bago_core").exists() and (cand / ".bago").exists():
        _ACTIVE_INSTALL = cand
        return cand
    pf = Path(os.environ["ProgramFiles"]) if os.environ.get("ProgramFiles") else Path.home().parent / "Program Files"
    if (pf / "BAGO" / "bago_core").exists():
        _ACTIVE_INSTALL = pf / "BAGO"
        return _ACTIVE_INSTALL
    if (TOOLS_DIR / "bago_core").exists():
        _ACTIVE_INSTALL = TOOLS_DIR.parent
        return _ACTIVE_INSTALL
    return None

def _portable_marker(drive: Path):
    return drive / ".bago_portable"

def _portable_base(drive: Path) -> Path | None:
    """Devuelve la carpeta base del pen portable si existe."""
    for folder in ("bago", "BAGO"):
        base = drive / folder
        if (base / ".bago").exists():
            return base
    return None

def _is_portable(drive: Path):
    return _portable_marker(drive).exists() or _portable_base(drive) is not None

def _get_removable_drives():
    system = platform.system()
    drives = []
    if system == "Windows":
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in range(26):
                if bitmask & (1 << letter):
                    drive = Path(f"{chr(65+letter)}:\\")
                    if not drive.exists():
                        continue
                    if _is_portable(drive):
                        drives.append(drive)
                        continue
                    try:
                        result = subprocess.run(
                            ["powershell", "-NoProfile", "-Command",
                             f"(Get-Volume -DriveLetter '{chr(65+letter)}').DriveType"],
                            capture_output=True, text=True, timeout=5,
                        )
                        if "Removable" in result.stdout:
                            drives.append(drive)
                    except Exception:
                        pass
        except Exception:
            pass
    elif system == "Darwin":
        try:
            for vol in Path("/Volumes").glob("*"):
                if vol.is_mount():
                    drives.append(vol)
        except Exception:
            pass
    else:
        try:
            for m in Path("/media").rglob("*"):
                if m.is_mount():
                    drives.append(m)
            for m in Path("/run/media").rglob("*"):
                if m.is_mount():
                    drives.append(m)
        except Exception:
            pass
    return drives

def _get_drive_size(drive: Path):
    try:
        if platform.system() == "Windows":
            import ctypes
            from ctypes import wintypes
            path = str(drive)
            if not path.endswith("\\"):
                path += "\\"
            free = wintypes.ULARGE_INTEGER()
            total = wintypes.ULARGE_INTEGER()
            total_free = wintypes.ULARGE_INTEGER()
            ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                path, ctypes.byref(free), ctypes.byref(total), ctypes.byref(total_free)
            )
            if ok:
                return total.value, free.value
            return 0, 0
        else:
            st = os.statvfs(str(drive))
            return st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
    except Exception:
        return 0, 0

def cmd_detect():
    print(f"\\n  {BOLD('BAGO Portable -- Deteccion de pen drives')}\\n")
    drives = _get_removable_drives()
    if not drives:
        print("  No se detectaron drives removibles.\\n")
        return
    found = False
    for drive in drives:
        total, free = _get_drive_size(drive)
        total_gb = total / (1024**3)
        free_gb = free / (1024**3)
        portable = _is_portable(drive)
        status = f"{GREEN('v BAGO portable')}" if portable else f"{YELLOW('o Sin BAGO')}"
        marker = ""
        if portable:
            try:
                data = json.loads(_portable_marker(drive).read_text(encoding="utf-8"))
                marker = f"  (creado: {data.get('created', '?')})"
            except Exception:
                pass
            found = True
        print(f"  {drive}  {status}  {free_gb:.1f} GB libre / {total_gb:.1f} GB total{marker}")
    if not found:
        print(f"\\n  {YELLOW('Ningun pen tiene BAGO portable instalado.')}")
        print(f"  {DIM('Usa: bago portable create <drive>')}\\n")
    else:
        print()

def cmd_create(drive_str: str, install_models=None, yes: bool = False):
    if install_models is None:
        install_models = []
    drive = Path(drive_str.replace("/", "\\").rstrip("\\"))
    if not drive.exists():
        print(f"  {RED('X')} Drive no encontrado: {drive}")
        return
    total, free = _get_drive_size(drive)
    if total == 0 and not drive.exists():
        print(f"  {RED('X')} No se pudo leer el drive.")
        return
    print(f"\\n  {BOLD('Creando BAGO portable')} en {CYAN(str(drive))}")
    print(f"  Espacio: {free / (1024**3):.1f} GB libre / {total / (1024**3):.1f} GB total")
    if total < 32 * (1024**3):
        print(f"  {YELLOW('!')} El drive tiene menos de 32 GB. Recomendado >=32 GB.")
        if not yes and sys.stdin.isatty():
            ans = input("  Continuar igual? [s/N] ").strip().lower()
            if ans not in ("s", "si", "y", "yes"):
                print("  Cancelado.")
                return
        elif not sys.stdin.isatty() and not yes:
            print(f"  {YELLOW("o")} Entrada no interactiva: usa --yes para forzar.")
            return
    src = _find_active_install()
    if not src:
        print(f"  {RED('X')} No se encontro instalacion BAGO activa.")
        return
    print(f"  {DIM('Origen: ' + str(src))}")
    items = [
        src / ".bago", src / "bago_core", src / "bago.cmd", src / "bago.ps1",
        src / "bago.ico", src / "runtime_contract.json", src / "CHANGELOG.md",
        src / "INSTALL.md", src / "LICENSE", src / "README.md", src / "QUICKSTART.md",
        src / "install.ps1", src / "smoke-test.ps1",
    ]
    dest = drive / "bago"
    dest.mkdir(parents=True, exist_ok=True)
    for item in items:
        if not item.exists():
            continue
        dst = dest / item.name
        try:
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
            else:
                shutil.copy2(item, dst)
            print(f"    {GREEN('v')} {item.name}")
        except Exception as exc:
            print(f"    {RED('X')} {item.name}: {exc}")
    marker = _portable_marker(drive)
    marker.write_text(json.dumps({
        "created": datetime.now().isoformat(),
        "source": str(src),
        "version": "1.0.0",
        "platform": platform.system(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    (drive / "models").mkdir(exist_ok=True)
    (drive / "sessions").mkdir(exist_ok=True)
    print(f"\\n  {GREEN('OK')} BAGO portable creado en {dest}")
    print(f"  {DIM('Usa: bago portable status ' + str(drive))} o arranca con el .ps1/.cmd del pen.\\n")
    if install_models:
        print(f"  {CYAN('->')} Instalando modelos seleccionados...")
        for model in install_models:
            print(f"    {DIM('Modelo: ' + model)} -- placeholder")

def cmd_sync(drive_str: str):
    drive = Path(drive_str.replace("/", "\\").rstrip("\\"))
    base = _portable_base(drive)
    if base is None:
        print(f"  {RED('X')} {drive} no tiene BAGO portable.")
        return
    print(f"\\n  {BOLD('Sincronizando')} {CYAN(str(drive))} <-> PC\\n")
    pc_sessions = STATE_DIR / "sessions"
    pen_sessions = drive / "sessions"
    if pc_sessions.exists():
        pen_sessions.mkdir(exist_ok=True)
        for f in pc_sessions.glob("*.json"):
            dst = pen_sessions / f.name
            if not dst.exists() or f.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(f, dst)
                print(f"  {GREEN('->')} Sesion {f.name} -> pen")
    if pen_sessions.exists():
        for f in pen_sessions.glob("*.json"):
            dst = pc_sessions / f.name
            if not dst.exists() or f.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(f, dst)
                print(f"  {GREEN('<-')} Sesion {f.name} -> PC")
    pc_state = STATE_DIR
    pen_state = base / ".bago" / "state"
    if pc_state.exists() and pen_state.exists():
        for f in pc_state.glob("*.json"):
            if f.name in ("global_state.json", "repo_context.json", "creation_studio.json"):
                dst = pen_state / f.name
                if not dst.exists() or f.stat().st_mtime > dst.stat().st_mtime:
                    shutil.copy2(f, dst)
                    print(f"  {GREEN('->')} Estado {f.name} -> pen")
    print(f"\\n  {GREEN('OK')} Sincronizacion completada.\\n")

def cmd_status(drive_str: str):
    drive = Path(drive_str.replace("/", "\\").rstrip("\\"))
    base = _portable_base(drive)
    if base is None:
        print(f"  {RED('X')} {drive} no tiene BAGO portable.")
        return
    total, free = _get_drive_size(drive)
    meta = json.loads(_portable_marker(drive).read_text(encoding="utf-8")) if _portable_marker(drive).exists() else {}
    dest = base
    sessions_dir = drive / "sessions"
    models_dir = drive / "models"
    session_count = len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0
    model_count = len(list(models_dir.iterdir())) if models_dir.exists() else 0
    print(f"\\n  {BOLD('BAGO Portable')} en {CYAN(str(drive))}")
    print(f"  Creado:     {meta.get('created', '?')}")
    print(f"  Origen:     {meta.get('source', '?')}")
    print(f"  Version:    {meta.get('version', '?')}")
    print(f"  Plataforma: {meta.get('platform', '?')}")
    print(f"  Espacio:    {free / (1024**3):.1f} GB libre / {total / (1024**3):.1f} GB total")
    print(f"  Sesiones:   {session_count}")
    print(f"  Modelos:    {model_count}")
    print(f"  Estado:     {'OK' if (dest / 'bago_core').exists() else RED('INCOMPLETO')}")
    print()

def cmd_boot(drive_str: str):
    drive = Path(drive_str.replace("/", "\\").rstrip("\\"))
    dest = _portable_base(drive)
    if dest is None:
        print(f"  {RED('X')} No se encontro lanzador en {drive}")
        return
    ps1 = dest / "bago.ps1"
    cmd = dest / "bago.cmd"
    if ps1.exists():
        print(f"  Arrancando BAGO desde {ps1}...")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), "launch"])
    elif cmd.exists():
        print(f"  Arrancando BAGO desde {cmd}...")
        subprocess.run([str(cmd), "launch"])
    else:
        print(f"  {RED('X')} No se encontro lanzador en {dest}")

def main():
    parser = argparse.ArgumentParser(description="BAGO Portable -- pen drive management")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("detect", help="Detectar pen drives BAGO")
    p_create = sub.add_parser("create", help="Crear instalacion portable en pen")
    p_create.add_argument("drive", help="Letra o path del drive (ej: E:)")
    p_create.add_argument("--models", nargs="+", default=[], help="Modelos a instalar")
    p_create.add_argument("--yes", action="store_true", help="Forzar sin confirmacion interactiva")
    p_sync = sub.add_parser("sync", help="Sincronizar memoria/sesiones")
    p_sync.add_argument("drive", help="Letra o path del drive")
    p_status = sub.add_parser("status", help="Estado del pen BAGO")
    p_status.add_argument("drive", help="Letra o path del drive")
    p_boot = sub.add_parser("boot", help="Arrancar BAGO desde el pen")
    p_boot.add_argument("drive", help="Letra o path del drive")
    args = parser.parse_args()
    if args.cmd == "detect":
        cmd_detect()
    elif args.cmd == "create":
        cmd_create(args.drive, args.models, yes=args.yes)
    elif args.cmd == "sync":
        cmd_sync(args.drive)
    elif args.cmd == "status":
        cmd_status(args.drive)
    elif args.cmd == "boot":
        cmd_boot(args.drive)
    else:
        cmd_detect()
    return 0

if __name__ == "__main__":
    sys.exit(main())
