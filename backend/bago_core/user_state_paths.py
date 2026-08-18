from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

# Canonical user-state contract:
#   BAGO_STATE_ROOT -> exact mutable state directory
#   BAGO_USER_ROOT  -> user-owned BAGO root (state lives in <root>/state)
#   default         -> the per-user LocalAppData BAGO root
# Path.home()/.bago is legacy discovery only; callers must not use it as the
# default write location.
USER_ROOT_ENV = "BAGO_USER_ROOT"
STATE_ROOT_ENV = "BAGO_STATE_ROOT"
RUNTIME_ROOT_ENV = "BAGO_RUNTIME_ROOT"
BACKUP_KEEP_COUNT_ENV = "BAGO_BACKUP_KEEP_COUNT"
BACKUP_KEEP_DAYS_ENV = "BAGO_BACKUP_KEEP_DAYS"
BACKUP_MAX_FILE_GB_ENV = "BAGO_BACKUP_MAX_FILE_GB"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


def legacy_user_root() -> Path:
    return Path.home() / ".bago"


def user_root() -> Path:
    override = _env_path(USER_ROOT_ENV)
    if override is not None:
        return override
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local).expanduser().resolve() / "BAGO"
    return Path.home() / "AppData" / "Local" / "BAGO"


def runtime_root() -> Path:
    override = _env_path(RUNTIME_ROOT_ENV)
    return override if override is not None else user_root() / "runtime"


def state_root() -> Path:
    override = _env_path(STATE_ROOT_ENV)
    return override if override is not None else user_root() / "state"


def logs_root() -> Path:
    return user_root() / "logs"


def secrets_root() -> Path:
    return user_root() / "secrets"


def state_read_roots() -> tuple[Path, ...]:
    """Canonical state root plus the legacy read-only fallback when safe.

    Explicit BAGO_STATE_ROOT/BAGO_USER_ROOT values are isolation boundaries,
    so they disable implicit reads from the user's legacy ~/.bago tree.
    """
    canonical = state_root()
    if _env_path(STATE_ROOT_ENV) is not None or _env_path(USER_ROOT_ENV) is not None:
        return (canonical,)
    legacy = legacy_user_root() / "state"
    return (canonical,) if legacy == canonical else (canonical, legacy)


def state_read_candidates(relative: str | Path) -> tuple[Path, ...]:
    target = Path(relative)
    if target.is_absolute():
        raise ValueError("state read candidate must be relative")
    return tuple(root / target for root in state_read_roots())


def user_read_roots() -> tuple[Path, ...]:
    """Canonical user root plus legacy read-only fallback without overrides."""
    canonical = user_root()
    if _env_path(USER_ROOT_ENV) is not None:
        return (canonical,)
    legacy = legacy_user_root()
    return (canonical,) if legacy == canonical else (canonical, legacy)


def user_read_candidates(relative: str | Path) -> tuple[Path, ...]:
    target = Path(relative)
    if target.is_absolute():
        raise ValueError("user read candidate must be relative")
    return tuple(root / target for root in user_read_roots())


def user_legacy_read_candidates(relative: str | Path) -> tuple[Path, ...]:
    """Legacy-only user paths, used for compatibility reads without writes."""
    target = Path(relative)
    if target.is_absolute():
        raise ValueError("user read candidate must be relative")
    return (legacy_user_root() / target,)


def cache_root() -> Path:
    return user_root() / "cache"


def backups_root() -> Path:
    return user_root() / "backups"


def backup_rotation_limits() -> tuple[int, int, int]:
    keep_count = int(os.environ.get(BACKUP_KEEP_COUNT_ENV, "3") or "3")
    keep_days = int(os.environ.get(BACKUP_KEEP_DAYS_ENV, "14") or "14")
    max_file_gb = float(os.environ.get(BACKUP_MAX_FILE_GB_ENV, "10") or "10")
    return keep_count, keep_days, int(max_file_gb * (1024**3))


def _backup_sidecars(zip_path: Path) -> list[Path]:
    return [
        zip_path.with_name(f"{zip_path.name}.manifest.json"),
        zip_path.with_name(f"{zip_path.name}.snapshot.json"),
        zip_path.with_name(f"{zip_path.name}.report.md"),
        zip_path.with_name(f"{zip_path.name}.sha256"),
    ]


def prune_backups_root(root: Path | None = None, *, dry_run: bool = False) -> list[Path]:
    backup_dir = root or backups_root()
    if not backup_dir.exists():
        return []

    keep_count, keep_days, max_file_bytes = backup_rotation_limits()
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=keep_days)
    archives = sorted(
        [p for p in backup_dir.rglob("*.zip") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    keep: set[Path] = set()
    for index, archive in enumerate(archives):
        mtime = _dt.datetime.fromtimestamp(archive.stat().st_mtime, tz=_dt.timezone.utc)
        if index < keep_count or mtime >= cutoff:
            keep.add(archive)

    removed: list[Path] = []
    for archive in archives:
        oversized = archive.stat().st_size > max_file_bytes
        if archive in keep and not oversized:
            continue
        if not oversized and archive in keep:
            continue
        for target in [archive, *_backup_sidecars(archive)]:
            if not target.exists():
                continue
            if dry_run:
                print(f"[dry-run] would remove {target}")
            else:
                target.unlink()
                print(f"removed {target}")
            removed.append(target)
    return removed


def install_selection_file() -> Path:
    return user_root() / "install_selection.json"


def supervisor_state_file() -> Path:
    return state_root() / "supervisor.json"


def supervisor_log_file() -> Path:
    return state_root() / "supervisor.log"


def supervisor_lock_file() -> Path:
    return state_root() / "supervisor.lock"


def bago_lock_file() -> Path:
    return state_root() / "bago.lock"


def supervisor_stop_file() -> Path:
    return state_root() / "supervisor.stop"


def ensure_user_roots() -> None:
    for path in (user_root(), runtime_root(), state_root(), cache_root(), backups_root()):
        path.mkdir(parents=True, exist_ok=True)
    prune_backups_root(backups_root())
