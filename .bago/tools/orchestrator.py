#!/usr/bin/env python3
"""orchestrator.py — Orquestador de workflows BAGO multi-tool.

BAGO como sistema de gobernanza necesita ejecutar múltiples tools
en secuencia, con condiciones, dependencias y resumen final.

El orquestador define workflows predefinidos y permite crear workflows
ad-hoc encadenando tools. Es la diferencia entre un toolbox y un sistema.

Workflows predefinidos:
  preprod      → commit-ready + lint + secret-scan + type-check + ci-report
  security     → secret-scan + dep-audit + api-check
  quality      → lint + complexity + dead-code + naming-check + doc-coverage
  selfcheck    → tool-guardian + pre-push
  onboarding   → doctor + tool-guardian + metrics
  full         → todo (10+ scanners, puede tardar)

Uso:
    python3 orchestrator.py preprod              # workflow pre-producción
    python3 orchestrator.py security             # auditoría seguridad
    python3 orchestrator.py quality              # calidad completa
    python3 orchestrator.py selfcheck            # chequeo del framework
    python3 orchestrator.py run lint complexity  # workflow ad-hoc
    python3 orchestrator.py --list               # lista workflows
    python3 orchestrator.py --dry-run preprod    # previsualiza sin ejecutar
    python3 orchestrator.py --fail-fast preprod  # para en el primer error
    python3 orchestrator.py preprod              # registra memoria espiral 3 voces
    python3 orchestrator.py --no-spiral preprod  # desactiva memoria espiral
    python3 orchestrator.py --test               # self-tests

Códigos: ORC-I001 (workflow OK), ORC-W001 (tool con warnings),
         ORC-E001 (tool falló), ORC-E002 (workflow desconocido)
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import sys
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_SCRIPT = PROJECT_ROOT / "bago"
SPIRAL_LOG = BAGO_ROOT / "logs" / "routing_spiral_memory.jsonl"
SPHERE_STATE = BAGO_ROOT / "logs" / "routing_sphere_state.json"
VOICE_LABELS = ("v1_reasoning", "v2_prepare", "v3_execute")
SPHERE_SLOTS = 24


WORKFLOWS = {
    "preprod": {
        "name": "Pre-Producción",
        "description": "Valida que el código esté listo para producción",
        "steps": [
            {"cmd": "commit-ready", "critical": True,  "label": "Preparación para commit"},
            {"cmd": "lint",         "critical": False, "label": "Calidad y estilo"},
            {"cmd": "secret-scan",  "critical": True,  "label": "Secretos hardcodeados"},
            {"cmd": "type-check",   "critical": False, "label": "Type hints"},
            {"cmd": "ci-report",    "critical": False, "label": "Reporte CI unificado"},
        ],
        "success_msg": "✅ Código listo para producción",
        "fail_msg": "❌ No está listo para producción — revisa los errores críticos",
    },
    "security": {
        "name": "Auditoría de Seguridad",
        "description": "Escaneo completo de superficie de ataque",
        "steps": [
            {"cmd": "secret-scan", "critical": True,  "label": "Secretos hardcodeados"},
            {"cmd": "dep-audit",   "critical": True,  "label": "Dependencias vulnerables"},
            {"cmd": "api-check",   "critical": False, "label": "Contratos de API"},
        ],
        "success_msg": "✅ Sin vulnerabilidades detectadas",
        "fail_msg": "❌ Vulnerabilidades encontradas — revisar antes de deploy",
    },
    "quality": {
        "name": "Calidad Completa",
        "description": "Análisis integral de calidad del código",
        "steps": [
            {"cmd": "lint",         "critical": False, "label": "Estilo y linting"},
            {"cmd": "complexity",   "critical": False, "label": "Complejidad ciclomática"},
            {"cmd": "dead-code",    "critical": False, "label": "Código muerto"},
            {"cmd": "naming-check", "critical": False, "label": "Convenciones de nombres"},
            {"cmd": "doc-coverage", "critical": False, "label": "Cobertura de docstrings"},
            {"cmd": "dup-check",    "critical": False, "label": "Bloques duplicados"},
        ],
        "success_msg": "✅ Calidad aceptable",
        "fail_msg": "⚠️  Problemas de calidad detectados",
    },
    "selfcheck": {
        "name": "Chequeo del Framework BAGO",
        "description": "Verifica la coherencia interna del framework",
        "steps": [
            {"cmd": "tool-guardian", "critical": True,  "label": "Coherencia de tools"},
            {"cmd": "pre-push",      "critical": False, "label": "Checklist pre-push"},
        ],
        "success_msg": "✅ Framework coherente",
        "fail_msg": "⚠️  Framework necesita atención",
    },
    "onboarding": {
        "name": "Onboarding / Primera Revisión",
        "description": "Primer análisis de un proyecto nuevo",
        "steps": [
            {"cmd": "doctor",       "critical": False, "label": "Diagnóstico general"},
            {"cmd": "tool-guardian","critical": False, "label": "Estado del framework"},
            {"cmd": "metrics",      "critical": False, "label": "Métricas actuales"},
            {"cmd": "hotspot",      "critical": False, "label": "Archivos de riesgo"},
        ],
        "success_msg": "✅ Onboarding completado",
        "fail_msg": "⚠️  Proyecto necesita trabajo antes de onboarding completo",
    },
    "full": {
        "name": "Auditoría Completa",
        "description": "Todos los scanners (puede tardar varios minutos)",
        "steps": [
            {"cmd": "lint",          "critical": False, "label": "Linting"},
            {"cmd": "complexity",    "critical": False, "label": "Complejidad"},
            {"cmd": "dead-code",     "critical": False, "label": "Código muerto"},
            {"cmd": "secret-scan",   "critical": True,  "label": "Secretos"},
            {"cmd": "dep-audit",     "critical": True,  "label": "Dependencias"},
            {"cmd": "type-check",    "critical": False, "label": "Type hints"},
            {"cmd": "naming-check",  "critical": False, "label": "Nombres"},
            {"cmd": "doc-coverage",  "critical": False, "label": "Docs"},
            {"cmd": "readme-check",  "critical": False, "label": "README"},
            {"cmd": "ci-report",     "critical": False, "label": "CI Report"},
        ],
        "success_msg": "✅ Auditoría completa — sin errores críticos",
        "fail_msg": "❌ Errores críticos detectados",
    },
}


def build_dynamic_workflow(context_text: str, threshold: float = 0.25, top_n: int = 5) -> dict:
    """Construye un workflow dinámico desde texto de contexto usando NeuralToolbox.

    Delega la selección de herramientas a neural_toolbox.NeuralToolbox.activate(),
    que deriva perfiles del registry y filtra por scope/risk/deprecated.

    Retorna un dict compatible con WORKFLOWS (mismo schema que workflows predefinidos).
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_neural_toolbox", str(BAGO_ROOT / "tools" / "neural_toolbox.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        toolbox = mod.NeuralToolbox()
        activations = toolbox.activate(context_text, threshold=threshold, top_n=top_n)
    except Exception as e:
        return {
            "name": "Dynamic (error)",
            "description": f"Error cargando NeuralToolbox: {e}",
            "steps": [],
            "success_msg": "⚠️  No se pudo construir el workflow dinámico",
            "fail_msg": "❌ Error en NeuralToolbox",
        }

    steps = [
        {
            "cmd":      a.cmd,
            "critical": False,
            "label":    a.description[:40] or a.cmd,
            "_score":   a.score,
        }
        for a in activations
    ]

    return {
        "name": f"Dynamic — '{context_text[:40]}'",
        "description": (
            f"Workflow generado dinámicamente por NeuralToolbox "
            f"({len(steps)} herramientas activadas, threshold={threshold})"
        ),
        "steps":       steps,
        "success_msg": f"✅ Workflow dinámico completado ({len(steps)} herramientas)",
        "fail_msg":    "⚠️  Algunas herramientas del workflow dinámico fallaron",
    }


