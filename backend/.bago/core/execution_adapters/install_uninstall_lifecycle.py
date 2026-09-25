"""Materialization helpers for the Permit-ticketed system uninstall owner."""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import stat
import subprocess
import zipfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from install_uninstall_plan import build_uninstall_target, path_has_link, resolve_uninstall_python, validate_uninstall_backup_space


def _normalize_path_entry(entry: str) -> str:
    return entry.strip().rstrip("\\").lower()


def _remove_install_from_path(install_path: str) -> str:
    removed_scopes: list[str] = []
    install_norm = _normalize_path_entry(install_path)
    os.environ["Path"] = ";".join(
        clean for clean in (item.strip() for item in os.environ.get("Path", "").split(";"))
        if clean and _normalize_path_entry(clean) != install_norm
    )
    if os.name != "nt":
        return "process"
    try:
        import winreg  # type: ignore
    except Exception:
        return "process"
    def rewrite(scope_root: int) -> bool:
        try:
            with winreg.OpenKey(scope_root, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                value, reg_type = winreg.QueryValueEx(key, "Path")
                kept = [clean for clean in (item.strip() for item in str(value or "").split(";"))
                        if clean and _normalize_path_entry(clean) != install_norm]
                winreg.SetValueEx(key, "Path", 0, reg_type, ";".join(kept))
            return True
        except Exception:
            return False
    if rewrite(winreg.HKEY_CURRENT_USER):
        removed_scopes.append("user")
    if rewrite(winreg.HKEY_LOCAL_MACHINE):
        removed_scopes.append("machine")
    return "+".join(removed_scopes) if removed_scopes else "process"


def _remove_registry_tree(winreg: Any, root: Any, subkey: str) -> None:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
        for child in children:
            _remove_registry_tree(winreg, root, f"{subkey}\\{child}")
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
    for subkey in (r"Software\Classes\Directory\shell\BAGO", r"Software\Classes\Directory\Background\shell\BAGO"):
        try:
            _remove_registry_tree(winreg, winreg.HKEY_CURRENT_USER, subkey)
            removed = True
        except Exception:
            pass
    return removed


def _rmtree_writable(path: Path) -> None:
    def fix_permissions(func: Any, target: str, exc_info: Any) -> None:
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except Exception:
            raise exc_info[1]
    shutil.rmtree(path, onerror=fix_permissions)


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _needs_elevation(install_dir: Path) -> bool:
    if os.name != "nt" or _is_admin():
        return False
    roots = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]
    return any(root and _is_under(install_dir, Path(root)) for root in roots)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _validate_ticket(args: Any, *, claim: bool) -> dict[str, Any]:
    from bago_core.user_state_paths import state_root

    permit_id = str(getattr(args, "authorization_permit_id", "") or "")
    nonce = str(getattr(args, "authorization_ticket_nonce", "") or "")
    ticket_raw = str(getattr(args, "authorization_ticket_path", "") or "")
    ledger_raw = str(getattr(args, "authorization_ledger_path", "") or "")
    ledger_path = state_root() / "authorization" / "ledger.json"
    ticket_path = ledger_path.parent / "install-tickets" / f"{permit_id}.json"
    if (not permit_id.startswith("permit-") or not nonce or not ticket_raw or not ledger_raw
            or Path(ledger_raw).resolve() != ledger_path.resolve()
            or Path(ticket_raw).resolve() != ticket_path.resolve()
            or path_has_link(ledger_path) or path_has_link(ticket_path)
            or not ticket_path.is_file()):
        raise ValueError("La autorización de uninstall no es canónica")
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    record = next((item for item in ledger.get("permits", {}).values()
                   if isinstance(item, dict) and item.get("permit_id") == permit_id), None)
    request = record.get("executed_request", {}) if isinstance(record, dict) else {}
    proof = record.get("proof", {}) if isinstance(record, dict) else {}
    decision = record.get("decision", {}) if isinstance(record, dict) else {}
    target = ticket.get("target", {})
    live_target = build_uninstall_target(str(getattr(args, "install_dir", "")), bool(getattr(args, "purge_state", False)))
    if (not isinstance(record, dict)
            or ticket.get("schema") != "bago.system-install-uninstall-ticket.v1"
            or ticket.get("nonce") != nonce or ticket.get("permit_id") != permit_id
            or ticket.get("effect_id") != "system.install.uninstall"
            or record.get("state") != "consumed" or record.get("effect_id") != ticket.get("effect_id")
            or record.get("session_id") != ticket.get("session_id")
            or record.get("operation_fingerprint") != ticket.get("operation_fingerprint")
            or request.get("operation_fingerprint") != ticket.get("operation_fingerprint")
            or request.get("session_id") != ticket.get("session_id")
            or request.get("effect_id") != ticket.get("effect_id")
            or request.get("source_surface") != "api.install.uninstall"
            or request.get("scope") != "system"
            or request.get("actor_kind") != "user"
            or request.get("principal_id") != "interactive-local-user"
            or request.get("target") != target or target != live_target
            or Path(str(getattr(args, "backup_root", ""))).resolve() != Path(target["backup_root"]).resolve()
            or Path(str(getattr(args, "user_state_dir", ""))).resolve() != Path(target["user_state_dir"]).resolve()
            or proof.get("user_decision") != "approve"
            or proof.get("proof_id") != record.get("proof_id")
            or proof.get("authenticated_session_id") != ticket.get("session_id")
            or proof.get("effect_id") != ticket.get("effect_id")
            or proof.get("operation_fingerprint") != ticket.get("operation_fingerprint")
            or proof.get("provenance", {}).get("kind") != "direct_user_interaction"
            or proof.get("provenance", {}).get("channel") != "desktop"
            or decision.get("result") != "allow"
            or decision.get("proof_id") != proof.get("proof_id")
            or decision.get("effect_id") != ticket.get("effect_id")
            or decision.get("operation_fingerprint") != ticket.get("operation_fingerprint")):
        raise ValueError("El ticket no coincide con el Permit consumido ni con el destino actual")
    if claim:
        marker = ticket_path.with_suffix(".consumed")
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        ticket_path.unlink()
    return target


