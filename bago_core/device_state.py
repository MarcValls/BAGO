"""Device and credential storage policy for BAGO startup."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from pathlib import Path


def default_user_home() -> Path:
    if platform.system() == "Windows":
        program_data = os.environ.get("ProgramData")
        if program_data:
            return Path(program_data) / "BAGO" / "user"
    return Path.home() / ".bago" / "user"


def binding_file() -> Path:
    return Path.home() / ".bago" / "device_binding.json"


def _portable_base(drive: Path) -> Path | None:
    for folder in ("bago", "BAGO"):
        base = drive / folder
        if (base / ".bago").exists():
            return base
    return None


def _windows_drives() -> list[Path]:
    drives: list[Path] = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in range(26):
            if bitmask & (1 << letter):
                drive = Path(f"{chr(65 + letter)}:\\")
                if drive.exists():
                    drives.append(drive)
    except Exception:
        pass
    return drives


def removable_drives() -> list[Path]:
    system = platform.system()
    if system == "Windows":
        out: list[Path] = []
        for drive in _windows_drives():
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(str(drive)) == 2:
                    out.append(drive)
            except Exception:
                pass
        return out
    if system == "Darwin":
        return [p for p in Path("/Volumes").glob("*") if p.is_mount()]

    roots: list[Path] = []
    for base in (Path("/media"), Path("/run/media"), Path("/mnt")):
        if base.exists():
            roots.extend(p for p in base.rglob("*") if p.is_mount())
    return roots


def bago_devices() -> list[Path]:
    devices: list[Path] = []
    seen: set[str] = set()
    for drive in removable_drives():
        base = _portable_base(drive)
        if base:
            key = str(base.resolve()).lower()
            if key not in seen:
                seen.add(key)
                devices.append(base)
    return devices


def device_user_home(device_root: Path) -> Path:
    return device_root / ".bago" / "user"


def load_binding() -> dict:
    path = binding_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_local_credential_binding(path: Path) -> None:
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    bf = binding_file()
    bf.parent.mkdir(parents=True, exist_ok=True)
    bf.write_text(
        json.dumps(
            {
                "schema": 1,
                "mode": "local",
                "credential_home": str(path),
                "warning": "Local credential storage. Do not commit this directory.",
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )


def resolve_device_context() -> dict:
    explicit_home = os.environ.get("BAGO_USER_HOME") or os.environ.get("BAGO_USER_DIR")
    if explicit_home:
        return {
            "mode": "explicit",
            "credentials_mode": os.environ.get("BAGO_CREDENTIALS_MODE", "local"),
            "user_home": str(Path(explicit_home).expanduser()),
            "device_root": "",
        }

    devices = bago_devices()
    if devices:
        device = devices[0]
        return {
            "mode": "device",
            "credentials_mode": "device",
            "user_home": str(device_user_home(device)),
            "device_root": str(device),
        }

    binding = load_binding()
    if binding.get("mode") == "local" and binding.get("credential_home"):
        return {
            "mode": "local",
            "credentials_mode": "local",
            "user_home": str(Path(binding["credential_home"]).expanduser()),
            "device_root": "",
        }

    return {
        "mode": "session",
        "credentials_mode": "session",
        "user_home": str(default_user_home()),
        "device_root": "",
    }


def apply_device_context() -> dict:
    ctx = resolve_device_context()
    os.environ.setdefault("BAGO_CREDENTIALS_MODE", ctx["credentials_mode"])
    if not os.environ.get("BAGO_USER_HOME") and not os.environ.get("BAGO_USER_DIR"):
        os.environ["BAGO_USER_HOME"] = ctx["user_home"]
    if ctx.get("device_root"):
        os.environ["BAGO_DEVICE_ROOT"] = ctx["device_root"]
    return ctx
