"""Helper para resolver el cwd del usuario invocador de BAGO."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .constants import USER_BAGO


_CWD_FILE = USER_BAGO / "cwd.json"
_WORKSPACES_FILE = USER_BAGO / "workspaces.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _load_persisted_cwd() -> Path | None:
    if not _CWD_FILE.exists():
        return None
    data = _read_json(_CWD_FILE)
    raw = str(data.get("cwd", "")).strip()
    if not raw:
        return None
    try:
        cwd = Path(raw).expanduser().resolve()
    except Exception:
        return None
    return cwd if cwd.exists() and cwd.is_dir() else None


def _load_active_workspace_cwd() -> Path | None:
    if not _WORKSPACES_FILE.exists():
        return None
    data = _read_json(_WORKSPACES_FILE)
    active_id = data.get("active_workspace_id")
    for ws in data.get("workspaces", []):
        if ws.get("id") != active_id:
            continue
        raw = str(ws.get("path", "")).strip()
        if not raw:
            return None
        try:
            cwd = Path(raw).expanduser().resolve()
        except Exception:
            return None
        return cwd if cwd.exists() and cwd.is_dir() else None
    return None


def set_user_cwd(path: str | Path, *, persist: bool = True) -> Path:
    cwd = Path(path).expanduser().resolve()
    if not cwd.exists():
        raise FileNotFoundError(f"No existe: {cwd}")
    if not cwd.is_dir():
        raise NotADirectoryError(f"No es una carpeta: {cwd}")
    os.environ["BAGO_USER_CWD"] = str(cwd)
    if persist:
        _CWD_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CWD_FILE.write_text(json.dumps({"cwd": str(cwd)}, indent=2, ensure_ascii=False), encoding="utf-8")
    return cwd


def clear_user_cwd() -> None:
    os.environ.pop("BAGO_USER_CWD", None)
    try:
        if _CWD_FILE.exists():
            _CWD_FILE.unlink()
    except Exception:
        pass


def get_user_cwd() -> Path:
    env_cwd = os.environ.get("BAGO_USER_CWD", "")
    if env_cwd:
        try:
            cwd = Path(env_cwd).expanduser().resolve()
            if cwd.exists() and cwd.is_dir():
                return cwd
        except Exception:
            pass
    persisted = _load_persisted_cwd()
    if persisted is not None:
        return persisted
    active_ws = _load_active_workspace_cwd()
    if active_ws is not None:
        return active_ws
    return Path(os.getcwd()).resolve()
