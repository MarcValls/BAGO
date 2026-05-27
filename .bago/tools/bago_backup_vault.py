#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bago_backup_vault.py — Backups trifásicos: engine, engine+memory, memory-only.

Directorios:
  .bago/backups/engine/         → instalación limpia, rotación con --max
  .bago/backups/engine_memory/  → engine + memoria fusionada, rotación con --max
  .bago/backups/memory/         → solo memoria fusionada incremental (1 archivo)

Uso:
  python3 bago_backup_vault.py create --type engine [--max 5]
  python3 bago_backup_vault.py create --type engine-memory [--max 5]
  python3 bago_backup_vault.py create --type memory
  python3 bago_backup_vault.py list
  python3 bago_backup_vault.py restore --type engine --index 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
BAGO_ROOT  = ROOT / ".bago"
STATE      = BAGO_ROOT / "state"
TOOLS_DIR  = BAGO_ROOT / "tools"
KNOWLEDGE  = BAGO_ROOT / "knowledge"
BACKUPS    = BAGO_ROOT / "backups"

USER_HOME  = Path.home()
CODEX_MEM  = USER_HOME / ".codex" / "memories"

# Directorios de destino
ENGINE_DIR        = BACKUPS / "engine"
ENGINE_MEMORY_DIR = BACKUPS / "engine_memory"
MEMORY_DIR        = BACKUPS / "memory"

# ── Archivos que forman el ENGINE limpio ─────────────────────────────────────
ENGINE_PATHS: list[Path] = [
    ROOT / "bago_core",
    ROOT / "docs",
    BAGO_ROOT / "tools",
    BAGO_ROOT / "knowledge",
    ROOT / "bago",
    ROOT / "bago.cmd",
    ROOT / "bago.ps1",
    ROOT / "bago.ico",
    ROOT / "runtime_contract.json",
    ROOT / "CHANGELOG.md",
    ROOT / "INSTALL.md",
    ROOT / "LICENSE",
    ROOT / "README.md",
    ROOT / "QUICKSTART.md",
    ROOT / "install.ps1",
    ROOT / "smoke-test.ps1",
    ROOT / "pyproject.toml",
]

