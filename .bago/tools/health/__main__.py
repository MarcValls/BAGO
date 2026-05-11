#!/usr/bin/env python3
"""bago health — Salud y calidad del framework BAGO."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from health._check import main as check_main
from health._report import main as report_main
from health._score import main as score_main

PYTHON = sys.executable

EXTERNAL_SUBCOMMANDS = {
    "efficiency": TOOLS / "efficiency_meter.py",
    "consistency": TOOLS / "bago_consistency_check.py",
    "sincerity": TOOLS / "sincerity_detector.py",
}

DESCRIPTIONS = {
    "score": "score 0-100 ponderado (default)",
    "report": "reporte completo Markdown/HTML",
    "stability": "diagnóstico completo de estabilidad del workspace",
    "efficiency": "ratio de eficiencia inter-versiones",
    "consistency": "anti-drift: registry/CI/README coherentes",
    "sincerity": "detecta sincofancía y promesas vacías en docs",
}

def _usage() -> None:
    print(__doc__)
    print("Subcomandos:")
    for key, desc in DESCRIPTIONS.items():
        marker = " ← default" if key == "score" else ""
        print(f"  bago health {key:<14} → {desc}{marker}")

def _suggest(exit_code: int) -> None:
    try:
        engine_path = TOOLS / "bago_sac_engine.py"
        spec = importlib.util.spec_from_file_location("bago_sac_engine", str(engine_path))
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.sac_suggest("bago health", exit_code=exit_code)
    except Exception:
        pass

def _run_external(script: Path, argv: list[str]) -> int:
    return subprocess.call([PYTHON, str(script)] + argv)

def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        code = score_main(args)
        _suggest(code)
        return code

    sub = args[0].lower()
    if sub in ("-h", "--help", "help"):
        _usage()
        return 0
    if sub.startswith("-"):
        code = score_main(args)
        _suggest(code)
        return code
    if sub == "score":
        code = score_main(args[1:])
        _suggest(code)
        return code
    if sub == "report":
        code = report_main(args[1:])
        _suggest(code)
        return code
    if sub in {"stability", "check"}:
        code = check_main(args[1:])
        _suggest(code)
        return code
    if sub in EXTERNAL_SUBCOMMANDS:
        code = _run_external(EXTERNAL_SUBCOMMANDS[sub], args[1:])
        _suggest(code)
        return code

    code = score_main(args)
    _suggest(code)
    return code

if __name__ == "__main__":
    raise SystemExit(main())
