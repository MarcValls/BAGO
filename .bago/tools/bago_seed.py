#!/usr/bin/env python3
"""
bago_seed.py — BAGO Seed: crea la huella mínima de BAGO en un proyecto externo.

`bago seed` es el comando más rápido para plantar BAGO en cualquier proyecto.
No copia todas las herramientas — sólo crea la estructura mínima:

  proyecto/
  ├── .bago/
  │   ├── pack.json         ← metadata: nombre, versión, padre_path
  │   └── state/            ← sessions, bago.db
  └── bago.cmd / bago       ← launcher local (delega al PADRE para commands de framework)

Uso:
  bago seed                          → siembra en directorio actual
  bago seed <ruta>                   → siembra en ruta especificada
  bago seed <ruta> --name MiProyecto → nombre personalizado
  bago seed <ruta> --dry-run         → muestra qué haría sin ejecutar
  bago seed --list                   → lista siembras registradas (alias de bago siembra list)
  bago seed --status                 → estado de todas las siembras
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Rutas del PADRE ────────────────────────────────────────────────────────────
_SEED_PATH = Path(__file__).resolve()
_TOOLS_DIR = _SEED_PATH.parent
_BAGO_ROOT  = _TOOLS_DIR.parent           # .bago/
_PADRE_PATH = _BAGO_ROOT.parent           # repo raíz del PADRE
_STATE_DIR  = _BAGO_ROOT / "state"
_SIEMBRAS_JSON = _STATE_DIR / "siembras.json"
_PACK_JSON     = _PADRE_PATH / ".bago" / "pack.json"

_PARENT_PACK = _BAGO_ROOT.parent / ".bago" / "pack.json"
# Actually pack.json is at bago_root/pack.json (one level above .bago)
_PARENT_PACK2 = _PADRE_PATH / "pack.json"

def _padre_version() -> str:
    for candidate in [_PARENT_PACK2, _PACK_JSON, _PARENT_PACK]:
        try:
            if candidate.exists():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data.get("version") or data.get("bago_version") or "3.4.0b1"
        except Exception:
            pass
    return "3.4.0b1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Plantilla pack.json ────────────────────────────────────────────────────────

def _make_pack_json(name: str, project_path: Path) -> dict:
    return {
        "_meta": (
            "pack.json — huella mínima BAGO (siembra). "
            "BAGO_PADRE_PATH apunta al framework padre completo."
        ),
        "name": name,
        "tipo": "siembra_seed",
        "bago_version": _padre_version(),
        "seeded_at": _now_iso(),
        "padre_path": str(_PADRE_PATH),
        "project_path": str(project_path.resolve()),
        "tools": "delegated_to_padre",
        "state": {
            "sessions_dir": str(project_path / ".bago" / "state" / "sessions"),
            "db": str(project_path / ".bago" / "state" / "bago.db"),
        },
    }


# ── Launcher template (delegating bago script) ────────────────────────────────

_LAUNCHER_PY = '''\
#!/usr/bin/env python3
"""bago — launcher de siembra {name}.
Delega al PADRE para todos los comandos del framework.
El PADRE está configurado en .bago/pack.json → padre_path.
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PACK = _HERE / ".bago" / "pack.json"

def _padre() -> Path:
    if _PACK.exists():
        p = json.loads(_PACK.read_text(encoding="utf-8")).get("padre_path", "")
        if p:
            return Path(p) / "bago"
    env_p = os.environ.get("BAGO_PADRE_PATH", "")
    if env_p:
        return Path(env_p) / "bago"
    raise FileNotFoundError(
        "PADRE no encontrado. Configura padre_path en .bago/pack.json "
        "o la variable BAGO_PADRE_PATH."
    )

def main() -> None:
    padre = _padre()
    env = {{**os.environ, "BAGO_SIEMBRA_PATH": str(_HERE), "BAGO_PADRE_PATH": str(padre.parent)}}
    result = subprocess.run([sys.executable, str(padre)] + sys.argv[1:], env=env)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
