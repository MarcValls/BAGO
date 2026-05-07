#!/usr/bin/env python3
"""bago_health_router — Salud y calidad del framework BAGO.

Sin subcomando → muestra el health score (igual que antes).

Uso:
  bago health                  → score 0-100 (comportamiento original)
  bago health score            → ídem, explícito
  bago health report           → reporte completo Markdown/HTML
  bago health stability        → resumen GO/WARN/KO de validadores
  bago health efficiency       → ratio de eficiencia inter-versiones
  bago health consistency      → anti-drift: registry/CI/README coherentes
  bago health sincerity        → centinela: detecta sincofancía en docs
"""
import subprocess, sys
from pathlib import Path

TOOLS = Path(__file__).parent
PYTHON = sys.executable

SUBCOMMANDS = {
    "score":       (TOOLS / "health_score.py",          []),
    "report":      (TOOLS / "health_report.py",         []),
    "stability":   (TOOLS / "stability_summary.py",     []),
    "efficiency":  (TOOLS / "efficiency_meter.py",      []),
    "consistency": (TOOLS / "bago_consistency_check.py",[]),
    "sincerity":   (TOOLS / "sincerity_detector.py",    []),
}

DESCRIPTIONS = {
    "score":       "score 0-100 ponderado (default)",
    "report":      "reporte completo Markdown/HTML",
    "stability":   "resumen GO/WARN/KO de validadores y sandbox",
    "efficiency":  "ratio de eficiencia inter-versiones",
    "consistency": "anti-drift: registry/CI/README coherentes",
    "sincerity":   "detecta sincofancía y promesas vacías en docs",
}

def _usage():
    print(__doc__)
    print("Subcomandos:")
    for k, desc in DESCRIPTIONS.items():
        marker = " ← default" if k == "score" else ""
        print(f"  bago health {k:<14} → {desc}{marker}")

def main():
    args = sys.argv[1:]

    # Sin subcomando → backward compat: health score
    if not args or args[0].startswith("-"):
        script = TOOLS / "health_score.py"
        sys.exit(subprocess.call([PYTHON, str(script)] + args))

    sub = args[0].lower()
    if sub in ("-h", "--help"):
        _usage(); return

    if sub not in SUBCOMMANDS:
        # Si el primer arg no es subcomando (ej: bago health --full)
        # asume que van para health_score
        script = TOOLS / "health_score.py"
        sys.exit(subprocess.call([PYTHON, str(script)] + args))

    script, extra = SUBCOMMANDS[sub]
    _code = subprocess.call([PYTHON, str(script)] + extra + args[1:])
    try:
        import importlib.util as _ilu
        _ep = Path(__file__).parent / "bago_sac_engine.py"
        _spec = _ilu.spec_from_file_location("bago_sac_engine", str(_ep))
        _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        _mod.sac_suggest("bago health", exit_code=_code)
    except Exception:
        pass
    sys.exit(_code)

if __name__ == "__main__":
    main()
