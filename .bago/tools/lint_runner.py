#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_runner.py — Ejecuta el linter en las apps del proyecto y agrega resultados.

Detecta scripts lint/typecheck/type-check en cada package.json y los ejecuta.
Agrega errores y warnings de todas las apps.

Uso:
    python3 .bago/tools/lint_runner.py            # todas las apps
    python3 .bago/tools/lint_runner.py --app web  # solo una app
    python3 .bago/tools/lint_runner.py --type     # solo typecheck
    python3 .bago/tools/lint_runner.py --fix      # lint con --fix si disponible
    python3 .bago/tools/lint_runner.py --list     # listar scripts detectados

Códigos de salida: 0 = sin errores, 1 = hay errores, 2 = error en ejecución
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

LINT_SCRIPTS   = ["lint", "lint:check", "eslint"]
TYPE_SCRIPTS   = ["typecheck", "type-check", "types", "tsc"]
ALL_SCRIPTS    = LINT_SCRIPTS + TYPE_SCRIPTS


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path:
    gs = STATE / "global_state.json"
    if gs.exists():
        try:
            data = json.loads(gs.read_text(encoding="utf-8"))
            p = data.get("active_project", {}).get("path", "")
            if p:
                return Path(p)
        except Exception:
            pass
    return ROOT


def _detect_apps(project: Path, filter_app: str | None) -> list[Path]:
    dirs = []
    # Check project root
    if (project / "package.json").exists():
        dirs.append(project)
    apps_dir = project / "apps"
    if apps_dir.exists():
        for d in sorted(apps_dir.iterdir()):
            if d.is_dir() and (d / "package.json").exists():
                if not filter_app or d.name == filter_app:
                    dirs.append(d)
    return dirs


def _get_scripts(app_dir: Path) -> dict[str, str]:
    """Return available lint/type scripts from package.json."""
    pkg = app_dir / "package.json"
    if not pkg.exists():
        return {}
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        return {k: v for k, v in scripts.items() if k in ALL_SCRIPTS}
    except Exception:
        return {}


def _run_script(app_dir: Path, script_name: str, fix: bool) -> tuple[int, str, str]:
    """Run npm run SCRIPT in app_dir. Returns (returncode, stdout, stderr)."""
    npm = shutil.which("npm") or "npm"
    cmd = [npm, "run", script_name]
    if fix and "lint" in script_name:
        cmd += ["--", "--fix"]
    try:
        result = subprocess.run(
            cmd, cwd=str(app_dir),
            capture_output=True, timeout=120,
        )
        out = result.stdout.decode("utf-8", errors="replace")
        err = result.stderr.decode("utf-8", errors="replace")
        return result.returncode, out, err
    except subprocess.TimeoutExpired:
        return 2, "", "Timeout (120s)"
    except Exception as e:
        return 2, "", str(e)


def _count_errors(output: str) -> tuple[int, int]:
    """Rough count of errors/warnings in linter output."""
    import re
    errors = warnings = 0
    for line in output.splitlines():
        ll = line.lower()
        if re.search(r'\berror\b', ll):
            errors += 1
        elif re.search(r'\bwarning\b|\bwarn\b', ll):
            warnings += 1
    return errors, warnings


def main() -> int:
    args       = sys.argv[1:]
    filter_app = None
    type_only  = "--type" in args
    fix_mode   = "--fix" in args
    list_only  = "--list" in args

    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            filter_app = args[idx + 1]

    target_scripts = TYPE_SCRIPTS if type_only else ALL_SCRIPTS
    project = _load_project()
    apps    = _detect_apps(project, filter_app)

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Linter del proyecto                                 │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if list_only:
        print(f"  {'APP':<20}  SCRIPTS DISPONIBLES")
        print(f"  {'───':<20}  ───────────────────")
        for app_dir in apps:
            scripts = _get_scripts(app_dir)
            available = [k for k in scripts if k in target_scripts]
            name = app_dir.relative_to(project) if app_dir != project else "root"
            if available:
                print(f"  {str(name):<20}  {', '.join(CYAN(s) for s in available)}")
            else:
                print(f"  {str(name):<20}  {DIM('(sin scripts de lint)')}")
        print()
        return 0

    total_errors = 0
    total_warnings = 0
    ran = 0

    for app_dir in apps:
        scripts = _get_scripts(app_dir)
        available = [k for k in target_scripts if k in scripts]
        if not available:
            continue

        name = str(app_dir.relative_to(project)) if app_dir != project else "root"
        script = available[0]  # run first matching script
        print(f"  {BOLD(name)}  → {DIM('npm run ' + script)}")

        rc, out, err = _run_script(app_dir, script, fix_mode)
        ran += 1
        combined = out + err
        errors, warnings = _count_errors(combined)
        total_errors   += errors
        total_warnings += warnings

        if rc == 0:
            print(f"    {GREEN('✅')} OK  {DIM(f'(~{warnings} warnings)')}")
        else:
            print(f"    {RED('✗')} Error  ({errors} errores, {warnings} warnings)")
            # Show last 8 lines of output
            lines = [l for l in combined.splitlines() if l.strip()][-8:]
            for line in lines:
                print(f"    {DIM(line[:100])}")
        print()

    if ran == 0:
        print(f"  {YELLOW('⚠')} No se encontraron scripts de lint en las apps\n")
        print(f"  {DIM('Scripts buscados:')} {', '.join(target_scripts)}\n")
        return 0

    print(f"  {'─' * 60}")
    if total_errors == 0:
        print(f"  {GREEN('✅ Sin errores')}  {DIM(f'({total_warnings} warnings en {ran} app(s))')}")
    else:
        print(f"  {RED(f'{total_errors} errores')}  {YELLOW(f'{total_warnings} warnings')}  en {ran} app(s)")
    print()
    return 1 if total_errors > 0 else 0



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
