#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snapshot.py — Exporta el estado de BAGO a un archivo ZIP de respaldo.

Captura: .bago/state/, .bago/ideas_catalog.json, .bago/tools/*.py

Uso:
    python3 .bago/tools/snapshot.py              # crea snapshot ahora
    python3 .bago/tools/snapshot.py --list       # lista snapshots existentes
    python3 .bago/tools/snapshot.py --out DIR    # directorio destino
    python3 .bago/tools/snapshot.py --verify N   # verifica snapshot N (más reciente)

Snapshots guardados en: .bago/snapshots/
Formato: bago_snapshot_YYYYMMDD_HHMMSS.zip
Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT        = Path(__file__).resolve().parents[2]
BAGO_DIR    = ROOT / ".bago"
STATE_DIR   = BAGO_DIR / "state"
SNAP_DIR    = BAGO_DIR / "snapshots"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _collect_files() -> list[tuple[Path, str]]:
    """Return list of (absolute_path, archive_name) to include in snapshot."""
    files: list[tuple[Path, str]] = []

    # Everything in .bago/state/
    if STATE_DIR.exists():
        for f in sorted(STATE_DIR.rglob("*")):
            if f.is_file():
                arc_name = f.relative_to(BAGO_DIR.parent).as_posix()
                files.append((f, arc_name))

    # ideas_catalog.json
    catalog = BAGO_DIR / "ideas_catalog.json"
    if catalog.exists():
        files.append((catalog, catalog.relative_to(BAGO_DIR.parent).as_posix()))

    # All Python tools
    tools_dir = BAGO_DIR / "tools"
    if tools_dir.exists():
        for f in sorted(tools_dir.glob("*.py")):
            arc_name = f.relative_to(BAGO_DIR.parent).as_posix()
            files.append((f, arc_name))

    return files


def _create_snapshot(out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name  = f"bago_snapshot_{ts}.zip"
    dest  = out_dir / name
    files = _collect_files()

    try:
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Write manifest
            manifest = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": [arc for _, arc in files],
                "root": str(ROOT),
            }
            zf.writestr(".bago_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            for abs_path, arc_name in files:
                try:
                    zf.write(abs_path, arc_name)
                except (PermissionError, OSError):
                    pass  # Skip locked files (e.g. .db WAL)
        return dest
    except Exception as e:
        print(f"  {RED('❌')} Error al crear snapshot: {e}")
        return None


def _list_snapshots(snap_dir: Path) -> list[Path]:
    if not snap_dir.exists():
        return []
    return sorted(snap_dir.glob("bago_snapshot_*.zip"), reverse=True)


def _format_size(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f}KB"
    else:
        return f"{size/1024/1024:.1f}MB"


def main() -> int:
    args = sys.argv[1:]
    do_list  = "--list" in args or "-l" in args
    verify   = "--verify" in args

    out_dir = SNAP_DIR
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_dir = Path(args[idx + 1])

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Snapshot                                            │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if do_list:
        snaps = _list_snapshots(SNAP_DIR)
        if not snaps:
            print(f"\n  {YELLOW('⚠')} No hay snapshots en {SNAP_DIR}\n")
            return 0
        print()
        for i, snap in enumerate(snaps):
            label = GREEN("← último") if i == 0 else ""
            ts_raw = snap.stem.replace("bago_snapshot_", "")
            try:
                ts = datetime.strptime(ts_raw, "%Y%m%d_%H%M%S")
                ts_str = ts.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                ts_str = ts_raw
            size = _format_size(snap)
            print(f"  {snap.name}  {DIM(size):<8}  {DIM(ts_str)}  {label}")
        print()
        return 0

    if verify:
        snaps = _list_snapshots(SNAP_DIR)
        if not snaps:
            print(f"\n  {YELLOW('⚠')} No hay snapshots para verificar.\n")
            return 1
        snap = snaps[0]
        print(f"\n  Verificando: {snap.name}")
        with zipfile.ZipFile(snap, "r") as zf:
            bad = zf.testzip()
        if bad is None:
            print(f"  {GREEN('✅ ZIP íntegro')}")
        else:
            print(f"  {RED(f'❌ Archivo dañado: {bad}')}")
            return 1
        print()
        return 0

    # Create snapshot
    print(f"\n  Recopilando archivos...")
    files = _collect_files()
    print(f"  {len(files)} archivos a comprimir")

    dest = _create_snapshot(out_dir)
    if dest is None:
        return 1

    size = _format_size(dest)
    print(f"\n  {GREEN('✅ Snapshot creado')}")
    print(f"  Archivo: {BOLD(dest.name)}")
    print(f"  Tamaño:  {size}")
    print(f"  Ruta:    {DIM(str(dest))}")
    print()
    print(f"  Usa {CYAN('bago snapshot --list')} para ver todos los snapshots")
    print()

    return 0



def _self_test():
    assert Path(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")


# ── COMPARE SUBCOMMAND ────────────────────────────────────────────────────────

def _read_zip_names(path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(path, "r") as z:
            return set(z.namelist())
    except Exception:
        return set()


def _read_json_from_zip(path: Path, name: str) -> dict | list | None:
    try:
        with zipfile.ZipFile(path, "r") as z:
            if name in z.namelist():
                raw = z.read(name).decode("utf-8", errors="replace")
                return json.loads(raw)
    except Exception:
        return None


def _extract_ideas(data: dict | list | None) -> set[str]:
    if not data:
        return set()
    if isinstance(data, dict):
        items = data.get("implemented", [])
    elif isinstance(data, list):
        items = data
    else:
        return set()
    return {item.get("title", item.get("idea_title", "")) for item in items}


def _compare_snapshots(snap_a: Path, snap_b: Path, only: str | None, as_json: bool) -> int:
    names_a = _read_zip_names(snap_a)
    names_b = _read_zip_names(snap_b)

    ideas_json   = ".bago/state/implemented_ideas.json"
    ideas_a      = _extract_ideas(_read_json_from_zip(snap_a, ideas_json))
    ideas_b      = _extract_ideas(_read_json_from_zip(snap_b, ideas_json))
    ideas_added   = ideas_b - ideas_a
    ideas_removed = ideas_a - ideas_b

    files_added   = names_b - names_a
    files_removed = names_a - names_b
    common        = names_a & names_b

    if as_json:
        result = {
            "snapshot_a": snap_a.name,
            "snapshot_b": snap_b.name,
            "ideas_added":   sorted(ideas_added),
            "ideas_removed": sorted(ideas_removed),
            "files_added":   sorted(files_added),
            "files_removed": sorted(files_removed),
            "files_common":  len(common),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if (ideas_added or ideas_removed or files_added or files_removed) else 0

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Comparar snapshots                                  │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  A: {DIM(snap_a.name)}")
    print(f"  B: {DIM(snap_b.name)}\n")

    has_diff = False

    if only in (None, "ideas"):
        print(f"  {BOLD('Ideas implementadas:')}")
        if not ideas_added and not ideas_removed:
            print(f"    {GREEN('✅ Sin diferencias')}  ({len(ideas_a)} ideas en ambos)")
        else:
            has_diff = True
            if ideas_added:
                print(f"    {GREEN(f'+ {len(ideas_added)} nuevas en B:')}")
                for t in sorted(ideas_added):
                    print(f"      {GREEN('+')} {t}")
            if ideas_removed:
                print(f"    {RED(f'- {len(ideas_removed)} eliminadas en B:')}")
                for t in sorted(ideas_removed):
                    print(f"      {RED('-')} {t}")
        print()

    if only in (None, "tools"):
        print(f"  {BOLD('Archivos en snapshot:')}")
        if not files_added and not files_removed:
            print(f"    {GREEN('✅ Sin diferencias')}  ({len(common)} archivos en ambos)")
        else:
            has_diff = True
            tools_added   = {f for f in files_added   if f.startswith(".bago/tools/")}
            tools_removed = {f for f in files_removed if f.startswith(".bago/tools/")}
            state_added   = {f for f in files_added   if f.startswith(".bago/state/")}
            state_removed = {f for f in files_removed if f.startswith(".bago/state/")}
            if tools_added:
                print(f"    {GREEN(f'+ {len(tools_added)} herramientas nuevas:')}")
                for f in sorted(tools_added):
                    print(f"      {GREEN('+')} {Path(f).name}")
            if tools_removed:
                print(f"    {RED(f'- {len(tools_removed)} herramientas eliminadas:')}")
                for f in sorted(tools_removed):
                    print(f"      {RED('-')} {Path(f).name}")
            if state_added:
                print(f"    {CYAN(f'+ {len(state_added)} archivos de estado nuevos')}")
            if state_removed:
                print(f"    {YELLOW(f'- {len(state_removed)} archivos de estado eliminados')}")
            other = files_added - tools_added - state_added
            if other:
                print(f"    {DIM(f'+ {len(other)} otros archivos nuevos')}")
        print()

    if not has_diff:
        print(f"  {GREEN('✅ Los snapshots son idénticos')} — sin diferencias detectadas\n")
        return 0
    return 1


def cmd_compare(args: list[str]) -> int:
    as_json = "--json" in args
    only    = None
    if "--ideas" in args:
        only = "ideas"
    if "--tools" in args:
        only = "tools"

    if "--list" in args or args == ["-l"]:
        snaps = _list_snapshots(SNAP_DIR)
        if not snaps:
            print(f"  {YELLOW('⚠')} No hay snapshots.\n")
            return 0
        for s in snaps:
            print(f"  {s.name}  {DIM(str(s.stat().st_size // 1024) + 'KB')}")
        return 0

    snaps = _list_snapshots(SNAP_DIR)
    pos   = [a for a in args if not a.startswith("-")]

    if len(pos) >= 2:
        snap_a = Path(pos[0]) if Path(pos[0]).exists() else SNAP_DIR / pos[0]
        snap_b = Path(pos[1]) if Path(pos[1]).exists() else SNAP_DIR / pos[1]
    elif len(snaps) >= 2:
        snap_b = snaps[0]
        snap_a = snaps[1]
    elif len(snaps) == 1:
        print(f"\n  {YELLOW('⚠')} Solo hay un snapshot. Crea otro con: bago snapshot\n")
        return 2
    else:
        print(f"\n  {YELLOW('⚠')} No hay snapshots. Crea uno con: bago snapshot\n")
        return 2

    for snap in (snap_a, snap_b):
        if not snap.exists():
            print(f"\n  {RED('✗')} No se encuentra: {snap}\n")
            return 2

    return _compare_snapshots(snap_a, snap_b, only, as_json)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def _dispatch_main() -> int:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if args[0] == "--test":
        _self_test()
        return 0

    if args[0] == "compare":
        return cmd_compare(args[1:])

    # Default: snapshot creation/listing/verification
    return main()


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        raise SystemExit(cmd_compare(sys.argv[2:]))
    raise SystemExit(main())
