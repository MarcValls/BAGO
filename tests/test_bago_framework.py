#!/usr/bin/env python3
"""test_bago_framework.py — Tests del framework BAGO.

Valida:
  - bago_locate: detecta fuente de verdad correctamente
  - bago_orchestrator: selecciona modelo óptimo por tarea
  - bago_dynamic_router: enruta a agente/rol/herramienta
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "tools"))

from bago_locate import locate_bago
from bago_orchestrator import orchestrate
from bago_dynamic_router import dynamic_route


def test_locate():
    loc = locate_bago()
    assert loc["source"] in ("pc", "usb", "both", "none"), "Fuente inválida"
    assert loc["primary_path"] is not None, "Debe detectar primary"
    assert loc["mode"] in ("installed", "portable", "first_time"), "Modo inválido"
    print(f"[OK] locate: {loc['message']}")


def test_orchestrator_simple():
    r = orchestrate("brainstorm ideas")
    assert "error" not in r, f"Error: {r}"
    # En Codex CLI: tareas simples -> gratis local
    assert r["cost"] in ("free", "included"), f"Tarea simple no debería costar: {r['cost']}"
    print(f"[OK] orchestrator simple: {r['model']} ({r['cost']})")


def test_orchestrator_complex():
    r = orchestrate("implementar login en varios archivos")
    assert "error" not in r
    # Tareas complejas -> Codex
    assert r["provider"] in ("codex", "copilot"), f"Compleja debería ir a Codex: {r['provider']}"
    assert r["model"] != "gpt-5.5", f"No debería elegir frontier si hay alternativa: {r['model']}"
    print(f"[OK] orchestrator complex: {r['model']} ({r['provider']})")


def test_router():
    r = dynamic_route("transponer partitura de piano")
    assert r["task_type"] == "music", f"Tipo incorrecto: {r['task_type']}"
    assert r["role"] == "GENERADOR_Contenido", f"Rol incorrecto: {r['role']}"
    assert len(r["primary_tools"]) > 0, "Debe devolver herramientas"
    assert r["confidence"] >= 60, f"Confianza baja: {r['confidence']}"
    print(f"[OK] router: {r['agent']} -> {r['role']} -> {r['model']} ({r['confidence']}%)")


def main():
    print("BAGO Framework Tests")
    print("-" * 40)
    test_locate()
    test_orchestrator_simple()
    test_orchestrator_complex()
    test_router()
    print("-" * 40)
    print("All tests PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

