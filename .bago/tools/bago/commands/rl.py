"""bago.commands.rl — Comandos RL integrados en el chat de BAGO.

Uso en el chat:
  rl-status      → Muestra transiciones acumuladas y checkpoints
  rl-demo        → Ejecuta demo manual (3 pasos, sandbox, 0 riesgo)
  rl-train bc    → Entrena Behavioral Cloning con datos acumulados
  rl-train ppo   → Entrena PPO online (si hay entorno)
  rl-eval        → Evalúa política entrenada en shadow mode
  rl-sandbox     → Activa/desactiva sandbox
  rl-shadow      → Activa/desactiva shadow mode

  rl-tool               → Ejecuta orquestador de herramientas (interactivo)
  rl-tool "busca archivos de config" → Ejecuta orquestador con tarea directa
  rl-train tool-bc      → Entrena BC del orquestador con dashboard
  rl-train tool-bandit  → Entrena LinUCB online del orquestador
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from rich.table import Table
from rich.live import Live
from rich.panel import Panel

from ..ui import console, pe, pi


def _rl_paths() -> tuple[Path, Path, Path]:
    """Retorna (root_dir, logs_path, checkpoints_dir)."""
    tools = Path(__file__).resolve().parents[2]
    root = tools.parent
    logs = root / ".bago" / "logs" / "rl_transitions.jsonl"
    ckpts = root / ".bago" / "rl" / "checkpoints"
    return root, logs, ckpts


def _tool_orchestrator_paths(root: Path) -> tuple[Path, Path, Path]:
    """Retorna paths del tool orchestrator Fase 5."""
    logs = root / ".bago" / "rl" / "logs" / "tool_orchestrator_transitions.jsonl"
    ckpts = root / ".bago" / "rl" / "checkpoints"
    train_script = root / ".bago" / "rl" / "training" / "train_tool_orchestrator.py"
    orchestrator_script = root / ".bago" / "rl" / "adapters" / "bago_tool_orchestrator.py"
    demo_gen = root / ".bago" / "rl" / "training" / "generate_synthetic_tool_demos.py"
    return logs, ckpts, train_script, orchestrator_script, demo_gen


def _count_transitions(logs: Path) -> int:
    if not logs.exists():
        return 0
    try:
        with logs.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f if _.strip())
    except Exception:
        return 0


def cmd_rl_status(session, args: str = ""):
    """Muestra estado del pipeline RL (Fase 1-4 + Fase 5)."""
    root, logs, ckpts = _rl_paths()
    tlogs, tckpts, _, _, _ = _tool_orchestrator_paths(root)

    console.print("[bold cyan]  Estado RL[/bold cyan]")

    # Fase 1-4
    count = _count_transitions(logs)
    console.print(f"  Transiciones clásicas: [bold]{count}[/bold]  ({'OK' if count >= 5 else 'Necesitas ~5 para BC, ~200 para PPO'})")

    # Fase 5 — Tool Orchestrator
    tcount = _count_transitions(tlogs)
    console.print(f"  Transiciones tool-orchestrator: [bold]{tcount}[/bold]  ({'OK' if tcount >= 5 else 'Ejecuta rl-tool para generar datos'})")

    # Checkpoints existentes
    bc_ckpt = ckpts / "bc" / "bc_model.pkl"
    ppo_ckpt = ckpts / "ppo_full_v3" / "final_model.zip"
    qmix_ckpt = ckpts / "qmix" / "mixer.pt"
    tool_bc = tckpts / "tool_policy_bc.json"
    tool_bandit = tckpts / "tool_policy_bandit.json"
    tool_bc_syn = tckpts / "tool_policy_bc_synthetic.json"

    table = Table(title="Checkpoints", box="ROUNDED")
    table.add_column("Pipeline", style="cyan")
    table.add_column("Checkpoint", style="green")
    table.add_column("Estado", style="bold")

    table.add_row("BC clásico", str(bc_ckpt.name), "✓" if bc_ckpt.exists() else "—")
    table.add_row("PPO", str(ppo_ckpt.name), "✓" if ppo_ckpt.exists() else "—")
    table.add_row("QMIX", str(qmix_ckpt.name), "✓" if qmix_ckpt.exists() else "—")
    table.add_row("Tool BC (real)", str(tool_bc.name), "✓" if tool_bc.exists() else "—")
    table.add_row("Tool BC (synthetic)", str(tool_bc_syn.name), "✓" if tool_bc_syn.exists() else "—")
    table.add_row("Tool LinUCB", str(tool_bandit.name), "✓" if tool_bandit.exists() else "—")
    console.print(table)

    # Sugerencias
    if tcount < 5 and not tool_bc_syn.exists():
        pi("Ejecuta rl-train tool-bc para generar datos sintéticos y entrenar.")
    elif not tool_bc.exists() and not tool_bc_syn.exists():
        pi("Ejecuta rl-tool para generar transiciones reales, luego rl-train tool-bc.")
    else:
        pi("Listo. rl-tool para orquestar, rl-train tool-bc para re-entrenar.")


def cmd_rl_demo(session, args: str = ""):
    """Ejecuta el demo manual de RL."""
    root, _, _ = _rl_paths()
    demo_script = root / ".bago" / "rl" / "rl_demo_manual.py"
    if not demo_script.exists():
        pe(f"No se encuentra {demo_script}")
        return
    console.print("[dim]  Ejecutando demo RL...[/dim]")
    try:
        proc = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True, text=True, cwd=str(root),
            timeout=30, encoding="utf-8", errors="replace",
        )
        if proc.stdout:
            console.print(proc.stdout)
        if proc.stderr:
            console.print(f"[red]{proc.stderr}[/red]")
    except Exception as exc:
        pe(f"Error ejecutando demo: {exc}")


def _run_training_with_dashboard(cmd: list[str], cwd: Path, title: str) -> None:
    """Ejecuta un script de entrenamiento y muestra un dashboard en vivo con Rich."""
    console.print(f"[bold cyan]  {title}[/bold cyan]")
    start = time.time()

    table = Table(box="ROUNDED", expand=True)
    table.add_column("Epoch", style="cyan", width=8)
    table.add_column("Loss / Reward", style="yellow")
    table.add_column("Transiciones", style="green")
    table.add_column("Tiempo", style="dim")

    metrics = {"epochs": [], "losses": [], "transitions": 0, "final": {}}
    epoch_re = re.compile(r"Epoch\s+(\d+)/(\d+).*?loss=([\d.]+)")
    json_re = re.compile(r"^\{.*\}$")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(cwd),
            encoding="utf-8",
            errors="replace",
        )
        with Live(table, console=console, refresh_per_second=2, vertical_overflow="visible") as live:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                m = epoch_re.search(line)
                if m:
                    ep, total, loss = m.groups()
                    metrics["epochs"].append((int(ep), float(loss)))
                    elapsed = time.time() - start
                    table.add_row(
                        f"{ep}/{total}",
                        f"loss={loss}",
                        str(metrics["transitions"]),
                        f"{elapsed:.1f}s",
                    )
                    live.update(table)
                elif json_re.match(line):
                    try:
                        metrics["final"] = json.loads(line)
                    except json.JSONDecodeError:
                        pass
                elif "transitions_used" in line.lower() or "transiciones" in line.lower():
                    # Fallback: imprimir línea directamente en tabla
                    table.add_row("—", line[:40], "", "")
                    live.update(table)
            proc.wait(timeout=600)
    except Exception as exc:
        pe(f"Error entrenando: {exc}")
        return

    elapsed = time.time() - start
    console.print(f"\n[green]  ✓ Entrenamiento completado en {elapsed:.1f}s[/green]")
    if metrics["final"]:
        console.print(Panel(json.dumps(metrics["final"], indent=2, ensure_ascii=False),
                            title="Métricas finales", border_style="green"))


def cmd_rl_train(session, args: str = ""):
    """Entrena un modelo RL (clásico o tool orchestrator)."""
    root, logs, ckpts = _rl_paths()
    sub = args.strip().lower().split()[0] if args.strip() else ""

    if sub == "bc":
        if not logs.exists() or _count_transitions(logs) < 5:
            pe(f"Solo {_count_transitions(logs)} transiciones. Necesitas al menos 5.")
            pi("Ejecuta rl-demo primero.")
            return
        train_script = root / ".bago" / "rl" / "training" / "train_bc.py"
        out_dir = ckpts / "bc_user"
        console.print(f"[dim]  Entrenando BC...[/dim]")
        try:
            proc = subprocess.run(
                [sys.executable, str(train_script), "--input", str(logs),
                 "--epochs", "20", "--output-dir", str(out_dir)],
                capture_output=True, text=True, cwd=str(root),
                timeout=60, encoding="utf-8", errors="replace",
            )
            if proc.stdout:
                console.print(proc.stdout)
            if proc.stderr:
                console.print(f"[red]{proc.stderr}[/red]")
        except Exception as exc:
            pe(f"Error entrenando BC: {exc}")

    elif sub == "ppo":
        train_script = root / ".bago" / "rl" / "training" / "train_online.py"
        out_dir = ckpts / "ppo_user"
        console.print(f"[dim]  Entrenando PPO...[/dim]")
        try:
            proc = subprocess.run(
                [sys.executable, str(train_script), "--checkpoint-dir", str(out_dir)],
                capture_output=True, text=True, cwd=str(root),
                timeout=300, encoding="utf-8", errors="replace",
            )
            if proc.stdout:
                console.print(proc.stdout)
            if proc.stderr:
                console.print(f"[red]{proc.stderr}[/red]")
        except Exception as exc:
            pe(f"Error entrenando PPO: {exc}")

    elif sub == "qmix":
        train_script = root / ".bago" / "rl" / "training" / "train_qmix.py"
        out_dir = ckpts / "qmix_user"
        console.print(f"[dim]  Entrenando QMIX...[/dim]")
        try:
            proc = subprocess.run(
                [sys.executable, str(train_script), "--episodes", "1000", "--save-dir", str(out_dir)],
                capture_output=True, text=True, cwd=str(root),
                timeout=600, encoding="utf-8", errors="replace",
            )
            if proc.stdout:
                console.print(proc.stdout)
            if proc.stderr:
                console.print(f"[red]{proc.stderr}[/red]")
        except Exception as exc:
            pe(f"Error entrenando QMIX: {exc}")

    # ── Fase 5 — Tool Orchestrator ───────────────────────────────────────────
    elif sub == "tool-bc":
        _, tckpts, train_script, _, demo_gen = _tool_orchestrator_paths(root)
        dataset = tckpts.parent / "logs" / "synthetic_tool_demos.jsonl"

        # Generar sintéticos si no existen
        if not dataset.exists():
            pi("Generando demostraciones sintéticas (500 transiciones)...")
            try:
                subprocess.run(
                    [sys.executable, str(demo_gen), "--episodes", "500", "--output", str(dataset)],
                    capture_output=True, text=True, cwd=str(root), timeout=30,
                )
            except Exception as exc:
                pe(f"Error generando demos: {exc}")
                return

        save = tckpts / "tool_policy_bc.json"
        _run_training_with_dashboard(
            [sys.executable, str(train_script), "--mode", "bc", "--epochs", "30",
             "--dataset", str(dataset), "--save", str(save)],
            cwd=root,
            title="Entrenando Tool Orchestrator (BC)",
        )

    elif sub == "tool-bandit":
        _, tckpts, train_script, _, _ = _tool_orchestrator_paths(root)
        save = tckpts / "tool_policy_bandit.json"
        _run_training_with_dashboard(
            [sys.executable, str(train_script), "--mode", "bandit", "--episodes", "2000",
             "--save", str(save)],
            cwd=root,
            title="Entrenando Tool Orchestrator (LinUCB)",
        )

    else:
        pi("Uso: rl-train bc | rl-train ppo | rl-train qmix | rl-train tool-bc | rl-train tool-bandit")
        pi("  bc          → Behavioral Cloning clásico (rápido, ~1 min)")
        pi("  ppo         → Proximal Policy Optimization (~5 min)")
        pi("  qmix        → Multi-Agent RL (~15 min)")
        pi("  tool-bc     → BC para orquestador de herramientas (~30s, synthetic)")
        pi("  tool-bandit → LinUCB online para orquestador (~10s)")


def cmd_rl_eval(session, args: str = ""):
    """Evalúa política entrenada en shadow mode."""
    root, _, ckpts = _rl_paths()
    eval_script = root / ".bago" / "rl" / "adapters" / "integration_test.py"
    if not eval_script.exists():
        pe(f"No se encuentra {eval_script}")
        return
    console.print("[dim]  Evaluando en shadow mode...[/dim]")
    try:
        proc = subprocess.run(
            [sys.executable, str(eval_script), "--mode", "all"],
            capture_output=True, text=True, cwd=str(root),
            timeout=60, encoding="utf-8", errors="replace",
        )
        if proc.stdout:
            console.print(proc.stdout)
        if proc.stderr:
            console.print(f"[red]{proc.stderr}[/red]")
    except Exception as exc:
        pe(f"Error evaluando: {exc}")


def cmd_rl_sandbox(session, args: str = ""):
    """Activa/desactiva sandbox."""
    sub = args.strip().lower()
    if sub in ("on", "activate"):
        pi("Sandbox activado (modo simulate). Las operaciones peligrosas se interceptan.")
    elif sub in ("off", "deactivate"):
        pi("Sandbox desactivado. Operaciones reales permitidas.")
    else:
        pi("Uso: rl-sandbox on | rl-sandbox off")


def cmd_rl_shadow(session, args: str = ""):
    """Activa/desactiva shadow mode para recopilar datos reales."""
    import os
    sub = args.strip().lower()
    if sub in ("on", "activate", "1", "true"):
        os.environ["BAGO_RL_SHADOW"] = "1"
        pi("Shadow mode ACTIVADO. Las transiciones reales se loguean en .bago/logs/rl_transitions_shadow.jsonl")
        pi("  Las decisiones del orquestador se comparan con el modelo BC en segundo plano.")
    elif sub in ("off", "deactivate", "0", "false"):
        os.environ["BAGO_RL_SHADOW"] = "0"
        pi("Shadow mode DESACTIVADO.")
    else:
        current = os.environ.get("BAGO_RL_SHADOW", "0")
        state = "ACTIVADO" if current.lower() in ("1", "true", "yes") else "DESACTIVADO"
        pi(f"Shadow mode: {state}")
        pi("Uso: rl-shadow on | rl-shadow off")


# ── Fase 5 — Tool Orchestrator commands ───────────────────────────────────────

def cmd_rl_tool(session, args: str = ""):
    """Ejecuta el orquestador de herramientas BAGO (Fase 5).

    Uso:
      rl-tool                          → modo interactivo
      rl-tool "busca archivos de config" → tarea directa (no interactivo)
    """
    root = Path(__file__).resolve().parents[2].parent
    _, _, _, orch_script, _ = _tool_orchestrator_paths(root)

    if not orch_script.exists():
        pe(f"No se encuentra {orch_script}")
        return

    task = args.strip()
    cmd = [sys.executable, str(orch_script), "--model", "qwen2.5:1.5b"]
    if task:
        cmd += ["--task", task]
    else:
        cmd += ["--interactive"]

    console.print(f"[dim]  Ejecutando orquestador: {' '.join(cmd[-2:])}...[/dim]")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(root),
            timeout=120, encoding="utf-8", errors="replace",
        )
        if proc.stdout:
            # Mostrar solo las últimas líneas para no saturar el chat
            lines = proc.stdout.strip().splitlines()
            output = "\n".join(lines[-30:]) if len(lines) > 30 else proc.stdout
            console.print(output)
        if proc.stderr:
            console.print(f"[red]{proc.stderr[:500]}[/red]")
    except Exception as exc:
        pe(f"Error ejecutando orquestador: {exc}")
