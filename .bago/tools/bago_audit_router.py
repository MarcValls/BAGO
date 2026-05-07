#!/usr/bin/env python3
"""bago_audit_router — Auditoría y calidad de código BAGO.

Sin subcomando → auditoría integral V2 (igual que antes).

Uso:
  bago audit               → auditoría integral: validate+health+workflow
  bago audit full          → ídem, explícito
  bago audit pack          → valida pack: manifest + state + roles
  bago audit scan          → linters + hallazgos normalizados
  bago audit commit        → gate de commit: syntax/secrets/TODOs/size
  bago audit push          → gate de push: dirty/diverge/sincerity
  bago audit doctor        → diagnóstico del entorno (Python/Git/Ollama/disco)
  bago audit heal          → auto-reparación de drift del toolchain
  bago audit quality       → orquesta agentes especializados de calidad
  bago audit purity        → chequeo estático: validate_* no escriben archivos
  bago audit ast [DIR]     → análisis AST semántico: asimetrías declare/consume
  bago audit ast --self    → análisis AST del propio BAGO
"""
import subprocess, sys
from pathlib import Path

TOOLS = Path(__file__).parent
PYTHON = sys.executable

SUBCOMMANDS = {
    "full":    (TOOLS / "audit_v2.py",                   []),
    "pack":    (TOOLS / "validate_pack.py",              []),
    "scan":    (TOOLS / "scan.py",                       []),
    "commit":  (TOOLS / "commit_readiness.py",           []),
    "push":    (TOOLS / "pre_push_guard.py",             []),
    "doctor":  (TOOLS / "bago_doctor.py",                []),
    "heal":    (TOOLS / "auto_heal.py",                  []),
    "quality": (TOOLS / "code_quality_orchestrator.py",  []),
    "purity":  (TOOLS / "check_validate_purity.py",      []),
    "ast":     (TOOLS / "bago_ast_audit.py",             []),
}

DESCRIPTIONS = {
    "full":    "auditoría integral: validate+health+workflow (default)",
    "pack":    "valida pack: manifest + state + roles",
    "scan":    "linters + hallazgos normalizados por severidad",
    "commit":  "gate de commit: syntax/secrets/debug/TODOs/size",
    "push":    "gate de push: dirty tree/diverge/sincerity",
    "doctor":  "diagnóstico del entorno: Python/Git/Ollama/disco",
    "heal":    "auto-reparación de drift del toolchain",
    "quality": "orquestador de agentes especializados de calidad",
    "purity":  "chequeo estático: validate_* no escriben archivos",
    "ast":     "análisis AST semántico: callbacks, async, fixtures, env, estados…",
}

def _usage():
    print(__doc__)
    print("Subcomandos:")
    for k, desc in DESCRIPTIONS.items():
        marker = " ← default" if k == "full" else ""
        print(f"  bago audit {k:<12} → {desc}{marker}")

def main():
    args = sys.argv[1:]

    # Sin subcomando → backward compat: auditoría integral
    if not args or args[0].startswith("-"):
        script = TOOLS / "audit_v2.py"
        sys.exit(subprocess.call([PYTHON, str(script)] + args))

    sub = args[0].lower()
    if sub in ("-h", "--help"):
        _usage(); return

    if sub not in SUBCOMMANDS:
        # Arg no reconocido → full audit con todos los args pasados
        script = TOOLS / "audit_v2.py"
        sys.exit(subprocess.call([PYTHON, str(script)] + args))

    script, extra = SUBCOMMANDS[sub]
    sys.exit(subprocess.call([PYTHON, str(script)] + extra + args[1:]))

if __name__ == "__main__":
    main()
