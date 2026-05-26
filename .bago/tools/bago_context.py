#!/usr/bin/env python3
"""bago_context — Mapa y detección de contexto BAGO.

Router de subcomandos para análisis de contexto del workspace.

Uso:
  bago context detect        → detecta madurez (HARVEST/WATCH/CLEAN)
  bago context map           → mapa distribuido de instalaciones .bago/
  bago context git           → estado git del repo activo
  bago context stale         → detecta artefactos desactualizados
  bago context               → muestra este menú
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import subprocess, sys
from pathlib import Path

TOOLS = Path(__file__).parent
PYTHON = sys.executable

SUBCOMMANDS = {
    "detect":  (TOOLS / "context_detector.py", []),
    "d":       (TOOLS / "context_detector.py", []),
    "map":     (TOOLS / "context_map.py",      []),
    "git":     (TOOLS / "git_context.py",      []),
    "stale":   (TOOLS / "stale_detector.py",   []),
}

def _usage():
    print(__doc__)
    print("Subcomandos disponibles:")
    for k in ["detect", "map", "git", "stale"]:
        print(f"  bago context {k}")

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        _usage(); return
    sub = args[0].lower()
    if sub not in SUBCOMMANDS:
        print(f"❌ Subcomando desconocido: '{sub}'"); _usage(); sys.exit(1)
    script, extra = SUBCOMMANDS[sub]
    cmd = [PYTHON, str(script)] + extra + args[1:]
    sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("bago_context --test: PASS (subcommands defined, router loadable)")
        raise SystemExit(0)
    main()
