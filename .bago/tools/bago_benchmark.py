#!/usr/bin/env python3
"""
bago_benchmark.py — Banco de pruebas de eficiencia BAGO (10 minutos).

Ejecuta una batería de comandos BAGO en rotación durante DURATION_SECONDS
(defecto: 600s = 10 min) y recoge métricas de rendimiento.

Métricas recogidas por comando:
  - latencia: min / avg / p95 / max (segundos)
  - tasa de éxito (exit code 0)
  - throughput: ejecuciones / minuto
  - output: bytes de salida media

Reporte final:
  - Tabla de resultados por comando
  - Score de eficiencia BAGO (0-100)
  - Recomendaciones SAC si hay comandos lentos o con fallos

Uso:
  python3 bago_benchmark.py                 # 10 minutos, todo
  python3 bago_benchmark.py --duration 60   # prueba rápida de 1 minuto
  python3 bago_benchmark.py --suite fast    # solo comandos rápidos
  python3 bago_benchmark.py --suite full    # suite completa (más lento)
  python3 bago_benchmark.py --json          # output JSON para pipelines
  python3 bago_benchmark.py --no-progress   # sin barra de progreso
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE  = Path(__file__).resolve().parent
_BAGO  = _HERE.parent
_ROOT  = _BAGO.parent
_BAGO_BIN = _ROOT / "bago"
_TOOLS = _BAGO / "tools"
_STATE = _BAGO / "state"

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ── BAGO Presence ─────────────────────────────────────────────────────────────
def _load_bp():
    try:
        spec = importlib.util.spec_from_file_location("bago_presence", _TOOLS / "bago_presence.py")
        mod  = importlib.util.module_from_spec(spec)    # type: ignore
        spec.loader.exec_module(mod)                    # type: ignore
        return mod.bp
    except Exception:
        class _Null:
            def __getattr__(self, _): return lambda *a, **k: None
        return _Null()

bp = _load_bp()

# ── Suites de comandos ────────────────────────────────────────────────────────

# Comandos rápidos (target < 2s cada uno)
SUITE_FAST: list[dict] = [
    {"id": "health",       "cmd": [str(_BAGO_BIN), "health"],                         "target_s": 2.0,  "weight": 3},
    {"id": "validate",     "cmd": [str(_BAGO_BIN), "validate"],                       "target_s": 2.0,  "weight": 3},
    {"id": "status",       "cmd": [str(_BAGO_BIN), "status"],                         "target_s": 1.0,  "weight": 2},
    {"id": "registry",     "cmd": [str(_BAGO_BIN), "registry"],                       "target_s": 1.5,  "weight": 2},
    {"id": "start_quiet",  "cmd": [sys.executable, str(_TOOLS / "bago_start.py"), "--quiet"], "target_s": 3.0, "weight": 2},
    {"id": "guard_audit",  "cmd": [sys.executable, str(_TOOLS / "agent_static_guard.py"), "--audit"], "target_s": 1.0, "weight": 1},
]

# Comandos medianos (target 2-5s)
SUITE_MEDIUM: list[dict] = [
    {"id": "sincerity",    "cmd": [str(_BAGO_BIN), "sincerity"],                      "target_s": 5.0,  "weight": 2},
    {"id": "stability",    "cmd": [str(_BAGO_BIN), "stability"],                      "target_s": 5.0,  "weight": 2},
    {"id": "ideas_top",    "cmd": [sys.executable, str(_TOOLS / "emit_ideas.py"), "--top", "3"], "target_s": 3.0, "weight": 1},
    {"id": "intent_route", "cmd": [sys.executable, str(_TOOLS / "intent_router.py"), "--test"], "target_s": 3.0, "weight": 1},
]

# Suite completa
SUITE_FULL = SUITE_FAST + SUITE_MEDIUM

SUITES: dict[str, list[dict]] = {
    "fast":   SUITE_FAST,
    "medium": SUITE_MEDIUM,
    "full":   SUITE_FULL,
}

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    cmd_id:     str
    duration_s: float
    exit_code:  int
    output_len: int
    timestamp:  float = field(default_factory=time.monotonic)


@dataclass
class CmdStats:
    cmd_id:      str
    runs:        int = 0
    successes:   int = 0
    failures:    int = 0
    durations:   list[float] = field(default_factory=list)
    output_lens: list[int]   = field(default_factory=list)
    target_s:    float = 2.0
    weight:      int = 1

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs > 0 else 0.0

    @property
    def avg_s(self) -> float:
        return statistics.mean(self.durations) if self.durations else 0.0

    @property
    def min_s(self) -> float:
        return min(self.durations) if self.durations else 0.0

    @property
    def max_s(self) -> float:
        return max(self.durations) if self.durations else 0.0

    @property
    def p95_s(self) -> float:
        if len(self.durations) < 2:
            return self.max_s
        sorted_d = sorted(self.durations)
        idx = max(0, int(len(sorted_d) * 0.95) - 1)
        return sorted_d[idx]

    @property
    def avg_output(self) -> float:
        return statistics.mean(self.output_lens) if self.output_lens else 0.0

    @property
    def throughput(self) -> float:
        """Ejecuciones por minuto."""
        if not self.durations:
            return 0.0
        total_time = sum(self.durations)
        return (self.runs / total_time) * 60 if total_time > 0 else 0.0

    @property
    def efficiency_score(self) -> float:
        """Score 0-100: combina success_rate + latencia vs target."""
        if self.runs == 0:
            return 0.0
        latency_score = max(0.0, 1.0 - (self.avg_s / (self.target_s * 2)))
        return round((self.success_rate * 0.6 + latency_score * 0.4) * 100, 1)


# ── Ejecutor de comandos ───────────────────────────────────────────────────────

def run_command(cmd: list[str], timeout: float = 30.0) -> RunResult:
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "BAGO_PLAIN": "1"},  # sin ANSI en output recogido
        )
        duration = time.monotonic() - t0
        output_len = len(result.stdout) + len(result.stderr)
        return RunResult(
            cmd_id="",
            duration_s=round(duration, 4),
            exit_code=result.returncode,
            output_len=output_len,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return RunResult(cmd_id="", duration_s=round(duration, 4), exit_code=-1, output_len=0)
    except Exception as e:
        duration = time.monotonic() - t0
        return RunResult(cmd_id="", duration_s=round(duration, 4), exit_code=-2, output_len=0)


# ── Barra de progreso ─────────────────────────────────────────────────────────

def _progress_bar(elapsed: float, total: float, width: int = 40) -> str:
    pct = min(elapsed / total, 1.0)
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    mins_left = max(0, int((total - elapsed) / 60))
    secs_left = max(0, int((total - elapsed) % 60))
    return f"  [{bar}] {pct*100:5.1f}%  ⏱  {mins_left:02d}:{secs_left:02d} restantes"


# ── Motor de benchmark ────────────────────────────────────────────────────────

class Benchmark:
    def __init__(
        self,
        suite: list[dict],
        duration_s: int = 600,
        show_progress: bool = True,
        show_json: bool = False,
    ) -> None:
        self.suite        = suite
        self.duration_s   = duration_s
        self.show_progress= show_progress
        self.show_json    = show_json
        self.stats        = {c["id"]: CmdStats(c["id"], target_s=c["target_s"], weight=c["weight"])
                             for c in suite}
        self.results: list[RunResult] = []
        self._cmd_idx     = 0

    def _next_cmd(self) -> dict:
        """Round-robin ponderado por weight."""
        weighted = []
        for c in self.suite:
            weighted.extend([c] * c["weight"])
        cmd = weighted[self._cmd_idx % len(weighted)]
        self._cmd_idx += 1
        return cmd

    def run(self) -> dict:
        t_start = time.monotonic()
        t_end   = t_start + self.duration_s

        bp.voice_enter("VALIDADOR", gate="BENCHMARK")
        bp.voice_line(f"duración: {self.duration_s}s  ·  {len(self.suite)} comandos en rotación")
        bp.voice_line(f"suite: {', '.join(c['id'] for c in self.suite)}")
        bp.voice_exit()
        print()

        last_progress = 0.0

        while time.monotonic() < t_end:
            elapsed = time.monotonic() - t_start
            cmd_def = self._next_cmd()
            cmd_id  = cmd_def["id"]

            # Ejecutar
            r = run_command(cmd_def["cmd"], timeout=min(30.0, cmd_def["target_s"] * 3))
            r.cmd_id = cmd_id

            # Acumular stats
            s = self.stats[cmd_id]
            s.runs += 1
            s.durations.append(r.duration_s)
            s.output_lens.append(r.output_len)
            if r.exit_code == 0:
                s.successes += 1
            else:
                s.failures += 1

            self.results.append(r)

            # Log en tiempo real (solo si hay cambio relevante)
            ok_s = "✓" if r.exit_code == 0 else "✗"
            status = f"{ok_s} {cmd_id:<15} {r.duration_s:.3f}s"
            if self.show_progress:
                bar = _progress_bar(elapsed, self.duration_s)
                # Actualizar barra cada 5 segundos
                if elapsed - last_progress >= 5 or r.exit_code != 0:
                    sys.stdout.write(f"\r{bar}   {status}  ")
                    sys.stdout.flush()
                    last_progress = elapsed
            else:
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{ts}] {status}")

        elapsed_total = time.monotonic() - t_start
        if self.show_progress:
            sys.stdout.write("\n")

        return self._compute_report(elapsed_total)

    def _compute_report(self, elapsed_s: float) -> dict:
        total_runs   = sum(s.runs for s in self.stats.values())
        total_ok     = sum(s.successes for s in self.stats.values())
        throughput   = (total_runs / elapsed_s) * 60 if elapsed_s > 0 else 0

        # Score global (media ponderada de scores por cmd)
        total_weight = sum(s.weight for s in self.stats.values())
        global_score = sum(
            s.efficiency_score * s.weight for s in self.stats.values()
        ) / total_weight if total_weight > 0 else 0.0

        return {
            "meta": {
                "timestamp":    datetime.now(timezone.utc).isoformat(),
                "duration_s":   round(elapsed_s, 1),
                "suite_size":   len(self.suite),
                "bago_version": _read_version(),
            },
            "summary": {
                "total_runs":       total_runs,
                "total_ok":         total_ok,
                "total_failures":   total_runs - total_ok,
                "success_rate_pct": round((total_ok / total_runs) * 100, 1) if total_runs else 0,
                "throughput_rpm":   round(throughput, 2),
                "efficiency_score": round(global_score, 1),
            },
            "commands": {
                cid: {
                    "runs":         s.runs,
                    "success_rate": round(s.success_rate * 100, 1),
                    "avg_s":        round(s.avg_s, 3),
                    "min_s":        round(s.min_s, 3),
                    "max_s":        round(s.max_s, 3),
                    "p95_s":        round(s.p95_s, 3),
                    "target_s":     s.target_s,
                    "throughput_rpm": round(s.throughput, 1),
                    "avg_output_bytes": round(s.avg_output),
                    "efficiency_score": s.efficiency_score,
                    "status": (
                        "LENTO"   if s.avg_s > s.target_s * 1.5 else
                        "OK"      if s.success_rate >= 0.95 else
                        "FALLOS"
                    ),
                }
                for cid, s in self.stats.items()
            },
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_version() -> str:
    try:
        gstate = _STATE / "global_state.json"
        if gstate.exists():
            d = json.loads(gstate.read_text(encoding="utf-8"))
            return d.get("bago_version", "?")
    except Exception:
        pass
    return "?"


def _print_report(report: dict) -> None:
    meta = report["meta"]
    summ = report["summary"]
    cmds = report["commands"]

    score = summ["efficiency_score"]
    score_icon = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"

    bp.header(f"BENCHMARK · {meta['duration_s']}s completados")

    # ── Resumen global ─────────────────────────────────────────────────────
    bp.voice_enter("VALIDADOR", gate="REPORTE")
    bp.voice_line(f"Ejecuciones totales : {summ['total_runs']}")
    bp.voice_line(f"Éxitos              : {summ['total_ok']}  ({summ['success_rate_pct']}%)")
    bp.voice_line(f"Fallos              : {summ['total_failures']}")
    bp.voice_line(f"Throughput          : {summ['throughput_rpm']} cmd/min")
    bp.voice_line(f"Score de eficiencia : {score}/100  {score_icon}")
    bp.voice_line(f"Versión BAGO        : {meta['bago_version']}")
    bp.voice_exit()

    # ── Tabla por comando ──────────────────────────────────────────────────
    print(f"\n  {'Comando':<18} {'Runs':>5} {'OK%':>6} {'avg':>6} {'p95':>6} {'max':>6} {'target':>7}  Estado")
    print(f"  {'─'*18} {'─'*5} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*7}  ──────")

    for cid, c in sorted(cmds.items(), key=lambda x: -x[1]["efficiency_score"]):
        status_icon = "✓" if c["status"] == "OK" else ("⚡" if c["status"] == "LENTO" else "✗")
        avg_s  = c["avg_s"]
        p95_s  = c["p95_s"]
        max_s  = c["max_s"]
        tgt    = c["target_s"]
        flag   = " ⚠" if avg_s > tgt * 1.5 else ""
        print(
            f"  {cid:<18} {c['runs']:>5} {c['success_rate']:>5.1f}%"
            f" {avg_s:>5.3f}s {p95_s:>5.3f}s {max_s:>5.3f}s {tgt:>6.1f}s"
            f"  {status_icon} {c['status']}{flag}"
        )

    print()

    # ── Recomendaciones ────────────────────────────────────────────────────
    slow  = [cid for cid, c in cmds.items() if c["avg_s"] > c["target_s"] * 1.5]
    fails = [cid for cid, c in cmds.items() if c["success_rate"] < 90]

    if slow or fails:
        bp.act("ANALISTA", "detectando cuellos de botella")
        if slow:
            for cid in slow:
                c = cmds[cid]
                bp.think(f"[LENTO] {cid}: avg {c['avg_s']:.3f}s > target {c['target_s']}s  → revisar I/O")
        if fails:
            for cid in fails:
                c = cmds[cid]
                bp.think(f"[FALLO] {cid}: {c['success_rate']:.1f}% éxito  → revisar dependencias")
    else:
        bp.act("ANALISTA", "todos los comandos dentro de rangos óptimos")

    print()

    # ── Guardar resultado ──────────────────────────────────────────────────
    out_path = _STATE / "benchmark_last.json"
    try:
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        bp.think(f"reporte guardado: {out_path}")
    except Exception as e:
        bp.think(f"no se pudo guardar reporte: {e}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="bago_benchmark.py — Banco de pruebas de eficiencia BAGO"
    )
    parser.add_argument("--duration",    type=int, default=600, metavar="SECS",
                        help="Duración en segundos (defecto: 600 = 10 min)")
    parser.add_argument("--suite",       choices=["fast", "medium", "full"], default="fast",
                        help="Suite de comandos a ejecutar (defecto: fast)")
    parser.add_argument("--json",        action="store_true",
                        help="Output JSON al finalizar (además del reporte)")
    parser.add_argument("--no-progress", action="store_true",
                        help="Sin barra de progreso (modo CI/log)")
    args = parser.parse_args()

    suite   = SUITES[args.suite]
    show_p  = not args.no_progress and sys.stdout.isatty()

    bp.header(f"BENCHMARK · iniciando")
    bp.act("MAESTRO", f"suite: {args.suite}  ·  duración: {args.duration}s  ·  {len(suite)} comandos")
    bp.think(f"inicio: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    print()

    bench  = Benchmark(suite, duration_s=args.duration, show_progress=show_p)
    report = bench.run()

    _print_report(report)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["summary"]["success_rate_pct"] >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
