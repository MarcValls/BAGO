#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — Herramientas de build del proyecto BAGO.

Subcomandos:
    run   — Ejecuta npm build en las apps del proyecto (default)
    clean — Elimina node_modules/dist/build para liberar espacio
    pack  — Crea un ZIP distribuible de BAGO con SHA256

Uso:
    python3 .bago/tools/build.py [run] [app] [--list] [--dry]
    python3 .bago/tools/build.py clean [--run] [--app web] [--keep-modules]
    python3 .bago/tools/build.py pack [--clean] [--out DIR] [--dry-run]
    python3 .bago/tools/build.py --test

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path


ROOT     = Path(__file__).resolve().parents[2]
BAGO_DIR = ROOT / ".bago"
STATE    = BAGO_DIR / "state"


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


# ── Shared ────────────────────────────────────────────────────────────────────

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


# ── BUILD RUN ─────────────────────────────────────────────────────────────────

def _pkg_has_build(pkg_path: Path) -> bool:
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        return "build" in pkg.get("scripts", {})
    except Exception:
        return False


def _detect_apps(project: Path) -> list[dict]:
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


def _run_build_app(app: dict, dry: bool) -> bool:
    name, path, cmd = app["name"], app["path"], app["cmd"]
    print(f"\n  {BOLD('▶')} {CYAN(name):20} {DIM(str(path))}")
    if dry:
        print(f"    {DIM('$ ' + ' '.join(cmd))}")
        print(f"    {YELLOW('(modo --dry, no ejecutado)')}")
        return True

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, cwd=str(path), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            print(f"    {GREEN('✅ OK')}  {DIM(f'{elapsed:.1f}s')}")
            out_lines = result.stdout.strip().splitlines()
            for line in out_lines[-2:]:
                print(f"    {DIM(line)}")
            return True
        else:
            print(f"    {RED('❌ FALLO')}  {DIM(f'{elapsed:.1f}s')}")
            for line in (result.stderr or result.stdout).strip().splitlines()[-5:]:
                print(f"    {RED(line)}")
            return False
    except subprocess.TimeoutExpired:
        print(f"    {RED('❌ TIMEOUT')}  (>300s)")
        return False
    except FileNotFoundError:
        print(f"    {RED('❌')} npm no encontrado en PATH")
        return False


def cmd_run(args: list[str]) -> int:
    dry     = "--dry" in args
    do_list = "--list" in args or "-l" in args
    filters = [a for a in args if not a.startswith("-")]

    project = _load_project()
    if not project:
        print(f"\n  {RED('❌')} No hay proyecto configurado. Ejecuta: bago config\n")
        return 1

    apps = _detect_apps(project)
    if not apps:
        print(f"\n  {YELLOW('⚠')} No se encontraron apps con script 'build' en {project}\n")
        return 0

    if filters:
        apps = [a for a in apps if a["name"] in filters]
        if not apps:
            print(f"\n  {RED('❌')} App(s) no encontradas: {', '.join(filters)}")
            print(f"  Disponibles: {', '.join(a['name'] for a in _detect_apps(project))}\n")
            return 1

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print(f"  │  BAGO · Build Runner{' (DRY RUN)' if dry else '':<39}│")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Proyecto: {DIM(str(project))}")
    print(f"  Apps:     {len(apps)} detectadas")

    if do_list:
        print()
        for app in apps:
            print(f"    {BOLD(app['name']):<16}  {DIM(str(app['path']))}")
        print()
        return 0

    results = []
    total_start = time.time()
    for app in apps:
        results.append((app["name"], _run_build_app(app, dry)))

    total   = time.time() - total_start
    passed  = sum(1 for _, ok in results if ok)
    failed  = len(results) - passed

    print()
    print(f"  {'─' * 61}")
    print(f"  Resultado: {GREEN(str(passed) + ' OK')}  "
          f"{RED(str(failed) + ' FALLO') if failed else ''}  {DIM(f'({total:.1f}s total)')}")
    for name, ok in results:
        print(f"    {GREEN('✅') if ok else RED('❌')}  {name}")
    print()
    return 0 if failed == 0 else 1


