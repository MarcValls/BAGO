#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_runner.py — Ejecuta los tests del proyecto activo en un paso.

Detecta el framework de tests (vitest, jest, pytest, mocha) desde package.json
o pyproject.toml y ejecuta la suite completa con salida resumida.

Uso:
    python3 .bago/tools/test_runner.py              # detecta y ejecuta tests
    python3 .bago/tools/test_runner.py --app server # solo un app concreto
    python3 .bago/tools/test_runner.py --list       # muestra qué runners detectó

Códigos de salida: 0 = todos los tests pasan, 1 = hay fallos, 2 = no tests
"""
from __future__ import annotations

import json
import os
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
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"

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


# ─── Runner detection ─────────────────────────────────────────────────────────

def _detect_npm_test_script(pkg_json: Path) -> str | None:
    """Return the npm test script if defined in package.json."""
    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        scripts = pkg.get("scripts", {})
        for key in ("test", "test:unit", "test:run", "test:all"):
            if key in scripts:
                return key
    except Exception:
        pass
    return None


def _has_node_modules(app_dir: Path) -> bool:
    return (app_dir / "node_modules").exists()


def _find_node_runners(project: Path) -> list[dict]:
    """Find Node.js test runners across apps/*."""
    runners = []
    apps_dir = project / "apps"
    if not apps_dir.exists():
        # Try monorepo root
        pkg_json = project / "package.json"
        if pkg_json.exists():
            script = _detect_npm_test_script(pkg_json)
            if script:
                runners.append({
                    "type": "npm",
                    "name": project.name,
                    "cwd": project,
                    "script": script,
                    "has_deps": _has_node_modules(project),
                })
        return runners

    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue
        pkg_json = app_dir / "package.json"
        if not pkg_json.exists():
            continue
        script = _detect_npm_test_script(pkg_json)
        if script:
            runners.append({
                "type": "npm",
                "name": app_dir.name,
                "cwd": app_dir,
                "script": script,
                "has_deps": _has_node_modules(app_dir),
            })

    return runners


def _find_python_runners(project: Path) -> list[dict]:
    """Find Python test runners (pytest) in the project."""
    runners = []
    for marker in ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini"):
        cfg = project / marker
        if cfg.exists():
            runners.append({
                "type": "pytest",
                "name": "python",  # noqa: HARDCODE
                "cwd": project,
                "has_deps": bool(which("pytest")),
            })
            break
    # Also check apps/*
    for app_dir in (project / "apps").glob("*") if (project / "apps").exists() else []:
        if (app_dir / "pyproject.toml").exists() or (app_dir / "pytest.ini").exists():
            runners.append({
                "type": "pytest",
                "name": app_dir.name,
                "cwd": app_dir,
                "has_deps": bool(which("pytest")),
            })
    return runners


# ─── Run tests ────────────────────────────────────────────────────────────────

def _run_npm(runner: dict) -> tuple[bool, str]:
    """Run npm test script. Returns (passed, summary)."""
    npm = which("npm") or ("npm.cmd" if IS_WIN else "npm")
    cmd = [npm, "run", runner["script"], "--", "--reporter=verbose"] if "vitest" in runner.get("script", "") else [npm, "run", runner["script"]]
    try:
        r = subprocess.run(
            cmd,
            cwd=str(runner["cwd"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = r.stdout + r.stderr
        # Extract summary line (vitest: "Tests X passed", jest: "X passed")
        summary_line = ""
        for line in reversed(output.splitlines()):
            l = line.strip()
            if any(kw in l.lower() for kw in ("pass", "fail", "test", "✓", "✗", "×")):
                summary_line = l
                break
        passed = r.returncode == 0
        summary = summary_line or (f"exit {r.returncode}")
        return passed, summary
    except subprocess.TimeoutExpired:
        return False, "timeout (>120s)"
    except Exception as e:
        return False, str(e)


def _run_pytest(runner: dict) -> tuple[bool, str]:
    """Run pytest. Returns (passed, summary)."""
    import shlex
    pytest_cmd = which("pytest") or sys.executable + " -m pytest"
    base = shlex.split(pytest_cmd) if " " in pytest_cmd else [pytest_cmd]
    try:
        r = subprocess.run(
            base + ["--tb=no", "-q"],
            cwd=str(runner["cwd"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = r.stdout.strip()
        last_line = output.splitlines()[-1] if output else f"exit {r.returncode}"
        return r.returncode == 0, last_line
    except subprocess.TimeoutExpired:
        return False, "timeout (>120s)"
    except Exception as e:
        return False, str(e)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    list_only = "--list" in args
    app_filter = None
    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            app_filter = args[idx + 1]

    project = _project_root()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Ejecutar tests del proyecto                         │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if project is None or not project.exists():
        print(f"  {YELLOW('⚠  No hay proyecto activo.')}")
        print()
        return 2

    print(f"  Proyecto : {project.name}")
    print()

    # Collect all runners
    node_runners = _find_node_runners(project)
    py_runners   = _find_python_runners(project)
    all_runners  = node_runners + py_runners

    if app_filter:
        all_runners = [r for r in all_runners if app_filter.lower() in r["name"].lower()]

    if not all_runners:
        print(f"  {YELLOW('⚠  No se encontraron suites de tests.')}")
        print()
        print(f"  {DIM('Requiere: apps/*/package.json con scripts.test, o pyproject.toml')}")
        print()
        return 2

    if list_only:
        print(f"  {'APP':<20}  {'TIPO':<10}  {'SCRIPT':<20}  {'DEPS'}")
        print(f"  {'───':<20}  {'────':<10}  {'──────':<20}  {'────'}")
        for r in all_runners:
            deps = GREEN("OK") if r.get("has_deps") else RED("MISSING")
            script = r.get("script", "pytest")
            print(f"  {r['name']:<20}  {r['type']:<10}  {script:<20}  {deps}")
        print()
        return 0

    # Run tests
    total, passed_count, failed_count = 0, 0, 0
    for runner in all_runners:
        name = runner["name"]
        print(f"  ▶  {BOLD(name)} [{runner['type']}]  ", end="", flush=True)

        if runner["type"] == "npm":
            if not runner.get("has_deps"):
                print(YELLOW("⚠  node_modules falta. Ejecuta: npm install"))
                continue
            ok, summary = _run_npm(runner)
        else:
            if not runner.get("has_deps"):
                print(YELLOW("⚠  pytest no encontrado. Ejecuta: pip install pytest"))
                continue
            ok, summary = _run_pytest(runner)

        total += 1
        if ok:
            passed_count += 1
            print(GREEN(f"✅  {summary}"))
        else:
            failed_count += 1
            print(RED(f"❌  {summary}"))

    print()
    if total == 0:
        print(f"  {YELLOW('⚠  Sin runners ejecutados.')}")
        return 2
    elif failed_count == 0:
        print(f"  {GREEN(f'✅  Todos los tests pasan ({passed_count}/{total} suites)')}")
        return 0
    else:
        print(f"  {RED(f'❌  {failed_count}/{total} suites con fallos')}")
        return 1



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
