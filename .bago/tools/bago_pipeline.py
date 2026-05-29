#!/usr/bin/env python3
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
"""bago_pipeline.py — Orquestación en segundo plano: Router -> Ejecutor -> Reviewer -> Consenso.

Uso:
  python bago_pipeline.py "tarea aquí" [--output resultado.json]

Fases:
  1. Router: bago_dynamic_router clasifica tarea -> agente + modelo + rol + tools
  2. Ejecutor: lanza CLI silencioso (gh copilot / ollama / codex proxy) con timeout
  3. Reviewer: segundo modelo revisa output del ejecutor
  4. Consenso: valida contra agent_contract.json y genera resultado final
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from bago_dynamic_router import dynamic_route
from bago_adaptive_engine import adaptive_timeout, agent_score, record_execution, print_adaptive_summary

STATE_DIR = TOOLS_DIR.parent / "state"
AGENTS_DIR = TOOLS_DIR.parent / "agents"
CONTRACT_FILE = AGENTS_DIR / "agent_contract.json"
GH_PATHS = [
    Path.home() / "AppData" / "Local" / "Programs" / "GitHub CLI" / "gh.exe",
    Path("C:/Program Files/GitHub CLI/gh.exe"),
]


def find_gh() -> str | None:
    try:
        r = subprocess.run(["gh", "--version"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return "gh"
    except Exception:
        pass
    for p in GH_PATHS:
        if p.exists():
            return str(p)
    return None


def _run_gh_copilot(prompt: str, timeout: int = 25) -> dict:
    """Ejecuta gh copilot en segundo plano silencioso."""
    gh = find_gh()
    if not gh:
        return {"success": False, "output": "", "error": "gh CLI no encontrado", "duration_ms": 0}
    out_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False)
    err_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False)
    out_file.close()
    err_file.close()
    try:
        start = time.time()
        proc = subprocess.Popen(
            [gh, "copilot", "--", "-p", prompt, "--silent", "--allow-all-tools", "--stream", "off"],
            stdout=open(out_file.name, "w", encoding="utf-8"),
            stderr=open(err_file.name, "w", encoding="utf-8"),
            text=True,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "output": "", "error": f"timeout {timeout}s", "duration_ms": int((time.time()-start)*1000)}
        duration_ms = int((time.time() - start) * 1000)
        with open(out_file.name, "r", encoding="utf-8", errors="ignore") as f:
            stdout = f.read().strip()
        with open(err_file.name, "r", encoding="utf-8", errors="ignore") as f:
            stderr = f.read().strip()
        success = proc.returncode == 0 and len(stdout) > 0
        return {
            "success": success,
            "output": stdout,
            "error": stderr if not success else "",
            "duration_ms": duration_ms,
            "exit_code": proc.returncode,
        }
    finally:
        try:
            os.unlink(out_file.name)
            os.unlink(err_file.name)
        except Exception:
            pass


def _run_ollama(model: str, prompt: str, timeout: int = 30) -> dict:
    """Ejecuta ollama run en segundo plano silencioso."""
    out_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False)
    err_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False)
    out_file.close()
    err_file.close()
    try:
        start = time.time()
        proc = subprocess.Popen(
            ["ollama", "run", model, prompt],
            stdout=open(out_file.name, "w", encoding="utf-8"),
            stderr=open(err_file.name, "w", encoding="utf-8"),
            text=True,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "output": "", "error": f"timeout {timeout}s", "duration_ms": int((time.time()-start)*1000)}
        duration_ms = int((time.time() - start) * 1000)
        with open(out_file.name, "r", encoding="utf-8", errors="ignore") as f:
            stdout = f.read().strip()
        with open(err_file.name, "r", encoding="utf-8", errors="ignore") as f:
            stderr = f.read().strip()
        success = proc.returncode == 0 and len(stdout) > 0
        return {
            "success": success,
            "output": stdout,
            "error": stderr if not success else "",
            "duration_ms": duration_ms,
            "exit_code": proc.returncode,
        }
    finally:
        try:
            os.unlink(out_file.name)
            os.unlink(err_file.name)
        except Exception:
            pass


def _execute(agent: str, model: str, prompt: str, timeout: int = 25) -> dict:
    """Ejecuta el agente/modelo adecuado en segundo plano."""
    if agent in ("copilot", "codex"):
        # Codex no se puede lanzar desde dentro de Codex -> proxy vía gh copilot
        return _run_gh_copilot(prompt, timeout)
    elif agent in ("ollama", "ollama-local"):
        return _run_ollama(model, prompt, timeout)
    else:
        return {"success": False, "output": "", "error": f"Agente no soportado: {agent}", "duration_ms": 0}


def _review(output: str, original_task: str, reviewer_agent: str = "copilot", reviewer_model: str = "claude-sonnet-4.6", timeout: int = 20) -> dict:
    """Fase 3: Reviewer revisa el output del ejecutor principal."""
    prompt = (
        f"Revisa el siguiente resultado generado para la tarea: '{original_task}'.\n\n"
        f"RESULTADO:\n{output[:2000]}\n\n"
        "Evalúa: ¿Es correcto? ¿Completo? ¿Hay errores? Responde en 1-3 líneas."
    )
    return _execute(reviewer_agent, reviewer_model, prompt, timeout=timeout)


def _validate_contract(result: dict) -> dict:
    """Fase 4: Valida contra agent_contract.json."""
    try:
        contract = json.loads(CONTRACT_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"valid": False, "issues": ["No se pudo leer agent_contract.json"]}

    issues = []
    required = contract.get("definitions", {}).get("AgentResult", {}).get("required", [])
    for field in required:
        if field not in result:
            issues.append(f"Falta campo requerido: {field}")

    return {"valid": len(issues) == 0, "issues": issues}



def _get_timeouts(task_type: str, agent: str) -> tuple[int, int]:
    """Devuelve timeouts adaptativos basados en historial real."""
    base = {
        "content": 20, "brainstorm": 20, "music": 120,
        "code": 50, "debug": 45, "quality": 40,
        "architecture": 60, "coordination": 35,
    }.get(task_type, 40)
    exec_t = adaptive_timeout(task_type, agent, base * 1000) // 1000
    review_t = max(15, exec_t * 2 // 3)
    return (exec_t, review_t)


def run_pipeline(task: str) -> dict:
    """Ejecuta pipeline completo de 4 fases con timeouts adaptativos."""
    start_total = time.time()

    # FASE 1: Router + Orquestador
    route = dynamic_route(task)
    agent = route["agent"]
    model = route["model"]
    provider = route["provider"]
    task_type = route["task_type"]

    # Timeouts adaptativos segun tipo de tarea
    exec_timeout, review_timeout = _get_timeouts(task_type, agent)

    print(f"  [Fase 1/4] Router -> {agent} | {model} | confianza {route['confidence']}%")
    print_adaptive_summary(task_type, agent)
    print(f"  Timeouts: exec={exec_timeout}s review={review_timeout}s")

    # FASE 2: Ejecutor principal
    print(f"  [Fase 2/4] Ejecutando principal [{model}]...")
    exec_result = _execute(agent, model, task, timeout=exec_timeout)
    if not exec_result["success"]:
        print(f"    WARN Principal fallo: {exec_result['error']}")
        # Fallback a copilot
        print(f"    -> Fallback a copilot...")
        exec_result = _execute("copilot", "claude-sonnet-4.6", task, timeout=max(45, exec_timeout))

    if exec_result["success"]:
        print(f"    OK Output: {exec_result['output'][:120]}...")
    else:
        print(f"    FAIL Error: {exec_result['error']}")
    record_execution(task, task_type, agent, model, exec_result['success'], exec_result.get('duration_ms', 0), exec_result.get('error',''))

    # FASE 3: Reviewer
    print(f"  [Fase 3/4] Reviewer revisando output...")
    reviewer = "copilot" if agent != "copilot" else "ollama-local"
    reviewer_model = "claude-sonnet-4.6" if reviewer == "copilot" else "qwen2.5:0.5b"
    review_result = _review(exec_result.get("output", ""), task, reviewer, reviewer_model, timeout=review_timeout)
    if review_result["success"]:
        print(f"    OK Review: {review_result['output'][:120]}...")
    else:
        print(f"    WARN Review no disponible: {review_result['error']}")
    record_execution(task, task_type, reviewer, reviewer_model, review_result['success'], review_result.get('duration_ms', 0), review_result.get('error',''))

    # FASE 4: Consenso + Validacion
    print(f"  [Fase 4/4] Consenso y validacion...")
    final_output = exec_result.get("output", "")
    review_text = review_result.get("output", "") if review_result["success"] else "Review no disponible"

    consensus = {
        "task": task,
        "success": exec_result["success"],
        "intent": route["task_type"],
        "output": final_output,
        "review": review_text,
        "adapter": agent,
        "model": model,
        "provider": provider,
        "role": route["role"],
        "confidence": route["confidence"],
        "duration_ms": int((time.time() - start_total) * 1000),
        "cost_hint": "included" if agent in ("copilot", "codex") else "free/local",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "neural_event_id": f"pipe_{int(time.time())}",
        "error": exec_result.get("error", ""),
        "phases": {
            "router": route,
            "executor": exec_result,
            "reviewer": review_result,
        },
    }

    validation = _validate_contract(consensus)
    consensus["contract_valid"] = validation["valid"]
    consensus["contract_issues"] = validation["issues"]

    print(f"    OK Consenso: {'VALIDO' if validation['valid'] else 'CON ISSUES'}")
    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"      ! {issue}")

    return consensus
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BAGO Pipeline Orchestrator")
    parser.add_argument("task", help="Tarea a orquestar")
    parser.add_argument("--output", help="Archivo JSON para guardar resultado")
    args = parser.parse_args()

    print(f"\n  [BAGO Pipeline] Orquestando en segundo plano...")
    print(f"  Tarea: {args.task}\n")

    result = run_pipeline(args.task)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Resultado guardado: {args.output}")
    else:
        print(f"\n  Resultado final (consenso):")
        print(f"  Éxito: {result['success']}")
        print(f"  Output: {result['output'][:200]}...")
        print(f"  Review: {result['review'][:200]}...")
        print(f"  Contract válido: {result['contract_valid']}")
        print(f"  Duración: {result['duration_ms']}ms\n")






