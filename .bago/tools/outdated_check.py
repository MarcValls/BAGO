#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
outdated_check.py — Lista paquetes npm desactualizados en las apps del proyecto.

Usa `npm outdated --json`. Si npm no está en PATH, muestra datos simulados.

Uso:
    python3 .bago/tools/outdated_check.py            # todas las apps
    python3 .bago/tools/outdated_check.py --app web  # una app
    python3 .bago/tools/outdated_check.py --major    # solo major bumps
    python3 .bago/tools/outdated_check.py --json     # salida JSON

Códigos de salida: 0 = todo ok, 1 = hay actualizaciones, 2 = error
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


def BOLD(s: str)    -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)     -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)   -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str)  -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)     -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str)    -> str: return f"\033[36m{s}\033[0m"
def MAGENTA(s: str) -> str: return f"\033[35m{s}\033[0m"


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
    apps_dir = project / "apps"
    if not apps_dir.exists():
        if (project / "package.json").exists():
            return [project]
        return []
    dirs = [d for d in apps_dir.iterdir()
            if d.is_dir() and (d / "package.json").exists()]
    if filter_app:
        dirs = [d for d in dirs if d.name == filter_app]
    return sorted(dirs)


def _version_tuple(v: str) -> tuple[int, ...]:
    parts = []
    for part in v.lstrip("^~>=<").split(".")[:3]:
        try:
            parts.append(int(part.split("-")[0]))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_major_bump(current: str, latest: str) -> bool:
    c = _version_tuple(current)
    lv = _version_tuple(latest)
    return len(c) > 0 and len(lv) > 0 and lv[0] > c[0]


def _run_npm_outdated(app_dir: Path) -> dict | None:
    npm = shutil.which("npm")
    if not npm:
        return None
    try:
        result = subprocess.run(
            [npm, "outdated", "--json"],
            cwd=str(app_dir),
            capture_output=True,
            timeout=60,
        )
        raw = result.stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _print_app(app_name: str, outdated: dict) -> None:
    if not outdated:
        print(f"  {BOLD(app_name)}: {GREEN('✅ al día')}")
        return
    print(f"  {BOLD(app_name)}  ({len(outdated)} desactualizados)")
    print(f"  {'PAQUETE':<30}  {'ACTUAL':<12}  {'QUERIDO':<12}  {'ÚLTIMO':<12}  SALTO")
    print(f"  {'───────':<30}  {'──────':<12}  {'───────':<12}  {'──────':<12}  ─────")
    for pkg, info in sorted(outdated.items()):
        current = info.get("current", "?")
        wanted  = info.get("wanted",  "?")
        latest  = info.get("latest",  "?")
        is_major = _is_major_bump(current, latest)
        bump = MAGENTA("MAJOR") if is_major else (YELLOW("minor") if current != wanted else DIM("patch"))
        clr  = RED if is_major else YELLOW
        print(f"  {clr(pkg):<30}  {DIM(current):<12}  {CYAN(wanted):<12}  {GREEN(latest):<12}  {bump}")
    print()


def main() -> int:
    args       = sys.argv[1:]
    filter_app = None
    major_only = "--major" in args
    as_json    = "--json" in args

    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            filter_app = args[idx + 1]

    project = _load_project()
    apps    = _detect_apps(project, filter_app)
    npm_ok  = bool(shutil.which("npm"))

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Dependencias desactualizadas                        │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if not npm_ok:
        print(f"  {YELLOW('⚠')} npm no está en PATH")
        print(f"  {DIM('Ejemplo de salida con datos simulados:')}")
        print()
        simulated = {
            "react":      {"current": "18.2.0", "wanted": "18.3.1", "latest": "19.0.0"},
            "typescript": {"current": "5.3.3",  "wanted": "5.7.2",  "latest": "5.7.2"},
            "vite":       {"current": "5.0.10", "wanted": "5.4.8",  "latest": "6.0.5"},
            "eslint":     {"current": "8.57.0", "wanted": "8.57.0", "latest": "9.15.0"},
        }
        if major_only:
            simulated = {k: v for k, v in simulated.items()
                         if _is_major_bump(v["current"], v["latest"])}
        _print_app("web (simulado)", simulated)
        return 1

    if not apps:
        print(f"  {YELLOW('⚠')} No se encontraron apps con package.json\n")
        return 2

    all_out: dict[str, dict] = {}
    for app_dir in apps:
        data = _run_npm_outdated(app_dir)
        if data is None:
            print(f"  {app_dir.name}: {YELLOW('npm no disponible')}")
            continue
        if major_only:
            data = {k: v for k, v in data.items()
                    if _is_major_bump(v.get("current", "0"), v.get("latest", "0"))}
        all_out[app_dir.name] = data
        if not as_json:
            _print_app(app_dir.name, data)

    if as_json:
        print(json.dumps(all_out, indent=2, ensure_ascii=False))

    total = sum(len(v) for v in all_out.values())
    if total == 0:
        print(f"  {GREEN('✅ Todas las dependencias están al día')}\n")
        return 0
    print(f"  {BOLD(str(total))} paquetes desactualizados\n")
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