def run_tool(cmd: str, dry_run: bool = False, timeout: int = 90) -> dict:
    """Ejecuta bago <cmd> y captura resultado."""
    start = time.time()
    if dry_run:
        return {"cmd": cmd, "rc": 0, "output": f"[DRY] bago {cmd}", "elapsed": 0.0}
    try:
        result = subprocess.run(
            [str(BAGO_SCRIPT), cmd],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=timeout
        )
        elapsed = time.time() - start
        return {
            "cmd": cmd, "rc": result.returncode,
            "output": (result.stdout + result.stderr).strip(),
            "elapsed": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "rc": 1, "output": f"TIMEOUT ({timeout}s)", "elapsed": timeout}
    except Exception as e:
        return {"cmd": cmd, "rc": 1, "output": str(e), "elapsed": 0.0}


def _load_recent_spiral_events(limit: int = 80) -> list[dict]:
    if not SPIRAL_LOG.exists():
        return []
    try:
        lines = SPIRAL_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out: list[dict] = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _resolve_context_for_cmd(cmd: str) -> dict | None:
    """Busca contexto previo útil para el comando en memoria espiral."""
    events = _load_recent_spiral_events(limit=160)
    for ev in reversed(events):
        voices = ev.get("voices", {})
        v1 = voices.get("v1_reasoning", {})
        if v1.get("cmd") == cmd:
            return {
                "source": "spiral",
                "last_ts": ev.get("ts"),
                "workflow": ev.get("workflow"),
                "harmonic_score": ev.get("validation", {}).get("harmonic_score"),
            }
    return None