# Archivos/directorios de memoria
MEMORY_PATHS: list[Path] = [
    STATE,
]
if CODEX_MEM.exists():
    MEMORY_PATHS.append(CODEX_MEM)


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    for d in (ENGINE_DIR, ENGINE_MEMORY_DIR, MEMORY_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _add_to_zip(zf: zipfile.ZipFile, src: Path, arc_prefix: str = "") -> None:
    """Añade un archivo o directorio al ZIP."""
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_file():
                # Skip __pycache__, node_modules, .git
                if "__pycache__" in f.parts or ".git" in f.parts or "node_modules" in f.parts:
                    continue
                arcname = f"{arc_prefix}/{f.relative_to(src)}" if arc_prefix else str(f.relative_to(ROOT))
                zf.write(f, arcname)
    elif src.is_file():
        arcname = f"{arc_prefix}/{src.name}" if arc_prefix else str(src.relative_to(ROOT))
        zf.write(src, arcname)


def _list_backups(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)


def _rotate(directory: Path, max_backups: int) -> None:
    """Elimina los backups más antiguos si supera el máximo."""
    backups = _list_backups(directory)
    while len(backups) > max_backups:
        old = backups.pop()
        try:
            old.unlink()
            print(f"    🗑  Eliminado backup antiguo: {old.name}")
        except Exception as exc:
            print(f"    ⚠  No se pudo eliminar {old.name}: {exc}")


def _merge_json(old_data, new_data):
    """Fusiona dos estructuras JSON."""
    if isinstance(old_data, list) and isinstance(new_data, list):
        seen = set()
        merged = []
        for item in old_data + new_data:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                merged.append(item)
        return merged
    if isinstance(old_data, dict) and isinstance(new_data, dict):
        merged = dict(old_data)
        for k, v in new_data.items():
            if k in merged and isinstance(merged[k], (dict, list)) and isinstance(v, (dict, list)):
                merged[k] = _merge_json(merged[k], v)
            else:
                merged[k] = v
        return merged
    return new_data


def _is_jsonl(path: Path) -> bool:
    if path.suffix == ".jsonl":
        return True
    return False


def _merge_files(old_path: Path, new_path: Path, out_path: Path) -> None:
    """Fusiona dos archivos y escribe el resultado en out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # SQLite: no fusionable, copiar el más reciente
    if new_path.suffix == ".db":
        shutil.copy2(new_path, out_path)
        return

    # JSONL
    if _is_jsonl(new_path):
        lines_old = set()
        if old_path.exists():
            try:
                with open(old_path, "r", encoding="utf-8", errors="replace") as f:
                    lines_old = {ln.strip() for ln in f if ln.strip()}
            except Exception:
                pass
        with open(out_path, "w", encoding="utf-8") as fout:
            if old_path.exists():
                with open(old_path, "r", encoding="utf-8", errors="replace") as f:
                    for ln in f:
                        if ln.strip():
                            fout.write(ln)
            with open(new_path, "r", encoding="utf-8", errors="replace") as f:
                for ln in f:
                    stripped = ln.strip()
                    if stripped and stripped not in lines_old:
                        fout.write(ln)
        return

    # JSON
    if new_path.suffix == ".json":
        try:
            with open(new_path, "r", encoding="utf-8", errors="replace") as f:
                new_data = json.load(f)
            if old_path.exists():
                with open(old_path, "r", encoding="utf-8", errors="replace") as f:
                    old_data = json.load(f)
                merged = _merge_json(old_data, new_data)
            else:
                merged = new_data
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            return
        except Exception:
            pass  # fallback a copia

    # Markdown / texto
    if new_path.suffix == ".md":
        with open(out_path, "w", encoding="utf-8") as fout:
            if old_path.exists():
                with open(old_path, "r", encoding="utf-8", errors="replace") as f:
                    fout.write(f.read())
                fout.write(f"\n\n---\n\n# Merge {datetime.now().isoformat()}\n\n")
            with open(new_path, "r", encoding="utf-8", errors="replace") as f:
                fout.write(f.read())
        return

    # Default: copiar el más reciente
    shutil.copy2(new_path, out_path)


def _backup_engine(max_backups: int) -> Path:
    _ensure_dirs()
    fname = f"bago_engine_{_ts()}.zip"
    out = ENGINE_DIR / fname

    print(f"\n  🗜  Engine backup: {fname}")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in ENGINE_PATHS:
            if src.exists():
                _add_to_zip(zf, src)
                print(f"    ✔ {src.name}")

    size_kb = out.stat().st_size // 1024
    print(f"  ✅ Engine backup creado ({size_kb} KB)")
    _rotate(ENGINE_DIR, max_backups)
    return out


def _backup_memory() -> Path:
    """Crea un backup fusionado de la memoria. Solo mantiene el más reciente."""
    _ensure_dirs()

    # Buscar backup anterior de memoria
    old_backups = _list_backups(MEMORY_DIR)
    old_backup = old_backups[0] if old_backups else None

    with tempfile.TemporaryDirectory(prefix="bago_mem_") as tmpdir:
        tmp = Path(tmpdir)
        old_extracted = tmp / "old"
        new_extracted = tmp / "new"
        merged = tmp / "merged"
        merged.mkdir()

        # Extraer backup anterior
        if old_backup:
            old_extracted.mkdir()
            with zipfile.ZipFile(old_backup, "r") as zf:
                zf.extractall(old_extracted)

        # Copiar memoria actual
        new_extracted.mkdir()
        for src in MEMORY_PATHS:
            if src.exists():
                dst = new_extracted / src.name
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

        # Fusionar: recorrer todos los archivos de old y new
        all_files: set[Path] = set()
        if old_extracted.exists():
            for f in old_extracted.rglob("*"):
                if f.is_file():
                    all_files.add(f.relative_to(old_extracted))
        for f in new_extracted.rglob("*"):
            if f.is_file():
                all_files.add(f.relative_to(new_extracted))

        print(f"\n  🧠  Memoria: fusionando {len(all_files)} archivos...")

        for rel in all_files:
            old_file = old_extracted / rel if old_extracted.exists() else None
            new_file = new_extracted / rel
            out_file = merged / rel

            if new_file.exists() and old_file and old_file.exists():
                _merge_files(old_file, new_file, out_file)
            elif new_file.exists():
                out_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(new_file, out_file)
            elif old_file and old_file.exists():
                out_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_file, out_file)

        # Empaquetar
        fname = f"bago_memory_merged_{_ts()}.zip"
        out = MEMORY_DIR / fname
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in merged.rglob("*"):
                if f.is_file():
                    zf.write(f, str(f.relative_to(merged)))

        # Eliminar backup anterior
        if old_backup:
            try:
                old_backup.unlink()
                print(f"    🗑  Backup anterior eliminado: {old_backup.name}")
            except Exception as exc:
                print(f"    ⚠  No se pudo eliminar anterior: {exc}")

    size_kb = out.stat().st_size // 1024
    print(f"  ✅ Memory backup fusionado ({size_kb} KB)")
    return out


def _backup_engine_memory(max_backups: int) -> Path:
    """Engine + memoria fusionada en un solo ZIP."""
    _ensure_dirs()

    # Primero fusionar memoria
    mem_backup = _backup_memory()

    fname = f"bago_engine_memory_{_ts()}.zip"
    out = ENGINE_MEMORY_DIR / fname

    print(f"\n  🗜  Engine+Memory backup: {fname}")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Engine
        for src in ENGINE_PATHS:
            if src.exists():
                _add_to_zip(zf, src)
                print(f"    ✔ engine/{src.name}")
        # Memory (desde el backup fusionado recién creado)
        with zipfile.ZipFile(mem_backup, "r") as mem_zf:
            for member in mem_zf.namelist():
                zf.writestr(f"memory/{member}", mem_zf.read(member))
        print(f"    ✔ memory/ (fusionada)")

    size_kb = out.stat().st_size // 1024
    print(f"  ✅ Engine+Memory backup creado ({size_kb} KB)")
    _rotate(ENGINE_MEMORY_DIR, max_backups)
    return out


def _cmd_create(btype: str, max_backups: int) -> None:
    if btype == "engine":
        _backup_engine(max_backups)
    elif btype == "memory":
        _backup_memory()
    elif btype in ("engine-memory", "engine_memory"):
        _backup_engine_memory(max_backups)
    else:
        print(f"  ❌ Tipo desconocido: {btype}")
        sys.exit(1)


def _cmd_list() -> None:
    _ensure_dirs()
    sections = [
        ("ENGINE", ENGINE_DIR),
        ("ENGINE + MEMORY", ENGINE_MEMORY_DIR),
        ("MEMORY (fusionada)", MEMORY_DIR),
    ]
    for title, directory in sections:
        print(f"\n  📁 {title}")
        backups = _list_backups(directory)
        if not backups:
            print("     (vacío)")
            continue
        for i, f in enumerate(backups, 1):
            sz = f.stat().st_size // 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"     {i}. {f.name:<50} {sz:>6} KB  {mtime}")


def _cmd_restore(btype: str, index: int) -> None:
    mapping = {
        "engine": ENGINE_DIR,
        "engine-memory": ENGINE_MEMORY_DIR,
        "engine_memory": ENGINE_MEMORY_DIR,
        "memory": MEMORY_DIR,
    }
    directory = mapping.get(btype)
    if not directory:
        print(f"  ❌ Tipo desconocido: {btype}")
        sys.exit(1)

    backups = _list_backups(directory)
    if not backups:
        print("  ❌ No hay backups disponibles.")
        sys.exit(1)
    if index < 1 or index > len(backups):
        print(f"  ❌ Índice fuera de rango (1-{len(backups)})")
        sys.exit(1)

    target = backups[index - 1]
    print(f"\n  📦 Restaurando desde: {target.name}")
    print(f"  ⚠️  Esto sobrescribirá archivos existentes.")
    confirm = input("  ¿Continuar? [s/N] ").strip().lower()
    if confirm != "s":
        print("  Cancelado.")
        return

    # Para memory, restaurar en .bago/state/ y ~/.codex/memories/
    with zipfile.ZipFile(target, "r") as zf:
        if btype in ("memory",):
            for member in zf.namelist():
                if member.startswith("state/"):
                    rel = member[len("state/"):]
                    dest = STATE / rel
                elif member.startswith("memories/"):
                    rel = member[len("memories/"):]
                    dest = CODEX_MEM / rel
                else:
                    # default to state
                    dest = STATE / member
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(member))
        else:
            # Engine / engine_memory: extraer todo
            zf.extractall(ROOT)

    print(f"  ✅ Restaurado desde {target.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="BAGO Backup Vault — backupeo trifásico")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create", help="Crear backup")
    p_create.add_argument("--type", "-t", required=True,
                          choices=["engine", "engine-memory", "memory"],
                          help="Tipo de backup")
    p_create.add_argument("--max", "-m", type=int, default=5,
                          help="Máximo de backups (engine y engine-memory). Default: 5")

    sub.add_parser("list", help="Listar backups")

    p_restore = sub.add_parser("restore", help="Restaurar backup")
    p_restore.add_argument("--type", "-t", required=True,
                           choices=["engine", "engine-memory", "memory"],
                           help="Tipo de backup")
    p_restore.add_argument("--index", "-i", type=int, required=True,
                           help="Índice del backup (ver list)")

    args = parser.parse_args()

    if args.cmd == "create":
        _cmd_create(args.type, args.max)
    elif args.cmd == "list":
        _cmd_list()
    elif args.cmd == "restore":
        _cmd_restore(args.type, args.index)
    else:
        parser.print_help()

    return 0




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    sys.exit(main())