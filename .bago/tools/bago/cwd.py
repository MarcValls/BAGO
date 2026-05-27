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



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
