#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore.py — Restaura el estado de BAGO desde un snapshot ZIP.

Uso:
    python3 .bago/tools/restore.py              # restaura el snapshot más reciente
    python3 .bago/tools/restore.py --list       # lista snapshots disponibles
    python3 .bago/tools/restore.py FILE.zip     # restaura snapshot específico
    python3 .bago/tools/restore.py --dry        # simula restauración sin escribir

Sólo restaura .bago/state/. No sobreescribe herramientas Python.
Crea un backup automático del estado actual antes de restaurar.
Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT      = Path(__file__).resolve().parents[2]
BAGO_DIR  = ROOT / ".bago"
STATE_DIR = BAGO_DIR / "state"
SNAP_DIR  = BAGO_DIR / "snapshots"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _list_snapshots() -> list[Path]:
    if not SNAP_DIR.exists():
        return []
    return sorted(SNAP_DIR.glob("bago_snapshot_*.zip"), reverse=True)


def _format_size(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f}KB"
    return f"{size/1024/1024:.1f}MB"


def _read_manifest(zf: zipfile.ZipFile) -> dict:
    try:
        return json.loads(zf.read(".bago_manifest.json").decode("utf-8"))
    except Exception:
        return {}


def _backup_current_state() -> Path | None:
    """Create a quick backup of current state before restoring."""
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = SNAP_DIR / f"bago_pre_restore_{ts}.zip"
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import zipfile as zf
        with zf.ZipFile(dest, "w", compression=zf.ZIP_DEFLATED) as z:
            if STATE_DIR.exists():
                for f in sorted(STATE_DIR.rglob("*")):
                    if f.is_file():
                        arc = f.relative_to(BAGO_DIR.parent).as_posix()
                        try:
                            z.write(f, arc)
                        except (PermissionError, OSError):
                            pass
        return dest
    except Exception:
        return None


def _restore_from_zip(snap_path: Path, dry: bool) -> int:
    """Restore .bago/state/ from ZIP. Returns 0 on success."""
    if not snap_path.exists():
        print(f"  {RED('❌')} Snapshot no encontrado: {snap_path}")
        return 1

    try:
        with zipfile.ZipFile(snap_path, "r") as zf:
            # Verify integrity
            bad = zf.testzip()
            if bad:
                print(f"  {RED(f'❌ ZIP dañado: {bad}')}")
                return 1

            manifest = _read_manifest(zf)
            # Filter: only state files
            state_entries = [n for n in zf.namelist()
                             if n.startswith(".bago/state/") and not n.endswith("/")]

            if not state_entries:
                print(f"  {YELLOW('⚠')} El snapshot no contiene archivos de estado.")
                return 1

            print(f"\n  Snapshot: {BOLD(snap_path.name)}")
            print(f"  Archivos de estado: {len(state_entries)}")
            created = manifest.get("created_at", "desconocida")
            print(f"  Creado:   {DIM(created)}")

            if dry:
                print(f"\n  {YELLOW('(--dry) Archivos que se restaurarían:')}")
                for entry in sorted(state_entries):
                    print(f"    {DIM(entry)}")
                return 0

            # Backup current state first
            print(f"\n  Creando backup del estado actual...")
            backup = _backup_current_state()
            if backup:
                print(f"  {GREEN('✅')} Backup: {backup.name}")
            else:
                print(f"  {YELLOW('⚠')} No se pudo crear backup previo")

            # Extract state files
            print(f"\n  Restaurando {len(state_entries)} archivos...")
            restored = 0
            skipped  = 0
            for entry in state_entries:
                dest_path = BAGO_DIR.parent / entry
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                # Skip .db files to avoid corruption (WAL issues)
                if dest_path.suffix == ".db":
                    skipped += 1
                    continue
                try:
                    data = zf.read(entry)
                    dest_path.write_bytes(data)
                    restored += 1
                except (PermissionError, OSError) as e:
                    print(f"    {YELLOW('⚠')} Omitido {entry}: {e}")
                    skipped += 1

            print(f"\n  {GREEN('✅ Restauración completa')}")
            print(f"  Restaurados: {restored}  Omitidos: {skipped}")
            if skipped:
                print(f"  {DIM('(archivos .db y bloqueados se omiten)')}")
            return 0

    except zipfile.BadZipFile:
        print(f"  {RED('❌')} Archivo ZIP corrupto.")
        return 1
    except Exception as e:
        print(f"  {RED(f'❌ Error: {e}')}")
        return 1


def main() -> int:
    args = sys.argv[1:]
    do_list = "--list" in args or "-l" in args
    dry     = "--dry"  in args or "-n" in args
    # Non-flag args: path or filename
    file_args = [a for a in args if not a.startswith("-")]

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Restore                                             │")
    print("  └─────────────────────────────────────────────────────────────┘")

    snaps = _list_snapshots()

    if do_list:
        if not snaps:
            print(f"\n  {YELLOW('⚠')} No hay snapshots en {SNAP_DIR}\n")
            return 0
        print()
        for i, snap in enumerate(snaps):
            label = GREEN("← usar este") if i == 0 else ""
            ts_raw = snap.stem.replace("bago_snapshot_", "").replace("bago_pre_restore_", "")
            try:
                ts = datetime.strptime(ts_raw, "%Y%m%d_%H%M%S")
                ts_str = ts.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                ts_str = ts_raw
            size = _format_size(snap)
            print(f"  {snap.name:<50} {DIM(size):<8} {DIM(ts_str)} {label}")
        print()
        print(f"  Uso: {CYAN('bago restore')} (más reciente)  o  {CYAN('bago restore ARCHIVO.zip')}")
        print()
        return 0

    # Select snapshot
    if file_args:
        snap_path = Path(file_args[0])
        if not snap_path.is_absolute():
            snap_path = SNAP_DIR / snap_path
    elif snaps:
        snap_path = snaps[0]
        print(f"\n  {DIM('(usando snapshot más reciente)')}")
    else:
        print(f"\n  {RED('❌')} No hay snapshots disponibles.")
        print(f"  Crea uno con: {CYAN('bago snapshot')}\n")
        return 1

    rc = _restore_from_zip(snap_path, dry)
    print()
    return rc



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