def _load_sphere_state() -> dict:
    if not SPHERE_STATE.exists():
        return {
            "schema": "bago.routing-sphere.v1",
            "cursor": 0,
            "slots": SPHERE_SLOTS,
            "memory": {},
        }
    try:
        return json.loads(SPHERE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema": "bago.routing-sphere.v1",
            "cursor": 0,
            "slots": SPHERE_SLOTS,
            "memory": {},
        }


def _save_sphere_state(state: dict) -> None:
    SPHERE_STATE.parent.mkdir(parents=True, exist_ok=True)
    SPHERE_STATE.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def _compute_voice_positions(base_slot: int, slots: int) -> dict:
    """3 voces desfasadas 120 grados sobre la esfera discreta."""
    offsets = (0, slots // 3, (2 * slots) // 3)
    return {
        VOICE_LABELS[i]: (base_slot + offsets[i]) % slots
        for i in range(3)
    }


def _project_context_snapshot(workflow_name: str, cmd: str) -> dict:
    """Voz 1: razonamiento de la petición dentro del contexto actual."""
    previous = _resolve_context_for_cmd(cmd)
    if previous is None:
        context_status = "created"
        context_payload = {
            "source": "synthetic",
            "reason": "no habia contexto previo; se crea contexto base",
        }
    else:
        context_status = "reused"
        context_payload = previous

    return {
        "workflow": workflow_name,
        "cmd": cmd,
        "project_root": str(PROJECT_ROOT),
        "bago_script": str(BAGO_SCRIPT),
        "context_hint": f"{workflow_name}:{cmd}",
        "context_status": context_status,
        "context": context_payload,
    }


def _prepare_artifacts_snapshot(cmd: str, critical: bool, timeout: int) -> dict:
    """Voz 2: preparación de entorno y artefactos antes de ejecutar."""
    tool_path = BAGO_ROOT / "tools" / f"{cmd}.py"
    return {
        "cmd": cmd,
        "critical": critical,
        "timeout": timeout,
        "tool_exists": tool_path.exists(),
        "tool_path": str(tool_path),
        "manifest_exists": (BAGO_ROOT / "tools.manifest.json").exists(),
        "bago_exists": BAGO_SCRIPT.exists(),
    }


def _harmonic_validation(voice1: dict, voice2: dict, voice3: dict, step_index: int) -> dict:
    """Valida alineación entre voces con un offset tipo bucle Shepard."""
    detune_cycle = [0, 7, -5]
    detune = detune_cycle[(step_index - 1) % len(detune_cycle)]

    aligned = True
    if voice1.get("cmd") != voice2.get("cmd"):
        aligned = False
    if voice2.get("cmd") != voice3.get("cmd"):
        aligned = False
    if not voice2.get("bago_exists", False):
        aligned = False

    # Armonía simple: base 1.0 cuando todo alinea, con caída por código de salida.
    rc = int(voice3.get("rc", 1))
    score = 1.0 if aligned and rc == 0 else (0.66 if aligned else 0.33)

    return {
        "aligned": aligned,
        "detune_cents": detune,
        "harmonic_score": score,
    }


def _memory_action_for_step(voice1: dict, harmony: dict, result: dict) -> str:
    """Decide acción de memoria: write, rewrite o delete."""
    if voice1.get("context_status") == "created":
        return "write"
    if int(result.get("rc", 1)) == 0 and harmony.get("aligned"):
        return "rewrite"
    return "delete"


def _append_spiral_event(event: dict) -> None:
    """Persistencia append-only de memoria de enrutamiento."""
    SPIRAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPIRAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")


def _record_spiral_triplet(workflow_name: str, step_num: int, total: int,
                           step: dict, result: dict, timeout: int) -> None:
    """Registra las 3 voces + validación armónica para un paso."""
    voice1 = _project_context_snapshot(workflow_name, step["cmd"])
    voice2 = _prepare_artifacts_snapshot(step["cmd"], step["critical"], timeout)
    voice3 = {
        "cmd": result["cmd"],
        "rc": result["rc"],
        "elapsed": result.get("elapsed", 0.0),
        "dry_run": result.get("output", "").startswith("[DRY]"),
    }
    harmony = _harmonic_validation(voice1, voice2, voice3, step_num)
    action = _memory_action_for_step(voice1, harmony, result)

    sphere = _load_sphere_state()
    slots = int(sphere.get("slots", SPHERE_SLOTS)) or SPHERE_SLOTS
    cursor = int(sphere.get("cursor", 0))
    positions = _compute_voice_positions(cursor, slots)
    memory = sphere.setdefault("memory", {})
    if action == "delete":
        memory.pop(step["cmd"], None)
    else:
        memory[step["cmd"]] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "workflow": workflow_name,
            "action": action,
            "harmonic_score": harmony.get("harmonic_score", 0.0),
        }
    sphere["cursor"] = (cursor + 1) % slots
    _save_sphere_state(sphere)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "schema": "bago.spiral-routing.v2",
        "workflow": workflow_name,
        "step": step_num,
        "total_steps": total,
        "sphere": {
            "slot": cursor,
            "voice_positions": positions,
            "action": action,
            "slots": slots,
        },
        "voices": {
            "v1_reasoning": voice1,
            "v2_prepare": voice2,
            "v3_execute": voice3,
        },
        "validation": harmony,
    }
    _append_spiral_event(event)


