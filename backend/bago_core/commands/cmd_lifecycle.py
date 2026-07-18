#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bago_core.resolver import add_piece_paths
from bago_core.user_state_paths import prune_backups_root
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

def _normalize_path_entry(entry: str) -> str:
    return entry.strip().rstrip("\\").lower()

def _remove_install_from_path(install_path: str) -> str:
    removed_scopes: list[str] = []
    install_norm = _normalize_path_entry(install_path)
    current = os.environ.get("Path", "")
    entries = []
    for entry in current.split(";"):
        clean = entry.strip()
        if clean and _normalize_path_entry(clean) != install_norm:
            entries.append(clean)
    os.environ["Path"] = ";".join(entries)

    try:
        import winreg  # type: ignore
    except Exception:
        return "process"

    def _rewrite(scope_root: int) -> bool:
        try:
            with winreg.OpenKey(scope_root, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                value, reg_type = winreg.QueryValueEx(key, "Path")
                kept = []
                for entry in str(value or "").split(";"):
                    clean = entry.strip()
                    if clean and _normalize_path_entry(clean) != install_norm:
                        kept.append(clean)
                winreg.SetValueEx(key, "Path", 0, reg_type, ";".join(kept))
            return True
        except Exception:
            return False

    if _rewrite(winreg.HKEY_CURRENT_USER):
        removed_scopes.append("user")
    if _rewrite(winreg.HKEY_LOCAL_MACHINE):
        removed_scopes.append("machine")
    return "+".join(removed_scopes) if removed_scopes else "process"

def _remove_registry_tree(winreg: Any, root: Any, subkey: str) -> None:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            index = 0
            while True:
                try:
                    child = winreg.EnumKey(key, index)
                except OSError:
                    break
                _remove_registry_tree(winreg, root, f"{subkey}\\{child}")
                index += 1
    except OSError:
        return
    try:
        winreg.DeleteKey(root, subkey)
    except OSError:
        pass

def _remove_bago_explorer_context_menu() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg  # type: ignore
    except Exception:
        return False
    removed = False
    for subkey in (
        r"Software\Classes\Directory\shell\BAGO",
        r"Software\Classes\Directory\Background\shell\BAGO",
    ):
        try:
            _remove_registry_tree(winreg, winreg.HKEY_CURRENT_USER, subkey)
            removed = True
        except Exception:
            pass
    return removed

def _zip_tree(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))

def _is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def _is_under_path(path: Path, parent: str) -> bool:
    if not parent:
        return False
    try:
        path.resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False

def _needs_uninstall_elevation(install_dir: Path) -> bool:
    if os.name != "nt" or _is_windows_admin():
        return False
    protected_roots = [
        _program_files_root(),
        Path(os.environ.get("ProgramFiles(x86)", "").strip()) if os.environ.get("ProgramFiles(x86)", "").strip() else Path.home() / "AppData" / "Local" / "Programs" / "x86",
    ]
    return any(_is_under_path(install_dir, root) for root in protected_roots if root)

def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def _relaunch_uninstall_elevated(args: argparse.Namespace, install_dir: Path) -> int:
    ps = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
    cli_path = BAGO_ROOT / "bago_core" / "cli.py"
    argv = [
        str(cli_path if cli_path.exists() else (BAGO_ROOT / "bago_core" / "launcher.py")),
        "--base-path",
        str(args.base_path),
        "uninstall",
        "--install-dir",
        str(install_dir),
        "--elevated-child",
    ]
    if args.backup_root:
        argv += ["--backup-root", args.backup_root]
    if args.user_state_dir:
        argv += ["--user-state-dir", args.user_state_dir]
    if args.purge_state:
        argv.append("--purge-state")
    arg_list = "@(" + ",".join(_ps_literal(item) for item in argv) + ")"
    command = (
        "$p = Start-Process -FilePath "
        + _ps_literal(sys.executable)
        + " -ArgumentList "
        + arg_list
        + " -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    )
    print("Elevacion    : requerida para borrar Program Files")
    return subprocess.call([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command])

def _rmtree_writable(path: Path) -> None:
    def _fix_permissions(func: Any, target: str, exc_info: Any) -> None:
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except Exception:
            raise exc_info[1]

    shutil.rmtree(path, onerror=_fix_permissions)

def cmd_uninstall(args: argparse.Namespace) -> int:
    profile = _normalize_profile(args.profile) if getattr(args, "profile", "") else ""
    install_dir = Path(args.install_dir) if args.install_dir else (_profile_install_dir(profile) if profile else _program_files_root() / "BAGO")
    backup_root = Path(args.backup_root) if args.backup_root else (_profile_backup_root(profile) if profile else (_program_data_root() / "BAGO" / "backups"))
    user_state_dir = Path(args.user_state_dir) if args.user_state_dir else (_profile_user_state_dir(profile) if profile else (_program_data_root() / "BAGO" / "user"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if not install_dir.exists():
        print(f"[ERROR] No se encontro la instalacion: {install_dir}")
        return 1

    backup_tag = profile or "install"
    backup_zip = backup_root / f"bago-{backup_tag}-uninstall-{stamp}.zip"
    print("BAGO local uninstall")
    print(f"Perfil       : {profile or 'none'}")
    print(f"Destino      : {install_dir}")
    print(f"Backup       : {backup_zip}")
    print(f"Estado user  : {user_state_dir}")
    print(f"Purga state  : {'si' if args.purge_state else 'no'}")
    if args.dry_run:
        print("Dry-run      : no ejecutado")
        return 0

    if _needs_uninstall_elevation(install_dir) and not args.elevated_child and not args.no_elevate:
        return _relaunch_uninstall_elevated(args, install_dir)

    try:
        _zip_tree(install_dir, backup_zip)
        removed_scope = _remove_install_from_path(str(install_dir))
        context_menu_removed = _remove_bago_explorer_context_menu()
        if args.purge_state and user_state_dir.exists():
            _rmtree_writable(user_state_dir)
        _rmtree_writable(install_dir)
    except PermissionError as exc:
        print(f"[ERROR] Sin permisos para desinstalar: {exc}")
        if os.name == "nt" and not _is_windows_admin():
            print("Ejecuta PowerShell como administrador o usa el prompt UAC del comando sin --no-elevate.")
        return 1
    except OSError as exc:
        print(f"[ERROR] No se pudo completar la desinstalacion: {exc}")
        return 1
    print(f"Backup creado: {backup_zip}")
    prune_backups_root(backup_root)
    print(f"PATH limpiado : {removed_scope}")
    print(f"Menu contexto : {'si' if context_menu_removed else 'no'}")
    return 0
