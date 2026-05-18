#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_hooks.py — Instala los git hooks de BAGO Supervision Layer.

Copia .bago/supervision/hooks/pre-commit.sh → .git/hooks/pre-commit
y lo marca como ejecutable.

Uso:
    python .bago/supervision/install_hooks.py [--uninstall] [--dry-run]
"""
from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

REPO_ROOT   = Path(__file__).resolve().parent.parent.parent
HOOKS_SRC   = Path(__file__).resolve().parent / "hooks"
GIT_HOOKS   = REPO_ROOT / ".git" / "hooks"


def install(dry_run: bool = False) -> int:
    if not GIT_HOOKS.exists():
        print(f"❌ No se encontró .git/hooks en {REPO_ROOT}")
        print("   ¿Estás en la raíz del repositorio?")
        return 1

    installed = 0
    for src in HOOKS_SRC.glob("*.sh"):
        hook_name = src.stem  # pre-commit.sh → pre-commit
        dst = GIT_HOOKS / hook_name

        if dst.exists():
            # Verificar si ya es nuestro hook
            existing = dst.read_text(encoding="utf-8", errors="replace")
            if "BAGO" in existing and not dry_run:
                print(f"  ✔  {hook_name}: ya instalado (BAGO hook)")
                continue
            elif "BAGO" not in existing:
                # Hook de otro sistema — hacer backup
                backup = dst.with_suffix(".backup")
                if not dry_run:
                    shutil.copy2(dst, backup)
                print(f"  💾 {hook_name}: backup guardado en {backup.name}")

        if dry_run:
            print(f"  [DRY-RUN] instalaría {hook_name} desde {src.name}")
            continue

        shutil.copy2(src, dst)
        # Marcar como ejecutable (chmod +x)
        current_mode = dst.stat().st_mode
        dst.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  ✅ {hook_name}: instalado en .git/hooks/{hook_name}")
        installed += 1

    if not dry_run and installed == 0:
        print("  ✔  Todos los hooks ya estaban instalados.")
    return 0


def uninstall(dry_run: bool = False) -> int:
    removed = 0
    for src in HOOKS_SRC.glob("*.sh"):
        hook_name = src.stem
        dst = GIT_HOOKS / hook_name
        if not dst.exists():
            continue
        content = dst.read_text(encoding="utf-8", errors="replace")
        if "BAGO" not in content:
            print(f"  ⚠️  {hook_name}: no es un BAGO hook, dejando intacto")
            continue
        if dry_run:
            print(f"  [DRY-RUN] eliminaría {hook_name}")
            continue
        # Restaurar backup si existe
        backup = dst.with_suffix(".backup")
        if backup.exists():
            shutil.move(str(backup), dst)
            print(f"  ↩️  {hook_name}: restaurado desde backup")
        else:
            dst.unlink()
            print(f"  🗑  {hook_name}: eliminado")
        removed += 1
    return 0


def main() -> int:
    dry_run   = "--dry-run" in sys.argv
    uninstall_mode = "--uninstall" in sys.argv

    print("🔧 BAGO Supervision — git hooks installer")
    if uninstall_mode:
        return uninstall(dry_run=dry_run)
    return install(dry_run=dry_run)


if __name__ == "__main__":
    sys.exit(main())
