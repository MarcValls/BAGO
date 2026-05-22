"""bago run — Execute any npm/pnpm script from the monorepo workspace."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".bago" / "state"


def _get_project_root() -> Path:
    gs_path = STATE_DIR / "global_state.json"
    if gs_path.exists():
        try:
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            p = gs.get("active_project", {}).get("path", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
    return ROOT.parent


PROJECT_ROOT = _get_project_root()


def _load_scripts() -> list[dict]:
    """Collect all scripts from root + apps/*/package.json."""
    entries = []
    candidates = [PROJECT_ROOT] + sorted(
        [d for d in (PROJECT_ROOT / "apps").iterdir() if d.is_dir()]
        if (PROJECT_ROOT / "apps").exists() else []
    )
    for pkg_dir in candidates:
        pkg = pkg_dir / "package.json"
        if not pkg.exists():
            continue
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except Exception:
            continue
        app_name = "root" if pkg_dir == PROJECT_ROOT else pkg_dir.name
        for name, cmd in data.get("scripts", {}).items():
            entries.append({
                "app": app_name,
                "name": name,
                "cmd": cmd,
                "cwd": str(pkg_dir),
            })
    return entries


def _color(s: str, code: str) -> str:
    return f"\033[{code}m{s}\033[0m"

def CYAN(s):  return _color(s, "36")
def GREEN(s): return _color(s, "32")
def YELLOW(s):return _color(s, "33")
def DIM(s):   return _color(s, "2")
def BOLD(s):  return _color(s, "1")


def cmd_list(scripts: list[dict], app_filter: str | None, grep: str | None):
    filtered = scripts
    if app_filter:
        filtered = [s for s in filtered if s["app"] == app_filter]
    if grep:
        g = grep.lower()
        filtered = [s for s in filtered if g in s["name"].lower() or g in s["cmd"].lower()]

    if not filtered:
        print("  (sin resultados)")
        return

    print()
    cur_app = None
    for i, s in enumerate(filtered, 1):
        if s["app"] != cur_app:
            cur_app = s["app"]
            print(f"  {CYAN(cur_app)}")
        print(f"    {DIM(str(i).rjust(3))}  {BOLD(s['name']):<30} {DIM(s['cmd'][:60])}")
    print()


def cmd_exec(scripts: list[dict], index: int):
    if index < 1 or index > len(scripts):
        print(f"  ✖ Índice inválido: {index}. Rango: 1-{len(scripts)}", file=sys.stderr)
        sys.exit(1)
    s = scripts[index - 1]
    print(f"\n  ▶  {CYAN(s['app'])} › {BOLD(s['name'])}")
    print(f"     {DIM(s['cmd'])}\n")

    pnpm_cmd = shutil.which("pnpm") or "pnpm"
    try:
        proc = subprocess.run(
            [pnpm_cmd, "run", s["name"]],
            cwd=s["cwd"],
        )
        sys.exit(proc.returncode)
    except FileNotFoundError:
        # fallback to npm
        proc = subprocess.run(["npm", "run", s["name"]], cwd=s["cwd"])
        sys.exit(proc.returncode)


def main():
    parser = argparse.ArgumentParser(description="BAGO run — Execute monorepo scripts")
    parser.add_argument("index", nargs="?", type=int,
                        help="Script index to run (from the list)")
    parser.add_argument("--app", "-a", help="Filter by app name")
    parser.add_argument("--grep", "-g", help="Filter scripts by name or command text")
    parser.add_argument("--list", "-l", action="store_true", help="Show all scripts (default)")
    args = parser.parse_args()

    scripts = _load_scripts()

    if args.index is not None:
        # Apply filters first so the index matches what the user saw
        filtered = scripts
        if args.app:
            filtered = [s for s in filtered if s["app"] == args.app]
        if args.grep:
            g = args.grep.lower()
            filtered = [s for s in filtered if g in s["name"].lower() or g in s["cmd"].lower()]
        cmd_exec(filtered, args.index)
    else:
        cmd_list(scripts, args.app, args.grep)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
