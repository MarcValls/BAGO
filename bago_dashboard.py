#!/usr/bin/env python3
"""bago_dashboard.py — Shortcut para ejecutar bago dashboard."""
import subprocess
import sys
from pathlib import Path

def main():
    repo = Path(__file__).parent
    launcher = repo / "bago_core" / "launcher.py"
    if not launcher.exists():
        print("[ERROR] Launcher no encontrado:", launcher)
        sys.exit(1)
    subprocess.run([sys.executable, str(launcher), "dashboard"] + sys.argv[1:])

if __name__ == "__main__":
    main()
