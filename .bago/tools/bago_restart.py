#!/usr/bin/env python3
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAT = ROOT / ".bago" / "tools" / "bago_chat.py"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--test" in argv:
        print("restart self-test OK" if CHAT.exists() else "restart self-test FAIL")
        return 0 if CHAT.exists() else 1
    if not CHAT.exists():
        print(f"No se encontró {CHAT}", file=sys.stderr)
        return 1
    if sys.platform == "win32":
        subprocess.Popen([sys.executable, str(CHAT)], cwd=str(ROOT), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        return 0
    os.execv(sys.executable, [sys.executable, str(CHAT)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
