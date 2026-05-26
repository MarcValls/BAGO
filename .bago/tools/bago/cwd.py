"""Helper para resolver el cwd del usuario invocador de BAGO."""
from __future__ import annotations

import os
from pathlib import Path


def get_user_cwd() -> Path:
    env_cwd = os.environ.get("BAGO_USER_CWD", "")
    if env_cwd:
        try:
            return Path(env_cwd).expanduser().resolve()
        except Exception:
            pass
    return Path(os.getcwd()).resolve()
