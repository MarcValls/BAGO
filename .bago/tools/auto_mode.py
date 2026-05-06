from typing import Optional
#!/usr/bin/env python3
"""
auto_mode.py — BAGO Modo Automático
Evalúa el estado actual y ejecuta los pasos coherentes sin intervención humana.

Uso (via bago script):
  python3 bago auto
  python3 bago auto --dry-run         (muestra el plan sin ejecutar nada)
  python3 bago auto --steps N         (máximo N pasos por iteración, por defecto 5)
  python3 bago auto --json            (salida machine-readable)
  python3 bago auto --loop            (bucle hasta estado estable o límite)
  python3 bago auto --loop --max-loops N  (máximo N iteraciones, por defecto 10)
  python3 bago auto --loop --infinite     (sin límite — para con Ctrl+C o al estabilizar)

O directo:
  python3 .bago/tools/auto_mode.py --dry-run
  python3 .bago/tools/auto_mode.py --loop --dry-run
"""

import hashlib
import json
import sys
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path
import os

# ─── Rutas ────────────────────────────────────────────────────────────────────
# Este archivo vive en <project>/.bago/tools/auto_mode.py
# PACK_DIR = <project>/.bago
# PROJECT_ROOT = <project>
PACK_DIR     = Path(__file__).resolve().parent.parent   # .bago/
PROJECT_ROOT = PACK_DIR.parent                           # project root (donde está el script 'bago')
STATE_DIR    = PACK_DIR / "state"
TOOLS        = PACK_DIR / "tools"

# ─── Imports directos de herramientas BAGO ───────────────────────────────────
sys.path.insert(0, str(TOOLS))
os.chdir(str(PROJECT_ROOT))   # las herramientas asumen cwd = project root

# target_selector es opcional (no disponible en todas las instalaciones)
try:
    from target_selector import choose_path as _choose_path
except ImportError:
    _choose_path = None

# ─── Selección dinámica de directorio ────────────────────────────────────────

def _load_recent_dirs() -> list[dict]:
    """Combina repo_context.json (actual) + nodos de context_map.json (recientes)."""
    entries: list[dict] = []
    seen: set[str] = set()

    # 1. Directorio actualmente configurado
    try:
        rc = json.loads((STATE_DIR / "repo_context.json").read_text())
        current = rc.get("repo_root")
        if current and Path(current).exists():
            entries.append({
                "path":       current,
                "label":      Path(current).name,
                "timestamp":  rc.get("recorded_at", ""),
                "is_current": True,
            })
            seen.add(current)
    except Exception:
        pass

    # 2. Nodos del context_map ordenados por fecha descendente
    try:
        cm    = json.loads((STATE_DIR / "context_map.json").read_text())
        nodes = sorted(
            cm.get("nodes", []),
            key=lambda n: n.get("recorded_at", "") or n.get("last_session", ""),
            reverse=True,
        )
        for node in nodes:
            mode      = node.get("working_mode", "")
            candidate = (node.get("repo_root") or node.get("path")) if mode == "external" \
                        else node.get("path")
            if not candidate or candidate in seen:
                continue
            if not Path(candidate).exists():
                continue
            ts = node.get("recorded_at", "") or node.get("last_session", "")
            entries.append({
                "path":       candidate,
                "label":      Path(candidate).name,
                "timestamp":  ts,
                "is_current": False,
            })
            seen.add(candidate)
    except Exception:
        pass

    return entries


def _pick_directory() -> "Optional[str]":
    """Muestra menú de directorios recientes y devuelve el path elegido."""
    dirs   = _load_recent_dirs()
    entries = []
    for d in dirs:
        ts = d["timestamp"][:10] if d["timestamp"] else "—"
        tag = "actual" if d["is_current"] else "reciente"
        entries.append({
            "label": f"{d['label']} [{tag}]",
            "path": d["path"],
            "reason": f"última marca: {ts}",
        })
    if _choose_path is None:
        return None
    return _choose_path(
        entries,
        title="BAGO · ¿Con qué directorio trabajamos?",
        custom_label="Ruta exacta…",
        custom_prompt="  Ruta del directorio: ",
    )


