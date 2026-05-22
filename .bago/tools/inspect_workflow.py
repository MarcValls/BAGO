#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""inspect_workflow — Inspecciona y muestra el contenido de workflows BAGO."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT / ".bago/workflows"


def _load_workflow_guidance() -> dict:
    """Load WORKFLOW_GUIDANCE from workflow_guidance.json; fall back to hardcoded dict on error."""
    try:
        cfg_path = ROOT / ".bago" / "state" / "config" / "workflow_guidance.json"
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data.get("workflows", _WORKFLOW_GUIDANCE_FALLBACK)
    except Exception:
        return _WORKFLOW_GUIDANCE_FALLBACK


_WORKFLOW_GUIDANCE_FALLBACK = {
    "W1": {
        "purpose": "Arrancar desde un repo desconocido y dejar un contexto util.",
        "context": [
            "Estructura real del repo",
            "Stack detectado",
            "Entradas canónicas del proyecto",
            "Estado actual frente al árbol real",
        ],
        "questions": [
            "Que objetivo técnico tiene prioridad ahora?",
            "Que partes del repo ya están claras y cuales no?",
            "Hay restricciones de seguridad, tiempo o alcance?",
        ],
        "prerequisites": [
            "Leer README raíz y la entrada .bago",
            "Listar archivos y detectar stack",
            "Contrastar estado con repo real",
        ],
        "verify": "Queda un objetivo inicial claro y un siguiente paso útil sin ambigüedad.",
    },
    "W2": {
        "purpose": "Implementar una tarea técnica sin dispersion ni perdida de trazabilidad.",
        "context": [
            "Objetivo concreto",
            "Alcance y no alcance",
            "Archivos afectados",
            "Validación esperada",
        ],
        "questions": [
            "Que cambio exacto hay que hacer?",
            "Que no debe cambiar?",
            "Como se valida que funciono?",
        ],
        "prerequisites": [
            "Aclarar objetivo",
            "Identificar archivos y contratos",
            "Definir criterio de salida",
        ],
        "verify": "La tarea entra en una implementación pequeña, acotada y verificable.",
    },
    "W3": {
        "purpose": "Refactorizar sin romper contratos ni introducir deriva.",
        "context": [
            "Contratos afectados",
            "Riesgo de regresión",
            "Límites del refactor",
        ],
        "questions": [
            "Que contrato no puede romperse?",
            "Que parte conviene aislar primero?",
            "Hay validación humana requerida?",
        ],
        "prerequisites": [
            "Inventariar contratos",
            "Marcar alcance del refactor",
            "Preparar validación",
        ],
        "verify": "El refactor queda delimitado y no altera el comportamiento esperado.",
    },
    "W4": {
        "purpose": "Investigar y resolver fallos donde hay varias causas plausibles.",
        "context": [
            "Síntomas observados",
            "Hipótesis en competencia",
            "Evidencia reproducible",
        ],
        "questions": [
            "Cual es el síntoma exacto?",
            "Que hipótesis tienen sentido primero?",
            "Que prueba mínima discrimina mejor?",
        ],
        "prerequisites": [
            "Capturar error exacto",
            "Reproducir el fallo",
            "Reducir superficie de búsqueda",
        ],
        "verify": "Se identifica una causa probable y una corrección mínima comprobable.",
    },
    "W5": {
        "purpose": "Dejar la sesión retocable y retomable.",
        "context": [
            "Objetivo vigente",
            "Trabajo hecho",
            "Pendientes",
            "Decisiones congeladas",
        ],
        "questions": [
            "Que queda pendiente de forma concreta?",
            "Que no se debe reabrir?",
            "Cual es el siguiente paso si se retoma?",
        ],
        "prerequisites": [
            "Resumir lo ejecutado",
            "Anotar lo pendiente",
            "Congelar decisiones",
        ],
        "verify": "La sesión puede retomarse sin reconstruir contexto manualmente.",
    },
    "W6": {
        "purpose": "Analizar el repo y proponer ideas contextualizadas, priorizadas por implementabilidad y estabilidad.",
        "context": [
            "Estado BAGO",
            "Reports del sandbox",
            "Baseline operativo",
            "Puntos de entrada del repo",
        ],
        "questions": [
            "Que ideas entran en contexto sin romper estabilidad?",
            "Que idea es la mas pequeña y útil?",
            "Conviene detalle o ya se puede aceptar?",
        ],
        "prerequisites": [
            "Leer el estado y los reports",
            "Verificar que la base está estable",
            "Ordenar ideas por riesgo y coste",
        ],
        "verify": "Se obtiene una idea concreta lista para pasar a W2 o se rechaza por riesgo.",
    },
}

WORKFLOW_GUIDANCE = _load_workflow_guidance()


def read_workflow(workflow_name: str) -> Path:
    path = next(WORKFLOWS_DIR.glob(f"{workflow_name}_*.md"), None)
    if path is None:
        raise SystemExit(f"Workflow not found: {workflow_name}")
    return path


def extract_value(text: str, heading: str) -> str | None:
    pattern = rf"## {re.escape(heading)}\n`([^`]+)`"
    match = re.search(pattern, text)
    return match.group(1) if match else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a BAGO workflow for human configuration."
    )
    parser.add_argument("workflow", help="Workflow code, e.g. W1, W2, W6")
    args = parser.parse_args(argv[1:])

    workflow = args.workflow.upper()
    if workflow not in WORKFLOW_GUIDANCE:
        raise SystemExit(f"Unsupported workflow: {workflow}")

    path = read_workflow(workflow)
    text = path.read_text(encoding="utf-8")
    guidance = WORKFLOW_GUIDANCE[workflow]

    print(f"BAGO workflow inspection: {workflow}")
    print(f"File: {path}")
    print(f"ID: {extract_value(text, 'id') or 'unknown'}")
    print(f"Purpose: {guidance['purpose']}")
    print("")
    print("Context to gather:")
    for item in guidance["context"]:
        print(f"- {item}")
    print("")
    print("Questions to ask:")
    for item in guidance["questions"]:
        print(f"- {item}")
    print("")
    print("If answers are missing, do these first:")
    for item in guidance["prerequisites"]:
        print(f"- {item}")
    print("")
    print(f"Verify finality: {guidance['verify']}")
    print("")
    print("Suggested next step:")
    print(f"- If the workflow is ready, run `make workflow-tactical NAME={workflow}`")
    print("- If not, complete the prerequisite tasks above and inspect again")
    return 0



def _self_test():
    """Autotest — verifica arranque limpio y carga del catálogo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    assert isinstance(WORKFLOW_GUIDANCE, dict), "WORKFLOW_GUIDANCE no es dict"
    assert len(WORKFLOW_GUIDANCE) >= 6, f"esperados >=6 workflows, got {len(WORKFLOW_GUIDANCE)}"
    for wid in ("W1", "W2", "W3", "W4", "W5", "W6"):
        assert wid in WORKFLOW_GUIDANCE, f"{wid} no encontrado en WORKFLOW_GUIDANCE"
    print(f"  3/3 tests pasaron ({len(WORKFLOW_GUIDANCE)} workflows cargados)")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv))
