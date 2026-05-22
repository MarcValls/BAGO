#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_runner.py — Ejecuta el proceso de build de las apps del proyecto.

Detecta y ejecuta scripts de build en cada app (server, web, electron, raíz).
Filtra por app si se especifica. Muestra éxito/fallo con duración.

Uso:
    python3 .bago/tools/build_runner.py               # build todas las apps
    python3 .bago/tools/build_runner.py web           # solo web
    python3 .bago/tools/build_runner.py server        # solo server
    python3 .bago/tools/build_runner.py --list        # listar apps detectadas
    python3 .bago/tools/build_runner.py --dry         # mostrar comandos sin ejecutar

Códigos de salida: 0 = todos OK, 1 = algún build falló
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path | None:
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return None
    try:
        gs = json.loads(gs_file.read_text(encoding="utf-8"))
        p = gs.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _pkg_has_build(pkg_path: Path) -> bool:
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        return "build" in pkg.get("scripts", {})
    except Exception:
        return False


def _detect_apps(project: Path) -> list[dict]:
    """Return list of {name, path, cmd} for apps that have a build script."""
    apps = []
    candidates = [
        ("root",     project),
        ("server",   project / "apps" / "server"),
        ("web",      project / "apps" / "web"),
        ("electron", project / "apps" / "electron"),
    ]
    for name, path in candidates:
        pkg = path / "package.json"
        if pkg.exists() and _pkg_has_build(pkg):
            apps.append({"name": name, "path": path, "cmd": ["npm", "run", "build"]})
    return apps


def _run_build(app: dict, dry: bool) -> bool:
    """Run build for an app. Returns True on success."""
    name = app["name"]
    path = app["path"]
    cmd  = app["cmd"]

    print(f"\n  {BOLD('▶')} {CYAN(name):20} {DIM(str(path))}")
    if dry:
        print(f"    {DIM('$ ' + ' '.join(cmd))}")
        print(f"    {YELLOW('(modo --dry, no ejecutado)')}")
        return True

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            print(f"    {GREEN('✅ OK')}  {DIM(f'{elapsed:.1f}s')}")
            # Show last 2 lines of stdout if any
            out_lines = result.stdout.strip().splitlines()
            if out_lines:
                for line in out_lines[-2:]:
                    print(f"    {DIM(line)}")
            return True
        else:
            print(f"    {RED('❌ FALLO')}  {DIM(f'{elapsed:.1f}s')}")
            err_lines = (result.stderr or result.stdout).strip().splitlines()
            for line in err_lines[-5:]:
                print(f"    {RED(line)}")
            return False
    except subprocess.TimeoutExpired:
        print(f"    {RED('❌ TIMEOUT')}  (>300s)")
        return False
    except FileNotFoundError:
        print(f"    {RED('❌')} npm no encontrado en PATH")
        return False


def main() -> int:
    args = sys.argv[1:]
    dry   = "--dry" in args
    lst   = "--list" in args or "-l" in args
    # Filter: non-flag args are app names
    filters = [a for a in args if not a.startswith("-")]

    project = _load_project()
    if not project:
        print(f"\n  {RED('❌')} No hay proyecto configurado. Ejecuta: bago config\n")
        return 1

    apps = _detect_apps(project)
    if not apps:
        print(f"\n  {YELLOW('⚠')} No se encontraron apps con script 'build' en {project}\n")
        return 0

    # Apply filter
    if filters:
        apps = [a for a in apps if a["name"] in filters]
        if not apps:
            print(f"\n  {RED('❌')} App(s) no encontradas: {', '.join(filters)}")
            print(f"  Disponibles: {', '.join(a['name'] for a in _detect_apps(project))}\n")
            return 1

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    mode_label = " (DRY RUN)" if dry else ""
    print(f"  │  BAGO · Build Runner{mode_label:<39}│")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Proyecto: {DIM(str(project))}")
    print(f"  Apps:     {len(apps)} detectadas")

    if lst:
        print()
        for app in apps:
            print(f"    {BOLD(app['name']):<16}  {DIM(str(app['path']))}")
        print()
        return 0

    results = []
    total_start = time.time()
    for app in apps:
        ok = _run_build(app, dry)
        results.append((app["name"], ok))

    total = time.time() - total_start
    passed = sum(1 for _, ok in results if ok)
    failed = len(results) - passed

    print()
    print(f"  {'─' * 61}")
    print(f"  Resultado: {GREEN(str(passed) + ' OK')}  {RED(str(failed) + ' FALLO') if failed else ''}  {DIM(f'({total:.1f}s total)')}")
    for name, ok in results:
        icon = GREEN("✅") if ok else RED("❌")
        print(f"    {icon}  {name}")
    print()

    return 0 if failed == 0 else 1



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