def _sync_context(target_path: str) -> bool:
    """Actualiza repo_context.json → target_path y regenera context_map."""
    target = Path(target_path).resolve()
    if not target.exists():
        print(f"  ❌ Directorio no existe: {target_path}")
        return False

    # Fingerprint consistente con repo_context_guard.py
    try:
        marker  = [str(target), str(PROJECT_ROOT.resolve())]
        marker += sorted(p.name for p in target.iterdir() if p.name != ".bago")[:200]
        fp      = hashlib.sha256("\n".join(marker).encode("utf-8")).hexdigest()
    except Exception:
        fp = ""

    working_mode = "self" if target.resolve() == PROJECT_ROOT.resolve() else "external"

    new_ctx = {
        "bago_host_root":   str(PROJECT_ROOT),
        "role":             "external_repo_pointer" if working_mode == "external" else "self",
        "working_mode":     working_mode,
        "repo_root":        str(target),
        "repo_fingerprint": fp,
        "recorded_at":      datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "note":             f"Sincronizado desde auto_mode · {target.name}",
    }

    ctx_file = STATE_DIR / "repo_context.json"
    try:
        ctx_file.write_text(json.dumps(new_ctx, indent=2, ensure_ascii=False) + "\n")
        print(f"  ✅ Contexto sincronizado → {target}")
    except Exception as e:
        print(f"  ❌ Error al guardar repo_context.json: {e}")
        return False

    print("  🔄 Regenerando context_map…")
    try:
        subprocess.run(
            [sys.executable, str(TOOLS / "context_map.py"), "--save"],
            cwd=str(PROJECT_ROOT), capture_output=True,
        )
        print("  ✅ context_map actualizado")
    except Exception:
        pass  # no bloqueante

    return True


# ─── Args ─────────────────────────────────────────────────────────────────────
def _parse():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--dry-run",    action="store_true")
    p.add_argument("--json",       action="store_true", dest="as_json")
    p.add_argument("--steps",      type=int, default=5)
    p.add_argument("--loop",       action="store_true")
    p.add_argument("--max-loops",  type=int, default=10, dest="max_loops")
    p.add_argument("--infinite",   action="store_true")
    args, _ = p.parse_known_args()
    return args

# ─── Estado ───────────────────────────────────────────────────────────────────
def _global_state():
    try:
        return json.loads((STATE_DIR / "global_state.json").read_text())
    except Exception:
        return {}

def _pending_task():
    try:
        t = json.loads((STATE_DIR / "pending_w2_task.json").read_text())
        return t if t.get("idea_title") else None
    except Exception:
        return None