# ── BUILD CLEAN ───────────────────────────────────────────────────────────────

DEFAULT_TARGETS = ["node_modules", "dist", "build", ".next", "out", "coverage", ".turbo"]


def _dir_size_fast(path: Path) -> int:
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def _fmt_size(b: int) -> str:
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.2f}GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f}MB"
    if b >= 1_024:         return f"{b/1_024:.1f}KB"
    return f"{b}B"


def cmd_clean(args: list[str]) -> int:
    do_run     = "--run" in args
    keep_mods  = "--keep-modules" in args
    filter_app = None

    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            filter_app = args[idx + 1]

    targets = list(DEFAULT_TARGETS)
    if "--targets" in args:
        idx = args.index("--targets")
        if idx + 1 < len(args):
            targets = [t.strip() for t in args[idx + 1].split(",")]

    if keep_mods and "node_modules" in targets:
        targets.remove("node_modules")

    project = _load_project() or ROOT
    scan_dirs = [project]
    apps_dir = project / "apps"
    if apps_dir.exists():
        for d in sorted(apps_dir.iterdir()):
            if d.is_dir() and (not filter_app or d.name == filter_app):
                scan_dirs.append(d)

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Limpiar artefactos de build                         │")
    print("  └─────────────────────────────────────────────────────────────┘")
    if not do_run:
        print(f"  {YELLOW('[DRY RUN]')} Usa --run para eliminar efectivamente")
    else:
        print(f"  {RED('⚠ ELIMINANDO artefactos...')}  (sin marcha atrás)")
    print(f"  Targets: {DIM(', '.join(targets))}\n")

    found: list[tuple[Path, int]] = []
    print("  Escaneando...")
    for scan_dir in scan_dirs:
        for target in targets:
            tp = scan_dir / target
            if tp.exists():
                found.append((tp, _dir_size_fast(tp)))

    if not found:
        print(f"  {GREEN('✅ No hay artefactos que limpiar')}\n")
        return 0

    total = sum(s for _, s in found)
    print(f"\n  {'DIRECTORIO':<55}  TAMAÑO")
    print(f"  {'──────────':<55}  ──────")
    for path, size in sorted(found, key=lambda x: x[1], reverse=True):
        try:
            rel = path.relative_to(project)
        except ValueError:
            rel = path
        color = RED if size > 500_000_000 else (YELLOW if size > 50_000_000 else DIM)
        print(f"  {str(rel):<55}  {color(_fmt_size(size))}")

    print()
    print(f"  Total a liberar: {BOLD(_fmt_size(total))}\n")

    if not do_run:
        print(f"  {DIM('Ejecuta con --run para eliminar estos directorios.')}\n")
        return 0

    freed = 0
    errors = 0
    for path, size in found:
        try:
            shutil.rmtree(str(path))
            freed += size
            try:
                rel = path.relative_to(project)
            except ValueError:
                rel = path
            print(f"  {GREEN('✓')} {rel}")
        except Exception as e:
            errors += 1
            print(f"  {RED('✗')} Error: {path.name}: {e}")

    print()
    print(f"  {GREEN('✅')} Liberado: {BOLD(_fmt_size(freed))}")
    if errors:
        print(f"  {YELLOW(f'{errors} error(s) al eliminar')}")
    print()
    return 0


# ── BUILD PACK ────────────────────────────────────────────────────────────────

EXCLUDE_PREFIXES: list[str] = [
    ".bago/dist", ".bago/state", ".bago/ImageStudio", ".bago/.models",
    ".bago/bin", ".bago/snapshots", ".bago/knowledge", ".git",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".Spotlight-V100",
    ".fseventsd", ".Trashes", ".TemporaryItems", ".DocumentRevisions-V100",
    "bago.egg-info", "dist", "System Volume Information",
]
EXCLUDE_SUFFIXES: list[str] = ["__pycache__", ".pyc", ".pyo", ".DS_Store", ".gitkeep"]


