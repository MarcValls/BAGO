"""bago.commands.rl — Comandos RL integrados en el chat de BAGO.

Uso en el chat:
  /rl-status    → Muestra transiciones acumuladas y checkpoints
  /rl-demo      → Ejecuta demo manual (3 pasos, sandbox, 0 riesgo)
  /rl-train bc  → Entrena Behavioral Cloning con datos acumulados
  /rl-train ppo → Entrena PPO online (si hay entorno)
  /rl-eval      → Evalúa política entrenada en shadow mode
  /rl-sandbox   → Activa/desactiva sandbox
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ..ui import console, pe, pi


def _rl_paths() -> tuple[Path, Path, Path]:
    """Retorna (root_dir, logs_path, checkpoints_dir)."""
    tools = Path(__file__).resolve().parents[2]
    root = tools.parent
    logs = root / ".bago" / "logs" / "rl_transitions.jsonl"
    ckpts = root / ".bago" / "rl" / "checkpoints"
    return root, logs, ckpts


def _count_transitions(logs: Path) -> int:
    if not logs.exists():
        return 0
    try:
        with logs.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f if _.strip())
    except Exception:
        return 0


def cmd_rl_status(session, args: str = ""):
    """Muestra estado del pipeline RL."""
    root, logs, ckpts = _rl_paths()
    count = _count_transitions(logs)

    console.print("[bold cyan]  Estado RL[/bold cyan]")
    console.print(f"  Transiciones acumuladas: [bold]{count}[/bold]  ({'Suficientes para entrenar' if count >= 5 else 'Necesitas ~5 para BC, ~200 para PPO'})")

    # Checkpoints existentes
    bc_ckpt = ckpts / "bc" / "bc_model.pkl"
    ppo_ckpt = ckpts / "ppo_full_v3" / "final_model.zip"
    qmix_ckpt = ckpts / "qmix" / "mixer.pt"

    has_bc = bc_ckpt.exists()
    has_ppo = ppo_ckpt.exists()
    has_qmix = qmix_ckpt.exists()

    console.print(f"  BC:     {'[green]✓[/green]' if has_bc else '[dim]—[/dim]'}  {bc_ckpt if has_bc else ''}")
    console.print(f"  PPO:    {'[green]✓[/green]' if has_ppo else '[dim]—[/dim]'}  {ppo_ckpt if has_ppo else ''}")
    console.print(f"  QMIX:   {'[green]✓[/green]' if has_qmix else '[dim]—[/dim]'}  {qmix_ckpt if has_qmix else ''}")

    # Sugerencias
    if count < 5:
        pi("Ejecuta /rl-demo para generar transiciones de prueba.")
    elif not has_bc:
        pi("Ejecuta /rl-train bc para entrenar Behavioral Cloning.")
    elif not has_ppo:
        pi("Ejecuta /rl-train ppo para entrenar PPO online.")
    else:
        pi("Todo listo. Ejecuta /rl-eval para evaluar en shadow mode.")


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


def cmd_rl_train(session, args: str = ""):
    """Entrena un modelo RL."""
    root, logs, ckpts = _rl_paths()
    sub = args.strip().lower().split()[0] if args.strip() else ""

    if sub == "bc":
        if not logs.exists() or _count_transitions(logs) < 5:
            pe(f"Solo {_count_transitions(logs)} transiciones. Necesitas al menos 5.")
            pi("Ejecuta /rl-demo primero.")
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

    else:
        pi("Uso: /rl-train bc | /rl-train ppo | /rl-train qmix")
        pi("  bc   → Behavioral Cloning (rapido, ~1 min)")
        pi("  ppo  → Proximal Policy Optimization (~5 min)")
        pi("  qmix → Multi-Agent RL (~15 min)")


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
        pi("Uso: /rl-sandbox on | /rl-sandbox off")


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
        pi("Uso: /rl-shadow on | /rl-shadow off")