def _health_score():
    try:
        from health_score import (score_integridad, score_disciplina_workflow,
                                   score_captura_decisiones, score_estado_stale,
                                   score_consistencia_inventario)
        total, max_total = 0, 0
        for fn in [score_integridad, score_disciplina_workflow,
                   score_captura_decisiones, score_estado_stale,
                   score_consistencia_inventario]:
            s, m, _ = fn()
            total += s; max_total += m
        return (total * 100 // max_total) if max_total else 0
    except Exception:
        return -1

def _detector():
    try:
        from context_detector import evaluate
        result = evaluate()
        verdict = result.get("verdict", "CLEAN")
        # context_detector returns 'score' (count of high/very_high signals)
        # and 'signals' list — align with actual schema
        high = result.get("score", 0)
        low  = len([s for s in result.get("signals", []) if s.get("weight") == "medium"])
        return verdict, high, low
    except Exception:
        return "CLEAN", 0, 0

def _validate():
    try:
        r1 = subprocess.run(
            [sys.executable, str(TOOLS / "validate_manifest.py")],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        r2 = subprocess.run(
            [sys.executable, str(TOOLS / "validate_state.py")],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        return r1.returncode == 0 and r2.returncode == 0
    except Exception:
        return False

def _stale_count():
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "stale_detector.py")],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        return sum(1 for l in r.stdout.splitlines() if "WARN" in l or "stale" in l.lower())
    except Exception:
        return 0

# ─── Decisión ─────────────────────────────────────────────────────────────────
def _decide(gs, health, verdict, high_signals, pack_ok, task, stale):
    """
    Prioridad:
      1. Pack roto          → validate (bloqueante)
      2. Health < 60        → audit
      3. Stale > 2          → stale
      4. Tarea W2 activa    → task (solo mostrar)
      5. HARVEST + high>=2  → cosecha (interactivo)
      6. HARVEST + high<2   → sugerencia sin ejecución
      7. Sin tarea          → ideas
      8. Siempre al final   → dashboard
    """
    steps = []

    if not pack_ok:
        steps.append({
            "id": "validate", "cmd": "validate",
            "label": "🔴 Pack dañado — revisar integridad",
            "reason": "validate_manifest o validate_state falla",
            "interactive": False, "blocking": True
        })
        return steps

    if health >= 0 and health < 60:
        steps.append({
            "id": "audit", "cmd": "audit",
            "label": f"🟠 Health bajo ({health}/100) — ejecutar audit",
            "reason": f"health_score = {health} < 60",
            "interactive": False, "blocking": False
        })

    if stale > 2:
        steps.append({
            "id": "stale", "cmd": "stale",
            "label": f"🟡 {stale} artefactos stale detectados",
            "reason": f"{stale} items stale en state/",
            "interactive": False, "blocking": False
        })

    if task:
        steps.append({
            "id": "task", "cmd": "task",
            "label": f"⏳ Tarea W2 activa: {task.get('idea_title','?')[:50]}",
            "reason": "pending_w2_task.json existe con tarea pendiente",
            "interactive": False, "blocking": False
        })

    if verdict == "HARVEST" and high_signals >= 2:
        steps.append({
            "id": "cosecha", "cmd": "cosecha",
            "label": "🌾 Detector W9: HARVEST — contexto listo para cosechar",
            "reason": f"detector=HARVEST con {high_signals} señales de peso alto",
            "interactive": True, "blocking": False
        })
    elif verdict == "HARVEST":
        steps.append({
            "id": "cosecha_hint", "cmd": None,
            "label": "🌾 Sugerencia: considera ejecutar bago cosecha",
            "reason": f"detector=HARVEST ({high_signals} señales altas — umbral mínimo: 2)",
            "interactive": False, "blocking": False
        })

    if not task and verdict != "HARVEST":
        steps.append({
            "id": "ideas", "cmd": "ideas",
            "label": "💡 Sin tarea activa — revisar ideas priorizadas",
            "reason": "no hay pending_w2_task.json ni problemas detectados",
            "interactive": False, "blocking": False
        })

    steps.append({
        "id": "dashboard", "cmd": "dashboard",
        "label": "📊 Dashboard — resumen del estado actual",
        "reason": "paso final de auto mode",
        "interactive": False, "blocking": False
    })

    return steps

# ─── Ejecutor ─────────────────────────────────────────────────────────────────
def _run_step(step):
    cmd = step.get("cmd")
    if not cmd:
        return True
    bago_script = PROJECT_ROOT / "bago"
    result = subprocess.run(
        [sys.executable, str(bago_script), cmd],
        cwd=str(PROJECT_ROOT)
    )
    return result.returncode == 0

def _plan_fingerprint(steps: list) -> str:
    """Hash compacto del plan activo — excluye dashboard y hints sin cmd.
    Dos planes idénticos → estado no cambió → loop estable (o atascado)."""
    actionable = [s["id"] for s in steps if s.get("cmd") not in (None, "dashboard")]
    raw = ",".join(actionable)
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:8]

# ─── Formato ──────────────────────────────────────────────────────────────────
W = 56
TOP = "╔" + "═" * W + "╗"
MID = "╠" + "═" * W + "╣"
BOT = "╚" + "═" * W + "╝"

def _box(text=""):
    return f"║  {text:<{W-2}}║"

def _health_icon(h):
    if h < 0:   return "?"
    if h >= 80: return f"✅ {h}/100"
    if h >= 60: return f"🟠 {h}/100"
    return f"🔴 {h}/100"

