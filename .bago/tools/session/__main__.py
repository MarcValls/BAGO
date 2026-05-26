#!/usr/bin/env python3
"""bago session — Ciclo de vida de sesiones BAGO."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from session._close import main as close_main
from session._logger import main as logger_main
from session._opener import main as opener_main
from session._preflight import main as preflight_main
from session._stats import main as stats_main

PYTHON = sys.executable
EXTERNAL_SUBCOMMANDS = {
    "harvest": TOOLS / "cosecha.py",
    "cosecha": TOOLS / "cosecha.py",
    "v2": TOOLS / "v2_close_checklist.py",
}

DESCRIPTIONS = {
    "open": "abre sesión W2 pre-rellenada desde handoff",
    "reopen": "reabre una sesión desde el último session_close",
    "close": "genera artefacto SESSION_CLOSE al terminar",
    "harvest": "protocolo W9 — cierra sesión + CHG + EVD automáticos",
    "v2": "checklist de cierre técnico V2 (validate/reconcile/stale)",
    "preflight": "valida reglas W7 antes de abrir sesión",
    "stats": "resumen estadístico de sesiones BAGO",
    "logger": "últimas sesiones o historial de ejecución",
}

def _usage() -> None:
    print(__doc__)
    print("Subcomandos:")
    for key, desc in DESCRIPTIONS.items():
        print(f"  bago session {key:<10} → {desc}")

def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        _usage()
        return 0

    sub = args[0].lower()
    rest = args[1:]
    if sub in {"open", "start"}:
        return opener_main(rest)
    if sub == "reopen":
        return opener_main(["--reopen", *rest])
    if sub == "close":
        return close_main(rest)
    if sub == "preflight":
        return preflight_main(rest)
    if sub == "stats":
        return stats_main(rest)
    if sub == "logger":
        return logger_main(rest)
    if sub in EXTERNAL_SUBCOMMANDS:
        return subprocess.call([PYTHON, str(EXTERNAL_SUBCOMMANDS[sub])] + rest)

    print(f"❌ Subcomando desconocido: '{sub}'")
    _usage()
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