def run_authorized_uninstall(args: Any) -> int:
    """Ticket-gated CLI helper; all uninstall material effects stay in this owner."""
    target = _validate_ticket(args, claim=False)
    validate_uninstall_backup_space(target)
    install_dir = Path(target["install_dir"])
    if _needs_elevation(install_dir) and not bool(getattr(args, "elevated_child", False)):
        from bago_core.launcher import BAGO_ROOT
        executable = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
        cli_path = Path(BAGO_ROOT) / "bago_core" / "cli.py"
        argv = [str(cli_path), "uninstall", "--install-dir", str(install_dir),
                "--backup-root", target["backup_root"], "--user-state-dir", target["user_state_dir"],
                "--authorization-ticket-path", args.authorization_ticket_path,
                "--authorization-ticket-nonce", args.authorization_ticket_nonce,
                "--authorization-permit-id", args.authorization_permit_id,
                "--authorization-ledger-path", args.authorization_ledger_path, "--elevated-child"]
        if target["purge_state"]:
            argv.append("--purge-state")
        # Start-Process accepts one command-line string. list2cmdline preserves
        # Windows quoting for paths and values containing spaces or quotes.
        ps_args = subprocess.list2cmdline(argv)
        python = resolve_uninstall_python(install_dir)
        quote_ps = lambda value: "'" + value.replace("'", "''") + "'"
        command = "$p=Start-Process -FilePath " + quote_ps(python) + " -ArgumentList " + quote_ps(ps_args) + " -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
        return subprocess.call([executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command])

    target = _validate_ticket(args, claim=True)
    # Re-fingerprint after consuming the ticket so drift between the initial
    # check and the one-use claim still blocks every material effect.
    current_target = build_uninstall_target(
        str(getattr(args, "install_dir", "")), bool(getattr(args, "purge_state", False))
    )
    if current_target != target:
        raise ValueError("La instalación cambió antes de comenzar la desinstalación")
    source = Path(target["install_dir"])
    backup_root = Path(target["backup_root"])
    user_state = Path(target["user_state_dir"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / f"bago-install-uninstall-{stamp}-{uuid.uuid4().hex[:8]}.zip"
    files = []
    size = 0
    for item in source.rglob("*"):
        info = item.lstat()
        if item.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            raise ValueError(f"La instalación contiene un enlace que impide desinstalar: {item}")
        if stat.S_ISREG(info.st_mode):
            files.append(item)
            size += info.st_size
    backup_root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(backup_root).free < size:
        raise OSError("No hay espacio suficiente para el backup de desinstalación")
    with zipfile.ZipFile(backup, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(item, item.relative_to(source))
    removed_scope = _remove_install_from_path(str(source))
    context_menu_removed = _remove_bago_explorer_context_menu()
    if target["purge_state"] and user_state.exists():
        if path_has_link(user_state):
            raise ValueError("El estado de usuario tiene un componente enlazado")
        _rmtree_writable(user_state)
    _rmtree_writable(source)
    print(f"Backup creado: {backup}")
    print(f"PATH limpiado : {removed_scope}")
    print(f"Menu contexto : {'si' if context_menu_removed else 'no'}")
    return 0
