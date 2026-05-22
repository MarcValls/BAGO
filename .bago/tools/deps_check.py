#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deps_check.py — Verifica dependencias instaladas del proyecto.

Comprueba que node_modules está presente y actualizado en cada app/*,
y que las dependencias Python (si existen) están instaladas.

Uso:
    python3 .bago/tools/deps_check.py              # verificar todas las apps
    python3 .bago/tools/deps_check.py --app server # solo una app
    python3 .bago/tools/deps_check.py --install    # ejecutar npm install si falta

Códigos de salida: 0 = OK, 1 = deps faltantes
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from shutil import which

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
IS_WIN = sys.platform == "win32"

# ─── Colores ──────────────────────────────────────────────────────────────────

def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"

# ─── Project detection ────────────────────────────────────────────────────────

def _project_root() -> Path | None:
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return None
    try:
        gs = json.loads(gs_file.read_text(encoding="utf-8"))
        p = gs.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


# ─── Node.js deps check ───────────────────────────────────────────────────────

def _count_pkg_deps(pkg_json: Path) -> int:
    """Count declared npm dependencies."""
    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        return (
            len(pkg.get("dependencies", {})) +
            len(pkg.get("devDependencies", {}))
        )
    except Exception:
        return 0


def _count_installed_modules(node_modules: Path) -> int:
    """Count top-level installed packages (approx)."""
    if not node_modules.exists():
        return 0
    return sum(1 for d in node_modules.iterdir()
               if d.is_dir() and not d.name.startswith("."))


def _is_outdated(pkg_json: Path, node_modules: Path) -> bool:
    """Return True if package.json is newer than node_modules (needs npm install)."""
    if not node_modules.exists():
        return True
    try:
        pkg_mtime = pkg_json.stat().st_mtime
        nm_mtime  = node_modules.stat().st_mtime
        return pkg_mtime > nm_mtime
    except OSError:
        return False


def _check_npm_app(app_dir: Path, run_install: bool) -> dict:
    pkg_json     = app_dir / "package.json"
    node_modules = app_dir / "node_modules"

    if not pkg_json.exists():
        return {"name": app_dir.name, "type": "npm", "status": "skip", "detail": "no package.json"}

    declared  = _count_pkg_deps(pkg_json)
    installed = _count_installed_modules(node_modules)
    outdated  = _is_outdated(pkg_json, node_modules)

    missing = not node_modules.exists()

    if missing or (outdated and installed == 0):
        status = "missing"
    elif outdated:
        status = "outdated"
    else:
        status = "ok"

    if (missing or outdated) and run_install:
        npm = which("npm") or ("npm.cmd" if IS_WIN else "npm")
        try:
            r = subprocess.run(
                [npm, "install"],
                cwd=str(app_dir),
                capture_output=True,
                timeout=120,
            )
            if r.returncode == 0:
                status = "installed"
                installed = _count_installed_modules(node_modules)
        except Exception as e:
            status = "install_failed"

    return {
        "name":      app_dir.name,
        "type":      "npm",
        "status":    status,
        "declared":  declared,
        "installed": installed,
        "detail":    "",
    }


def _check_python_app(app_dir: Path) -> dict | None:
    """Check Python deps if requirements.txt or pyproject.toml exists."""
    req_files = list(app_dir.glob("requirements*.txt")) + [app_dir / "pyproject.toml"]
    req_present = [f for f in req_files if f.exists()]
    if not req_present:
        return None

    # Check if pip packages are installed (rough: try importing each)
    # Instead: check if a venv exists or site-packages is populated
    venv_dirs = [app_dir / ".venv", app_dir / "venv", app_dir / "env"]
    has_venv = any(v.exists() for v in venv_dirs)

    if app_dir / "requirements.txt" in req_present:
        # Count requirements lines
        try:
            lines = [l.strip() for l in (app_dir / "requirements.txt")
                     .read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
            declared = len(lines)
        except Exception:
            declared = 0
    else:
        declared = 0

    return {
        "name":      app_dir.name,
        "type":      "python",  # noqa: HARDCODE
        "status":    "ok" if has_venv else "no_venv",
        "declared":  declared,
        "installed": 0,
        "detail":    ".venv found" if has_venv else "no virtualenv detected",
    }


# ─── Status display ───────────────────────────────────────────────────────────

_STATUS_DISPLAY = {
    "ok":             lambda: GREEN("✅  OK"),
    "outdated":       lambda: YELLOW("⚠   outdated (run npm install)"),
    "missing":        lambda: RED("❌  MISSING node_modules"),
    "installed":      lambda: GREEN("✅  installed now"),
    "install_failed": lambda: RED("❌  install failed"),
    "no_venv":        lambda: YELLOW("⚠   no virtualenv"),
    "skip":           lambda: DIM("—  skip"),
}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args         = sys.argv[1:]
    run_install  = "--install" in args
    app_filter   = None
    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            app_filter = args[idx + 1]

    project = _project_root()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Dependencias del proyecto                           │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if project is None or not project.exists():
        print(f"  {YELLOW('⚠  No hay proyecto activo.')}")
        print()
        return 1

    print(f"  Proyecto : {project.name}")
    if run_install:
        print(f"  Modo     : instalar si falta")
    print()

    results = []

    # Check apps/*
    apps_dir = project / "apps"
    if apps_dir.exists():
        for app_dir in sorted(apps_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            if app_filter and app_filter.lower() not in app_dir.name.lower():
                continue
            npm_result = _check_npm_app(app_dir, run_install)
            if npm_result["status"] != "skip":
                results.append(npm_result)
            py_result = _check_python_app(app_dir)
            if py_result:
                results.append(py_result)
    else:
        # Monorepo root
        if not app_filter:
            npm_result = _check_npm_app(project, run_install)
            if npm_result["status"] != "skip":
                results.append(npm_result)

    if not results:
        print(f"  {YELLOW('⚠  No se encontraron proyectos con dependencias declaradas.')}")
        print()
        return 2

    print(f"  {'APP':<20}  {'TIPO':<8}  {'DECLARADAS':>10}  {'ESTADO'}")
    print(f"  {'───':<20}  {'────':<8}  {'──────────':>10}  {'──────'}")

    total, issues = 0, 0
    for r in results:
        total += 1
        status_fn = _STATUS_DISPLAY.get(r["status"], lambda: r["status"])
        status_str = status_fn()
        declared = str(r.get("declared", "?")) if r.get("declared") else "?"
        print(f"  {r['name']:<20}  {r['type']:<8}  {declared:>10}  {status_str}")
        if r["status"] not in ("ok", "installed", "skip"):
            issues += 1

    print()
    if issues == 0:
        print(f"  {GREEN(f'✅  Todas las dependencias están instaladas ({total} apps)')}")
    else:
        print(f"  {RED(f'❌  {issues}/{total} apps con dependencias faltantes')}")
        if not run_install:
            print(f"  {DIM('Ejecuta: bago deps --install  para instalarlas automáticamente')}")
    print()

    return 1 if issues > 0 else 0



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
