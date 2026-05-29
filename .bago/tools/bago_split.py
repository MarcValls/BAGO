#!/usr/bin/env python3
"""bago_split.py — Wrapper Python para lanzar el entorno dividido.

Uso:
    python bago_split.py
    bago split

Delega en bago_split.ps1 (en la raíz del repo) para mantener la lógica
de paneles en un único lugar.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent
    root = here.parents[1]  # .bago/tools → .bago → root
    ps1 = root / "bago_split.ps1"

    if not ps1.exists():
        print(f"[ERROR] No se encontro {ps1}", file=sys.stderr)
        return 1

    cmd = [
        "powershell",
        "-ExecutionPolicy", "Bypass",
        "-File", str(ps1),
        "-BagoRoot", str(root),
        "-ChatScript", ".bago\\tools\\bago_chat.py",
    ]
    print(f"[BAGO-Split] Lanzando entorno dividido desde {ps1} ...")
    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    sys.exit(main())