def _print_header(health, verdict, pack_ok, task, dry_run):
    print()
    print(TOP)
    print(_box("BAGO · Modo Automático"))
    print(MID)
    print(_box(f"  Pack:     {'✅ GO' if pack_ok else '🔴 FAIL'}"))
    print(_box(f"  Health:   {_health_icon(health)}"))
    det_map = {"HARVEST": "🌾 HARVEST", "WATCH": "👁 WATCH", "CLEAN": "✅ CLEAN"}
    print(_box(f"  Detector: {det_map.get(verdict, verdict)}"))
    t_str = ("⏳ " + task.get("idea_title","?")[:40]) if task else "—"
    print(_box(f"  Tarea:    {t_str}"))
    if dry_run:
        print(MID)
        print(_box("  ⚠️  DRY-RUN — no se ejecuta nada"))
    print(BOT)
    print()

# ─── Entry point ──────────────────────────────────────────────────────────────
def run():
    args      = _parse()
    dry_run   = args.dry_run
    as_json   = args.as_json
    max_steps = args.steps
    loop_mode = args.loop or args.infinite
    infinite  = args.infinite
    max_loops = 0 if infinite else args.max_loops  # 0 = sin límite

    # ── Selección de directorio (solo en modo interactivo, no --loop ni --json) ─
    if not as_json and not loop_mode:
        target_dir = _pick_directory()
        if target_dir is None:
            print("  ↩  Cancelado.")
            return
        print()
        if dry_run:
            print(f"  [dry-run] Se sincronizaría contexto → {target_dir}")
        else:
            if not _sync_context(target_dir):
                return
        print()

    gs = _global_state()

    # ── Modo bucle ──────────────────────────────────────────────────────────────
    if loop_mode:
        _run_loop(gs, max_steps, max_loops, dry_run)
        return

    # ── Modo normal (un solo pase) ──────────────────────────────────────────────
    health                 = _health_score()
    verdict, high, low     = _detector()
    pack_ok                = _validate()
    task                   = _pending_task()
    stale                  = _stale_count()

    steps = _decide(gs, health, verdict, high, pack_ok, task, stale)[:max_steps]

    if as_json:
        print(json.dumps({
            "state": {
                "health": health, "detector": verdict, "high_signals": high,
                "pack_ok": pack_ok,
                "pending_task": task.get("idea_title") if task else None,
                "stale": stale
            },
            "plan": [{"id": s["id"], "cmd": s.get("cmd"), "label": s["label"],
                       "interactive": s.get("interactive", False)} for s in steps],
            "dry_run": dry_run,
            "ts": datetime.now(timezone.utc).isoformat()
        }, indent=2, ensure_ascii=False))
        return

    _print_header(health, verdict, pack_ok, task, dry_run)

    print("  Plan de pasos:")
    print()
    for i, s in enumerate(steps, 1):
        icon = "→" if s.get("cmd") else "·"
        tag  = "  [requiere input]" if s.get("interactive") else ""
        print(f"  [{i}] {icon}  {s['label']}{tag}")
        print(f"       ↳ {s['reason']}")
        print()

    if dry_run:
        return

    print("─" * (W + 4))
    print()
    for i, step in enumerate(steps, 1):
        if step.get("interactive"):
            print(f"  [{i}] {step['label']}")
            ans = input("       ¿Ejecutar ahora? [S/n] ").strip().lower()
            if ans == "n":
                print("       Saltado.\n")
                continue

        if step.get("cmd"):
            print(f"  [{i}] {step['label']}")

        ok = _run_step(step)
        print()

        if not ok and step.get("blocking"):
            print("  ❌ Paso bloqueante falló — deteniendo auto mode.")
            break

    print("  ✅ Auto mode completado.")
    print()