def print_step_header(step_num: int, total: int, label: str, cmd: str):
    pct = int(step_num / total * 100)
    bar_len = 20
    filled = int(bar_len * step_num / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  [{bar}] {pct:3d}%  Paso {step_num}/{total}: {label}")
    print(f"  ▶ bago {cmd}")
    print("  " + "─" * 54)


def print_step_result(result: dict, critical: bool):
    rc = result["rc"]
    elapsed = result["elapsed"]
    if rc == 0:
        print(f"  ✅ OK  ({elapsed:.1f}s)")
    else:
        tag = "❌ ERROR" if critical else "⚠️  WARN"
        print(f"  {tag}  ({elapsed:.1f}s)")
    # Print last few lines of output
    lines = result["output"].splitlines()
    if lines:
        for line in lines[-5:]:
            print(f"     {line}")


def run_workflow(workflow: dict, dry_run: bool = False, fail_fast: bool = False,
                 verbose: bool = False, spiral: bool = True, timeout: int = 90) -> dict:
    steps = workflow["steps"]
    total = len(steps)
    step_results = []
    critical_failed = False

    print(f"\n  {'━' * 54}")
    print(f"  BAGO Orchestrator — {workflow['name']}")
    print(f"  {workflow['description']}")
    print(f"  {'━' * 54}")

    for i, step in enumerate(steps, 1):
        print_step_header(i, total, step["label"], step["cmd"])
        result = run_tool(step["cmd"], dry_run=dry_run, timeout=timeout)
        print_step_result(result, step["critical"])
        step_results.append({**step, **result})

        if spiral:
            _record_spiral_triplet(workflow["name"], i, total, step, result, timeout)

        if result["rc"] != 0 and step["critical"]:
            critical_failed = True
            if fail_fast:
                print(f"\n  [ORC-E001] ⚡ FAIL-FAST: paso crítico falló. Abortando.")
                break

    # Summary
    print(f"\n  {'━' * 54}")
    passed = sum(1 for r in step_results if r["rc"] == 0)
    failed = sum(1 for r in step_results if r["rc"] != 0)
    total_time = sum(r.get("elapsed", 0) for r in step_results)
    print(f"  Resultado: {passed}/{len(step_results)} pasos OK  |  {total_time:.1f}s total")
    print()

    for r in step_results:
        icon = "✅" if r["rc"] == 0 else ("❌" if r["critical"] else "⚠️ ")
        print(f"    {icon}  {r['label']:30s}  bago {r['cmd']}")

    print()
    if critical_failed:
        print(f"  {workflow['fail_msg']}")
    else:
        print(f"  {workflow['success_msg']}")
    print()

    return {
        "workflow": workflow["name"],
        "passed": passed, "failed": failed,
        "critical_failed": critical_failed,
        "steps": step_results,
    }


def run_adhoc(commands: list, dry_run: bool = False, fail_fast: bool = False) -> int:
    """Ejecuta un workflow ad-hoc con los comandos dados."""
    workflow = {
        "name": "Workflow Ad-hoc",
        "description": f"Comandos: {' → '.join(commands)}",
        "steps": [{"cmd": c, "critical": False, "label": c} for c in commands],
        "success_msg": "✅ Workflow completado",
        "fail_msg": "⚠️  Algunos pasos fallaron",
    }
    result = run_workflow(workflow, dry_run=dry_run, fail_fast=fail_fast)
    return 1 if result["critical_failed"] else 0


def cmd_list():
    print(f"\n  BAGO Workflows ({len(WORKFLOWS)})")
    print("  " + "─" * 56)
    for name, wf in WORKFLOWS.items():
        steps_str = " → ".join(s["cmd"] for s in wf["steps"])
        print(f"  {name:12s}  {wf['description']}")
        print(f"              [{steps_str}]")
        print()


def run_tests():
    results = []

    # Test 1: WORKFLOWS dict has required fields
    required = {"name", "description", "steps", "success_msg", "fail_msg"}
    ok1 = all(required.issubset(wf.keys()) for wf in WORKFLOWS.values())
    results.append(("orchestrator:workflows_schema", ok1, f"count={len(WORKFLOWS)}"))

    # Test 2: all steps have required fields
    step_required = {"cmd", "critical", "label"}
    ok2 = all(
        step_required.issubset(step.keys())
        for wf in WORKFLOWS.values()
        for step in wf["steps"]
    )
    results.append(("orchestrator:steps_schema", ok2, ""))

    # Test 3: run_tool dry-run returns expected structure
    r = run_tool("lint", dry_run=True)
    ok3 = r["rc"] == 0 and "cmd" in r and "output" in r
    results.append(("orchestrator:dry_run_structure", ok3, f"rc={r['rc']}"))

    # Test 4: preprod workflow has at least one critical step
    preprod = WORKFLOWS["preprod"]
    ok4 = any(s["critical"] for s in preprod["steps"])
    results.append(("orchestrator:preprod_has_critical", ok4, ""))

    # Test 5: run_workflow dry-run returns result dict
    result = run_workflow(WORKFLOWS["selfcheck"], dry_run=True)
    ok5 = isinstance(result, dict) and "passed" in result and "failed" in result
    results.append(("orchestrator:workflow_returns_dict", ok5,
                     f"passed={result.get('passed')} failed={result.get('failed')}"))

    # Test 6: all workflow commands are non-empty strings
    ok6 = all(
        isinstance(step["cmd"], str) and len(step["cmd"]) > 0
        for wf in WORKFLOWS.values()
        for step in wf["steps"]
    )
    results.append(("orchestrator:all_cmds_nonempty", ok6, ""))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "✅" if ok else "❌"
        print(f"  {status}  {name}: {detail}")
    print(f"\n  {passed}/{len(results)} pasaron")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        raise SystemExit(0)

    if "--test" in args:
        raise SystemExit(run_tests())

    if "--list" in args:
        cmd_list()
        raise SystemExit(0)

    dry_run = "--dry-run" in args
    fail_fast = "--fail-fast" in args
    verbose = "--verbose" in args or "-v" in args
    spiral = "--no-spiral" not in args

    clean_args = [a for a in args if not a.startswith("--")]

    if not clean_args:
        print("  Usa: orchestrator.py <workflow|run> [cmds...]")
        print("  Workflows: " + ", ".join(WORKFLOWS.keys()))
        raise SystemExit(1)

    if clean_args[0] == "run":
        cmds = clean_args[1:]
        if not cmds:
            print("  Uso: orchestrator.py run cmd1 cmd2 ...")
            raise SystemExit(1)
        raise SystemExit(run_adhoc(cmds, dry_run=dry_run, fail_fast=fail_fast))

    # Dynamic workflow from natural language context
    if clean_args[0] == "dynamic":
        context = " ".join(clean_args[1:])
        if not context:
            print("  Uso: orchestrator.py dynamic \"texto describiendo el trabajo\"")
            raise SystemExit(1)
        wf = build_dynamic_workflow(context)
        if not wf["steps"]:
            print("  [ORC-W001] Sin herramientas activadas para este contexto.")
            print("  Prueba con más palabras clave: security, lint, test, workflow...")
            raise SystemExit(0)
        result = run_workflow(
            wf,
            dry_run=dry_run,
            fail_fast=fail_fast,
            verbose=verbose,
            spiral=spiral,
        )
        raise SystemExit(1 if result["critical_failed"] else 0)

    workflow_name = clean_args[0]
    if workflow_name not in WORKFLOWS:
        print(f"  [ORC-E002] Workflow desconocido: '{workflow_name}'")
        print(f"  Disponibles: {', '.join(WORKFLOWS.keys())} + dynamic")
        raise SystemExit(1)

    result = run_workflow(
        WORKFLOWS[workflow_name],
        dry_run=dry_run,
        fail_fast=fail_fast,
        verbose=verbose,
        spiral=spiral,
    )
    raise SystemExit(1 if result["critical_failed"] else 0)
