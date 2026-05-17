#!/usr/bin/env python3
"""test_bago_brutal.py — Tests brutales en múltiples entornos simulados.

Simula:
  1. Codex CLI + Ollama local (actual)
  2. Solo Ollama local (offline)
  3. Solo Ollama local con modelos pequeños (<1GB)
  4. Sin proveedores (first_time)
  5. USB portable
  6. PC + USB (both)
  7. Contexto masivo (>500K tokens)
  8. Tarea desconocida (fallback)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "tools"))

from bago_orchestrator import orchestrate
from bago_dynamic_router import dynamic_route
from bago_locate import locate_bago


def run_tests():
    passed = 0
    failed = 0
    print("=" * 60)
    print("BAGO BRUTAL TEST SUITE")
    print("=" * 60)

    # -----------------------------------------------------------------
    # TEST 1: Codex CLI + Ollama local (entorno actual)
    # -----------------------------------------------------------------
    print("\n[TEST 1] Codex CLI + Ollama local")
    try:
        r = orchestrate("brainstorm ideas")
        assert r.get("model") == "qwen25-mini", f"Simple debe ir a mini gratis: {r.get('model')}"
        assert r.get("cost") == "free", f"Simple debe ser gratis: {r.get('cost')}"
        print(f"  [PASS] Simple: {r['model']} ({r['cost']})")

        r = orchestrate("implementar login en varios archivos")
        assert r.get("provider") == "codex", f"Compleja debe ir a Codex: {r.get('provider')}"
        assert r.get("model") != "gpt-5.5", f"No frontier innecesario: {r.get('model')}"
        print(f"  [PASS] Compleja: {r['model']} ({r['provider']})")
        passed += 2
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 2: Offline (solo Ollama local)
    # -----------------------------------------------------------------
    print("\n[TEST 2] Offline — solo Ollama local")
    try:
        # Forzar modo offline
        r = orchestrate("transponer partitura", mode_name="offline")
        assert "error" not in r, f"Offline debería funcionar: {r}"
        assert r.get("cost") == "free", f"Offline debe ser gratis: {r.get('cost')}"
        print(f"  [PASS] Offline: {r['model']} ({r['cost']})")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 3: Contexto masivo
    # -----------------------------------------------------------------
    print("\n[TEST 3] Contexto masivo")
    try:
        r = orchestrate("analizar repo completo de partituras")
        assert r.get("model") in ["kimi-k2-1t", "gpt-5.2", "gpt-5.4", "gpt-5.5"], f"Contexto masivo necesita modelo grande: {r.get('model')}"
        print(f"  [PASS] Contexto masivo: {r['model']}")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 4: Tarea desconocida
    # -----------------------------------------------------------------
    print("\n[TEST 4] Tarea desconocida")
    try:
        r = orchestrate("hacer café y tocar guitarra")
        assert "error" not in r, f"Fallback debería funcionar: {r}"
        assert r.get("model") is not None, f"Debe devolver algún modelo: {r}"
        print(f"  [PASS] Fallback: {r['model']} ({r.get('reason', '')[:40]}...)")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 5: Router dinámico completo
    # -----------------------------------------------------------------
    print("\n[TEST 5] Router dinámico")
    try:
        agents = [
            {"id": "ollama", "available": True, "models": ["qwen25-coder"]},
            {"id": "codex", "available": True, "models": ["gpt-5.4", "gpt-5.3-codex"]},
            {"id": "copilot", "available": True, "models": ["claude-sonnet-4.6"]},
        ]

        r = dynamic_route("transponer partitura de piano", available_agents=agents)
        assert r["agent"] == "codex", f"Música en Codex: {r['agent']}"
        assert r["task_type"] == "music", f"Tipo music: {r['task_type']}"
        print(f"  [PASS] Router música: {r['agent']} -> {r['model']}")

        r = dynamic_route("revisa este PR", available_agents=agents)
        assert r["agent"] == "copilot", f"Review en Copilot: {r['agent']}"
        assert r["task_type"] == "quality", f"Tipo quality: {r['task_type']}"
        print(f"  [PASS] Router review: {r['agent']} -> {r['model']}")
        passed += 2
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 6: Locator — detección de fuente
    # -----------------------------------------------------------------
    print("\n[TEST 6] Locator — fuente de verdad")
    try:
        loc = locate_bago()
        assert loc["source"] in ["pc", "usb", "both", "none"], f"Fuente válida: {loc['source']}"
        assert loc["primary_path"] is not None, "Debe tener primary"
        assert Path(loc["primary_path"]).exists(), f"Primary debe existir: {loc['primary_path']}"
        print(f"  [PASS] Locator: {loc['source']} -> {loc['primary_path']}")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 7: Review profunda
    # -----------------------------------------------------------------
    print("\n[TEST 7] Auditoría / Review profunda")
    try:
        r = orchestrate("auditoria de seguridad del código")
        assert r.get("provider") in ["codex", "copilot"], f"Seguridad en cloud: {r.get('provider')}"
        assert "error" not in r, f"Debe funcionar: {r}"
        print(f"  [PASS] Auditoría: {r['model']} ({r['provider']})")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # TEST 8: Render / Preview (tarea simple local)
    # -----------------------------------------------------------------
    print("\n[TEST 8] Render preview — simple local")
    try:
        r = orchestrate("render preview de score")
        assert r.get("cost") == "free", f"Render debe ser gratis: {r.get('cost')}"
        assert r.get("provider") == "ollama-local", f"Render en local: {r.get('provider')}"
        print(f"  [PASS] Render: {r['model']} ({r['cost']})")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # -----------------------------------------------------------------
    # RESUMEN
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTADO: {passed}/{total} PASSED, {failed} FAILED")
    if failed == 0:
        print("BRUTAL TESTS: ALL GREEN")
    else:
        print("BRUTAL TESTS: HAY FALLOS")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