# ─── Bucle de evolución ───────────────────────────────────────────────────────
def _run_loop(gs: dict, max_steps: int, max_loops: int, dry_run: bool) -> None:
    """Repite el ciclo de evaluación+ejecución hasta que el plan no cambie
    (estado estable), se alcance max_loops iteraciones (0 = infinito),
    o el usuario interrumpa con Ctrl+C."""

    infinite = (max_loops == 0)
    SEP = "═" * (W + 4)
    label = "∞ sin límite — Ctrl+C para detener" if infinite else f"máx {max_loops} iteraciones"
    print()
    print(SEP)
    print(f"  BAGO · Bucle de evolución  ({label})")
    if dry_run:
        print("  ⚠️  DRY-RUN — no se ejecuta nada")
    print(SEP)

    prev_fingerprint: str = ""
    stable_since:     int = 0
    actions_total:    int = 0
    start_ts = datetime.now(timezone.utc)

    def _elapsed() -> str:
        delta = datetime.now(timezone.utc) - start_ts
        mins, secs = divmod(int(delta.total_seconds()), 60)
        return f"{mins}m{secs:02d}s"

    counter = 0
    try:
        while True:
            counter += 1
            gs = _global_state()  # recarga estado en cada iteración
            iter_label = f"Iteración {counter}" if infinite else f"Iteración {counter}/{max_loops}"

            print(f"\n{'─'*40}")
            print(f"  {iter_label}  [{_elapsed()}]")
            print(f"{'─'*40}")

            # ── Re-evalúa estado ───────────────────────────────────────────────
            health             = _health_score()
            verdict, high, low = _detector()
            pack_ok            = _validate()
            task               = _pending_task()
            stale              = _stale_count()
            steps              = _decide(gs, health, verdict, high, pack_ok, task, stale)[:max_steps]

            fp         = _plan_fingerprint(steps)
            actionable = [s for s in steps if s.get("cmd") not in (None, "dashboard")]

            det_map = {"HARVEST": "🌾 HARVEST", "WATCH": "👁 WATCH", "CLEAN": "✅ CLEAN"}
            fp_tag  = "↩ igual" if fp == prev_fingerprint else "→ nuevo"
            print(f"  Health: {_health_icon(health)}  |  Detector: {det_map.get(verdict, verdict)}")
            print(f"  Pack:   {'✅ GO' if pack_ok else '🔴 FAIL'}  |  Stale: {stale}")
            print(f"  Plan:   [{fp}] {fp_tag}  |  Acciones totales: {actions_total}")
            print()

            # ── Estabilidad: plan idéntico → parar ────────────────────────────
            if fp == prev_fingerprint:
                stable_since += 1
                if stable_since >= 1 or not actionable:
                    print("  ✅ Estado estable — plan sin cambios. Bucle completado.")
                    break
            else:
                stable_since = 0
            prev_fingerprint = fp

            # ── Sin acciones → verde ───────────────────────────────────────────
            if not actionable:
                print("  ✅ Sin acciones pendientes — sistema en verde.")
                if not dry_run:
                    _run_step({"cmd": "dashboard"})
                break

            # ── Ejecutar pasos no-interactivos ────────────────────────────────
            for i, step in enumerate(steps, 1):
                if step.get("interactive"):
                    print(f"  ⏸️  Paso [{i}] requiere input humano: {step['label']}")
                    print("      → Bucle pausado. Ejecuta el paso manualmente y reinicia con bago auto --loop.")
                    _print_loop_summary(counter, actions_total, start_ts, SEP)
                    return

                if not step.get("cmd"):
                    continue

                print(f"  [{i}] {step['label']}")
                if not dry_run:
                    ok = _run_step(step)
                    actions_total += 1
                    print()
                    if not ok and step.get("blocking"):
                        print("  ❌ Paso bloqueante falló — deteniendo bucle.")
                        _print_loop_summary(counter, actions_total, start_ts, SEP)
                        return
                else:
                    print(f"       [dry-run] saltado\n")

            # ── Límite de iteraciones (solo en modo no-infinito) ───────────────
            if not infinite and counter >= max_loops:
                print(f"\n  ⚠️  Límite de {max_loops} iteraciones alcanzado sin converger.")
                print("      Revisa el estado con: bago health && bago audit")
                break

    except KeyboardInterrupt:
        print("\n\n  🛑 Interrumpido por el usuario (Ctrl+C)")

    _print_loop_summary(counter, actions_total, start_ts, SEP)


def _print_loop_summary(iterations: int, actions: int, start_ts, sep: str) -> None:
    delta = datetime.now(timezone.utc) - start_ts
    mins, secs = divmod(int(delta.total_seconds()), 60)
    elapsed = f"{mins}m{secs:02d}s"
    print()
    print(sep)
    print(f"  Resumen: {iterations} iteraciones · {actions} acciones ejecutadas · {elapsed}")
    print(sep)
    print()
if __name__ == '__main__':
    run()
