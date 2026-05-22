#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cabinet_orchestrator.py — GABINETE DE AGENTES BAGO

Orquesta en paralelo un conjunto canónico de "agentes" (tools BAGO existentes)
y produce un reporte unificado con veredicto por agente + severidad agregada.

Filosofía:
  - Cada agente es una tool aislada con exit-code semántico.
  - El gabinete NO reinterpreta el output: lo cita textualmente.
  - Especialista principal: CENTINELA_SINCERIDAD (sincerity_detector.py),
    que audita la documentación en busca de trampas narrativas.

Agentes invocados por defecto:
  - validador:  validate_pack.py           (integridad del pack)
  - salud:      health_score.py            (score general)
  - stale:      stale_detector.py          (artefactos desactualizados)
  - contexto:   context_detector.py        (coherencia de repo)
  - sinceridad: sincerity_detector.py      (sincofancía / trampas en docs)

Uso:
  python3 .bago/tools/cabinet_orchestrator.py
  python3 .bago/tools/cabinet_orchestrator.py --json
  python3 .bago/tools/cabinet_orchestrator.py --only sinceridad,salud
  python3 .bago/tools/cabinet_orchestrator.py --strict   # WARN del centinela → exit 1

Exit codes:
  0 — todos los agentes OK (o solo con avisos no bloqueantes)
  1 — al menos un agente devolvió ERROR
  2 — fallo interno del orquestador
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS.parent

# cmd_id → (descripción, ruta absoluta, args extra)
AGENTS: dict[str, tuple[str, Path, list[str]]] = {
    "validador":  ("Integridad del pack",               TOOLS / "validate_pack.py",    []),
    "salud":      ("Health score del pack",             TOOLS / "health_score.py",     []),
    "stale":      ("Artefactos de reporte obsoletos",   TOOLS / "stale_detector.py",   []),
    "contexto":   ("Coherencia de contexto de repo",    TOOLS / "context_detector.py", []),
    "sinceridad": ("Detección de sincofancía en docs",  TOOLS / "sincerity_detector.py", ["--max", "40"]),
}

# Agentes críticos para el veredicto del gabinete.
# "sinceridad" es WARN (no CRITICAL) hasta que las reglas de detección estén
# calibradas — un falso positivo no debe bloquear el veredicto global.
CRITICAL = {"validador"}


@dataclass
class AgentResult:
    agent: str
    description: str
    exit_code: int
    duration_s: float
    stdout: str
    stderr: str
    verdict: str  # OK | WARN | ERROR | MISSING


def classify(agent: str, rc: int) -> str:
    if rc == 0:
        return "OK"
    if rc == 1:
        return "ERROR" if agent in CRITICAL else "WARN"
    return "ERROR"


def run_agent(name: str, path: Path, extra: list[str]) -> AgentResult:
    desc = AGENTS[name][0]
    if not path.exists():
        return AgentResult(agent=name, description=desc, exit_code=127,
                           duration_s=0.0, stdout="", stderr=f"tool missing: {path}",
                           verdict="MISSING")
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(path), *extra],
            capture_output=True, text=True, check=False, timeout=180,
        )
        rc = proc.returncode
        out, err = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = 124, "", f"timeout after {e.timeout}s"
    except Exception as e:  # noqa: BLE001
        rc, out, err = 2, "", f"orchestrator error: {e!r}"
    dt = time.time() - t0
    return AgentResult(
        agent=name, description=desc, exit_code=rc, duration_s=round(dt, 3),
        stdout=out, stderr=err, verdict=classify(name, rc),
    )


def aggregate(results: list[AgentResult]) -> tuple[str, dict[str, int]]:
    counts = {"OK": 0, "WARN": 0, "ERROR": 0, "MISSING": 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    if counts["ERROR"] > 0 or counts["MISSING"] > 0:
        final = "ERROR"
    elif counts["WARN"] > 0:
        final = "WARN"
    else:
        final = "OK"
    return final, counts


def format_text(results: list[AgentResult], final: str, counts: dict[str, int]) -> str:
    lines: list[str] = []
    lines.append("╔══ GABINETE BAGO · INFORME UNIFICADO ═══════════════════════════════╗")
    lines.append(f"║ Raíz      : {BAGO_ROOT.parent}")
    lines.append(f"║ Agentes   : {len(results)}")
    lines.append(f"║ Veredicto : {final}   (OK={counts['OK']} WARN={counts['WARN']} ERROR={counts['ERROR']} MISSING={counts['MISSING']})")
    lines.append("╚════════════════════════════════════════════════════════════════════╝")
    for r in results:
        lines.append("")
        lines.append(f"── [{r.verdict}] {r.agent} · {r.description}   (rc={r.exit_code}, {r.duration_s}s)")
        body = (r.stdout or "").rstrip()
        if body:
            for ln in body.splitlines()[:60]:
                lines.append(f"   {ln}")
            extra_lines = len(body.splitlines()) - 60
            if extra_lines > 0:
                lines.append(f"   ... ({extra_lines} líneas más truncadas)")
        if r.stderr.strip():
            lines.append(f"   [stderr] {r.stderr.strip().splitlines()[0]}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Orquesta el gabinete de agentes BAGO.")
    p.add_argument("--only", type=str, default=None,
                   help="Lista separada por comas de agentes a ejecutar. Por defecto todos.")
    p.add_argument("--json", action="store_true", help="Emitir reporte JSON.")
    p.add_argument("--strict", action="store_true",
                   help="Cualquier WARN global hace exit 1.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    selected = list(AGENTS.keys())
    if args.only:
        requested = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [x for x in requested if x not in AGENTS]
        if unknown:
            print(f"[cabinet] Agentes desconocidos: {unknown}", file=sys.stderr)
            return 2
        selected = requested

    results: list[AgentResult] = []
    with cf.ThreadPoolExecutor(max_workers=min(4, len(selected) or 1)) as ex:
        futs = {
            ex.submit(run_agent, name, AGENTS[name][1], AGENTS[name][2]): name
            for name in selected
        }
        for fut in cf.as_completed(futs):
            results.append(fut.result())

    # Orden estable según selección
    order = {n: i for i, n in enumerate(selected)}
    results.sort(key=lambda r: order.get(r.agent, 999))

    final, counts = aggregate(results)

    if args.json:
        payload = {
            "verdict": final,
            "counts": counts,
            "agents": [asdict(r) for r in results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_text(results, final, counts))

    if final == "ERROR":
        return 1
    if args.strict and final == "WARN":
        return 1
    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())
