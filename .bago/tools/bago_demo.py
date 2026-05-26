#!/usr/bin/env python3
"""bago_demo.py - entrada rapida para mostrar BAGO sin exponer estado interno."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent.parent


def main() -> int:
    port = "8080"
    args = sys.argv[1:]
    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = args[idx + 1]

    if "--serve" in args:
        server = TOOLS / "bago_miniapp_server.py"
        return subprocess.run([sys.executable, str(server), "--port", port]).returncode

    print("BAGO demo")
    print(f"Dashboard publico: python {REPO / 'bago_core' / 'launcher.py'} dashboard --public")
    print(f"Publish kit beta:  python {REPO / 'bago_core' / 'launcher.py'} publish-kit --channel beta")
    print(f"Miniapp local:      python {REPO / 'bago_core' / 'launcher.py'} demo --serve --port {port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