def _should_exclude(rel: Path) -> bool:
    rel_str = str(rel).replace("\\", "/")
    for prefix in EXCLUDE_PREFIXES:
        norm = prefix.replace("\\", "/")
        if rel_str == norm or rel_str.startswith(norm + "/"):
            return True
    for suffix in EXCLUDE_SUFFIXES:
        norm = suffix.replace("\\", "/")
        if rel_str.endswith(norm) or ("/" + norm + "/") in rel_str:
            return True
    return False


def _read_version() -> str:
    pack_json = BAGO_DIR / "pack.json"
    if pack_json.exists():
        try:
            return json.loads(pack_json.read_text())["version"]
        except Exception:
            pass
    return "unknown"


def cmd_pack(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="build pack", add_help=False)
    parser.add_argument("--clean",   action="store_true")
    parser.add_argument("--out",     default="dist")
    parser.add_argument("--dry-run", action="store_true")
    opts, _ = parser.parse_known_args(args)

    out_dir = Path(opts.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    version   = _read_version()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack_name = f"BAGO_{version}_{timestamp}"
    zip_path  = out_dir / f"{pack_name}.zip"
    sha_path  = out_dir / f"{pack_name}.sha256"

    if opts.clean and out_dir.exists() and not opts.dry_run:
        shutil.rmtree(out_dir)
        print(f"  🧹 Cleaned: {out_dir}")

    if not opts.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    dynamic_excludes: list[str] = []
    try:
        rel_out = out_dir.resolve().relative_to(ROOT)
        dynamic_excludes.append(str(rel_out))
    except ValueError:
        pass

    entries: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if _should_exclude(rel):
            continue
        rel_str = str(rel)
        if any(rel_str == ex or rel_str.startswith(ex + "/") for ex in dynamic_excludes):
            continue
        entries.append(path)

    print(f"  📦 Building {pack_name}.zip")
    print(f"     Files included: {len(entries)}")

    if opts.dry_run:
        for e in entries:
            print(f"     + {e.relative_to(ROOT)}")
        print("  ℹ️  Dry-run: no files written.")
        return 0

    skipped = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in entries:
            arcname = str(path.relative_to(ROOT))
            try:
                zf.write(path, arcname)
            except (FileNotFoundError, PermissionError) as exc:
                print(f"  ⚠  Skipped: {arcname} — {exc}", file=sys.stderr)
                skipped += 1

    if skipped:
        print(f"  ⚠  Skipped {skipped} files")

    h = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path.write_text(f"{h}  {zip_path.name}\n")

    size_mb = zip_path.stat().st_size / 1_048_576
    print(f"  ✅ {zip_path}  ({size_mb:.1f} MB)")
    print(f"  🔑 {sha_path}")
    return 0


# ── DISPATCH ──────────────────────────────────────────────────────────────────

_HELP = """
  BAGO · Build Tools

  Subcomandos:
    run    Ejecutar npm build en las apps del proyecto (default)
    clean  Eliminar node_modules / dist para liberar espacio
    pack   Crear ZIP distribuible de BAGO con SHA256

  Ejemplos:
    build run              → build todas las apps
    build run web          → solo app 'web'
    build run --dry        → mostrar sin ejecutar
    build clean            → dry-run de limpieza
    build clean --run      → eliminar efectivamente
    build pack             → crear ZIP
    build pack --dry-run   → listar archivos sin comprimir
"""


def main() -> int:
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print(_HELP)
        return 0

    if args[0] == "--test":
        _self_test()
        return 0

    sub = args[0]
    rest = args[1:]

    if sub == "run":
        return cmd_run(rest)
    elif sub == "clean":
        return cmd_clean(rest)
    elif sub == "pack":
        return cmd_pack(rest)
    else:
        # Default: treat all args as 'run' args
        return cmd_run(args)


def _self_test() -> None:
    assert ROOT.exists(), "ROOT no encontrado"
    assert BAGO_DIR.exists(), "BAGO_DIR no encontrado"
    p = _load_project()
    print(f"  ✅ build.py: ROOT={ROOT.name}, proyecto={'detectado' if p else 'ninguno'}")


if __name__ == "__main__":
    raise SystemExit(main())