'''

_LAUNCHER_CMD = '''\
@echo off
python "%~dp0bago" %*
'''


# ── Registro en siembras.json ─────────────────────────────────────────────────

def _register_siembra(name: str, project_path: Path) -> None:
    siembras = {"_meta": "Siembras registradas en el PADRE.", "siembras": []}
    if _SIEMBRAS_JSON.exists():
        try:
            siembras = json.loads(_SIEMBRAS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Remove stale entry for same path if any
    siembras["siembras"] = [
        s for s in siembras.get("siembras", [])
        if Path(s.get("path", "")).resolve() != project_path.resolve()
    ]
    siembras["siembras"].append({
        "name": name,
        "path": str(project_path.resolve()),
        "tipo": "siembra_seed",
        "seeded_at": _now_iso(),
        "seeded_from": _padre_version(),
        "last_sync": _now_iso(),
        "estado": "activa",
    })
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _SIEMBRAS_JSON.write_text(
        json.dumps(siembras, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Core seed logic ──────────────────────────────────────────────────────────

def seed_project(project_path: Path, name: str, dry_run: bool = False) -> int:
    bago_dir   = project_path / ".bago"
    state_dir  = bago_dir / "state"
    sessions_dir = state_dir / "sessions"
    pack_file  = bago_dir / "pack.json"
    launcher   = project_path / "bago"
    launcher_cmd = project_path / "bago.cmd"

    print(f"\n🌱 BAGO Seed → {project_path.resolve()}")
    print(f"   Nombre:      {name}")
    print(f"   PADRE path:  {_PADRE_PATH}")
    print(f"   Versión:     {_padre_version()}")
    if dry_run:
        print("\n[DRY RUN] Lo que se crearía:\n")

    items = [
        ("dir", bago_dir),
        ("dir", state_dir),
        ("dir", sessions_dir),
        ("file", pack_file, json.dumps(_make_pack_json(name, project_path), indent=2, ensure_ascii=False)),
        ("file", launcher, _LAUNCHER_PY.format(name=name)),
        ("file", launcher_cmd, _LAUNCHER_CMD),
    ]

    for item in items:
        kind = item[0]
        target = item[1]
        if dry_run:
            icon = "📁" if kind == "dir" else "📄"
            status = "EXISTS" if target.exists() else "CREATE"
            print(f"  {icon} [{status}] {target.relative_to(project_path) if target.is_relative_to(project_path) else target}")
            continue
        if kind == "dir":
            target.mkdir(parents=True, exist_ok=True)
        else:
            content = item[2]
            if not target.exists():
                target.write_text(content, encoding="utf-8")
                if target.name == "bago" and platform.system() != "Windows":
                    target.chmod(target.stat().st_mode | 0o111)
                print(f"  ✅ Creado: {target.name}")
            else:
                print(f"  ⏩ Ya existe: {target.name}")

    if not dry_run:
        _register_siembra(name, project_path)
        print(f"\n✅ Siembra registrada en {_SIEMBRAS_JSON.name}")
        print(f"\n💡 Siguiente paso:")
        print(f"   cd {project_path}")
        print(f"   python bago health\n")
    else:
        print("\n[DRY RUN] Nada creado. Elimina --dry-run para ejecutar.\n")

    return 0


# ── list / status helpers ────────────────────────────────────────────────────

def _cmd_list() -> int:
    if not _SIEMBRAS_JSON.exists():
        print("No hay siembras registradas.")
        return 0
    data = json.loads(_SIEMBRAS_JSON.read_text(encoding="utf-8"))
    siembras = data.get("siembras", [])
    print(f"\n🌱 {len(siembras)} siembra(s) registrada(s):\n")
    for s in siembras:
        path = Path(s.get("path", ""))
        exists = path.exists()
        icon = "✅" if exists and s.get("estado") == "activa" else "⚠️" if not exists else "📦"
        print(f"  {icon} {s.get('name', '?')}")
        print(f"     path:   {s.get('path', '?')}")
        print(f"     tipo:   {s.get('tipo', '?')} | estado: {s.get('estado', '?')}")
        print(f"     seeded: {s.get('seeded_at', '?')} | sync: {s.get('last_sync', '?')}")
        print()
    return 0


def _cmd_status() -> int:
    if not _SIEMBRAS_JSON.exists():
        print("No hay siembras registradas.")
        return 0
    data = json.loads(_SIEMBRAS_JSON.read_text(encoding="utf-8"))
    siembras = data.get("siembras", [])
    activas = sum(1 for s in siembras if s.get("estado") == "activa")
    archivadas = len(siembras) - activas
    print(f"\n🌱 BAGO Siembras — Status")
    print(f"   Total:     {len(siembras)}")
    print(f"   Activas:   {activas}")
    print(f"   Archivadas:{archivadas}")
    print()
    for s in siembras:
        path = Path(s.get("path", ""))
        pack_ok = (path / ".bago" / "pack.json").exists()
        icon = "✅" if pack_ok else "❌"
        print(f"  {icon} {s.get('name', '?'):<25} {s.get('estado', '?'):<10} {s.get('path', '?')}")
    print()
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="bago seed",
        description="BAGO Seed — Planta la huella mínima de BAGO en un proyecto externo.",
        epilog="Diseño: .bago/core/architecture/PADRE_SIEMBRA.md",
    )
    p.add_argument("path", nargs="?", default=".",
                   help="Ruta del proyecto a sembrar (default: directorio actual)")
    p.add_argument("--name", "-n", default="",
                   help="Nombre del proyecto (default: nombre del directorio)")
    p.add_argument("--dry-run", action="store_true",
                   help="Muestra qué haría sin ejecutar nada")
    p.add_argument("--list", action="store_true",
                   help="Lista todas las siembras registradas")
    p.add_argument("--status", action="store_true",
                   help="Estado resumido de todas las siembras")

    args = p.parse_args(argv)

    if args.list:
        return _cmd_list()
    if args.status:
        return _cmd_status()

    project_path = Path(args.path).resolve()
    if not project_path.exists():
        print(f"❌ La ruta no existe: {project_path}", file=sys.stderr)
        return 1

    name = args.name or project_path.name
    return seed_project(project_path, name, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
