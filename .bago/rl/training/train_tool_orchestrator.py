#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_tool_orchestrator.py — CLI entry point para entrenar política RL de herramientas BAGO.

Lee transiciones de bago_tool_orchestrator.py y entrena un agente LinUCB
(Fase 1) o Behavioral Cloning (Fase 2) para predecir la mejor herramienta
dado el contexto de la tarea.

Uso:
    python train_tool_orchestrator.py --mode bandit --episodes 5000
    python train_tool_orchestrator.py --mode bc --epochs 30
    python train_tool_orchestrator.py --eval --checkpoint .bago/rl/checkpoints/tool_policy.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Insertamos .bago/rl en path para importar envs
_RL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RL_DIR))

from training import evaluate_policy, train_bandit, train_bc

CHECKPOINTS_DIR = _RL_DIR / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena política RL para herramientas BAGO")
    parser.add_argument("--mode", choices=["bandit", "bc"], default="bandit",
                        help="Algoritmo: bandit (LinUCB) o bc (Behavioral Cloning)")
    parser.add_argument("--episodes", type=int, default=2000, help="Episodios (bandit)")
    parser.add_argument("--epochs", type=int, default=30, help="Épocas (bc)")
    parser.add_argument("--alpha", type=float, default=1.0, help="Exploración LinUCB")
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate BC")
    parser.add_argument("--dataset", type=Path, help="JSONL de transiciones para BC (demo sintética o real)")
    parser.add_argument("--eval", action="store_true", help="Modo evaluación")
    parser.add_argument("--checkpoint", type=Path, help="Checkpoint para evaluar")
    parser.add_argument("--save", type=Path, help="Ruta de guardado")
    args = parser.parse_args()

    if args.eval:
        if not args.checkpoint:
            print("[ERROR] --eval requiere --checkpoint")
            sys.exit(1)
        print(f"Evaluando {args.checkpoint}...")
        metrics = evaluate_policy(args.checkpoint, transitions_file=args.dataset)
        print(json.dumps(metrics, indent=2))
        return

    if args.mode == "bandit":
        save = args.save or CHECKPOINTS_DIR / "tool_policy_bandit.json"
        print(f"Entrenando LinUCB ({args.episodes} episodios, alpha={args.alpha})...")
        metrics = train_bandit(args.episodes, args.alpha, save)
    else:
        save = args.save or CHECKPOINTS_DIR / "tool_policy_bc.json"
        print(f"Entrenando BC ({args.epochs} epochs, lr={args.lr})...")
        metrics = train_bc(args.epochs, args.lr, save, transitions_file=args.dataset)

    print("\n=== Métricas ===")
    print(json.dumps(metrics, indent=2))
    print(f"\nCheckpoint guardado en: {save}")


if __name__ == "__main__":
    main()
