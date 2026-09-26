#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from bago_core.resolver import add_piece_paths
from bago_core.workspace_paths import workspace_root

BAGO_ROOT = Path(__file__).resolve().parents[2]

def _program_files_root() -> Path:
    override = os.environ.get("BAGO_INSTALL_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve().parent
    root = os.environ.get("ProgramFiles", "").strip()
    if root:
        return Path(root)
    return Path.home() / "AppData" / "Local" / "Programs"

def _program_data_root() -> Path:
    override = os.environ.get("BAGO_DATA_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    root = os.environ.get("ProgramData", "").strip()
    if root:
        return Path(root)
    return Path.home() / "AppData" / "Local"

PROFILE_ROOTS = {
    "stable": _program_files_root() / "BAGO",
    "des": workspace_root() / "dev",
    "ign": workspace_root() / "launch",
}
PROFILE_DATA_ROOT = _program_data_root() / "BAGO"


def _normalize_profile(profile: str) -> str:
    value = profile.strip().lower()
    aliases = {
        "prod": "stable",
        "production": "stable",
        "release": "stable",
        "dev": "des",
        "development": "des",
        "integration": "ign",
        "integracion": "ign",
    }
    value = aliases.get(value, value)
    if value not in PROFILE_ROOTS:
        raise ValueError(f"Perfil desconocido: {profile}")
    return value


def _profile_install_dir(profile: str) -> Path:
    root = PROFILE_ROOTS[_normalize_profile(profile)]
    return root


def _profile_backup_root(profile: str) -> Path:
    return PROFILE_DATA_ROOT / "backups" / _normalize_profile(profile)


def _profile_user_state_dir(profile: str) -> Path:
    return PROFILE_DATA_ROOT / "user" / _normalize_profile(profile)

add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")

def cmd_install(args: argparse.Namespace) -> int:
    import subprocess

    root = BAGO_ROOT
    profile = _normalize_profile(args.profile) if getattr(args, "profile", "") else ""
    install_dir = Path(args.install_dir) if args.install_dir else (_profile_install_dir(profile) if profile else _program_files_root() / "BAGO")
    if args.source_root:
        source_root = Path(args.source_root)
    elif profile == "ign" and not args.package_zip:
        source_root = _profile_install_dir("des")
    else:
        source_root = Path(args.source_root) if args.source_root else root
    same_source_and_target = False
    try:
        same_source_and_target = source_root.resolve() == install_dir.resolve()
    except Exception:
        same_source_and_target = str(source_root).rstrip("\\/").lower() == str(install_dir).rstrip("\\/").lower()
    repair_only = bool(args.repair_only or (same_source_and_target and not args.package_zip))
    script = root / "install-v4.ps1"
    if not script.exists():
        print(f"[ERROR] No se encontro instalador local: {script}")
        return 1

    ps = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
    command = [
        ps,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    if args.source_root:
        command += ["-SourceRoot", args.source_root]
    if args.package_zip:
        command += ["-PackageZip", args.package_zip]
    if args.install_dir:
        command += ["-InstallDir", args.install_dir]
    if profile:
        command += ["-Profile", profile]
    if args.mode:
        command += ["-Mode", args.mode]
    elif repair_only:
        command += ["-Mode", "Express"]
    command.append("-ExplorerContextMenu")
    if repair_only:
        command.append("-RepairOnly")
    if args.skip_tests:
        command.append("-SkipTests")
    if args.no_path_update:
        command.append("-NoPathUpdate")

    print("BAGO local install")
    print(f"Fuente local : {source_root}")
    print(f"Perfil       : {profile or 'none'}")
    print(f"Destino      : {install_dir}")
    print(f"Modo         : {'repair' if repair_only else 'install'}")
    print("Red          : no descarga nada")
    if args.dry_run:
        print("Dry-run      : no ejecutado")
        return 0
    return subprocess.call(command)

def cmd_uninstall(args: argparse.Namespace) -> int:
    from execution_adapters.install_uninstall_lifecycle import run_authorized_uninstall

    try:
        return run_authorized_uninstall(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] No se pudo desinstalar BAGO: {exc}")
        return 1


def cmd_rollback_archive(args: argparse.Namespace) -> int:
    """Restore a named installer ZIP through the strong ExecutionGateway owner."""
    from bago_core.cli_execution import execute_cli_effect
    from execution_adapters.archive_rollback import SystemInstallArchiveRollbackEffectAdapter
    from execution_request import build_execution_request

    install_dir = str(getattr(args, "install_dir", "") or "").strip()
    if not install_dir:
        install_dir = os.environ.get("BAGO_INSTALL_DIR", "").strip() or str(_program_files_root() / "BAGO")
    backup_root = str(getattr(args, "backup_root", "") or "").strip()
    if not backup_root:
        backup_root = str(_program_data_root() / "backups")
    backup_zip = str(getattr(args, "backup_zip", "") or "").strip()
    if not backup_zip:
        candidates = sorted(Path(backup_root).glob("bago-programfiles-backup-*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            print(f"[ERROR] No se encontraron backups BAGO en {backup_root}")
            return 1
        backup_zip = str(candidates[0])
    try:
        target = SystemInstallArchiveRollbackEffectAdapter.prepare_target(
            install_dir, backup_root, backup_zip,
            restore_backed_up_state=bool(getattr(args, "restore_backed_up_state", False)),
        )
        request = build_execution_request(
            effect_id="system.install.archive.rollback",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=f"archive-rollback:{target['install_dir']}",
            source_surface="cli.install.archive-rollback",
            target=target,
            arguments={},
            scope="system",
        )
        result, _authorization = execute_cli_effect(
            request,
            confirmation_text=(
                f"Restaurar {target['backup_zip']} sobre {target['install_dir']}; "
                f"backup de seguridad: {target['safety_zip']}; "
                f"restaurar estado archivado: {str(target['restore_backed_up_state']).lower()}"
            ),
        )
    except Exception as exc:
        print(f"[ERROR] Rollback bloqueado: {exc}")
        return 1
    print(f"[OK] Runtime restaurado: {result['restored_to']}")
    print(f"[OK] Receipt: {result['receipt_id']}")
    return 0
