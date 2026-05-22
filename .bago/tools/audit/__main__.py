#!/usr/bin/env python3
"""bago audit — Auditoría y calidad de código BAGO."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from audit._ast import main as ast_main
from audit._security import main as security_main
from audit._v2 import main as full_main

PYTHON = sys.executable
EXTERNAL_SUBCOMMANDS = {
    "pack": TOOLS / "validate_pack.py",
    "scan": TOOLS / "scan.py",
    "commit": TOOLS / "commit_readiness.py",
    "push": TOOLS / "pre_push_guard.py",
    "doctor": TOOLS / "doctor.py",
    "heal": TOOLS / "auto_heal.py",
    "quality": TOOLS / "code_quality_orchestrator.py",
    "purity": TOOLS / "check_validate_purity.py",
}

DESCRIPTIONS = {
    "full": "auditoría integral: validate+health+workflow (default)",
    "pack": "valida pack: manifest + state + roles",
    "scan": "linters + hallazgos normalizados por severidad",
    "commit": "gate de commit: syntax/secrets/debug/TODOs/size",
    "push": "gate de push: dirty tree/diverge/sincerity",
    "doctor": "diagnóstico del entorno: Python/Git/Ollama/disco",
    "heal": "auto-reparación de drift del toolchain",
    "quality": "orquestador de agentes especializados de calidad",
    "purity": "chequeo estático: validate_* no escriben archivos",
    "ast": "análisis AST semántico: callbacks, async, fixtures, env, estados…",
    "security": "auditoría de seguridad de dependencias npm",
}

def _usage() -> None:
    print(__doc__)
    print("Subcomandos:")
    for key, desc in DESCRIPTIONS.items():
        marker = " ← default" if key == "full" else ""
        print(f"  bago audit {key:<12} → {desc}{marker}")

def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        return full_main(args)

    sub = args[0].lower()
    rest = args[1:]
    if sub in ("-h", "--help", "help"):
        _usage()
        return 0
    if sub.startswith("-"):
        return full_main(args)
    if sub == "full":
        return full_main(rest)
    if sub == "ast":
        return ast_main(rest)
    if sub == "security":
        return security_main(rest)
    if sub in EXTERNAL_SUBCOMMANDS:
        return subprocess.call([PYTHON, str(EXTERNAL_SUBCOMMANDS[sub])] + rest)

    return full_main(args)

if __name__ == "__main__":
    raise SystemExit(main())
