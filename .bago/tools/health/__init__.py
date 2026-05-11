"""Health package for BAGO tools."""
from ._check import main as check_main
from ._report import generate_html, generate_markdown, main as report_main
from ._score import (
    main as score_main,
    run_script,
    score_captura_decisiones,
    score_consistencia_inventario,
    score_disciplina_workflow,
    score_estado_stale,
    score_integridad,
)

__all__ = [
    "check_main",
    "generate_html",
    "generate_markdown",
    "report_main",
    "run_script",
    "score_captura_decisiones",
    "score_consistencia_inventario",
    "score_disciplina_workflow",
    "score_estado_stale",
    "score_integridad",
    "score_main",
]
