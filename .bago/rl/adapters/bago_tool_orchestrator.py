#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_tool_orchestrator.py — CLI entry point del orquestador BAGO + LLM local.

Conecta Ollama (modelo local ≤5B) con las 5 herramientas de análisis recién creadas:
  bago_search, bago_list, bago_read, bago_call_search, bago_grep_smart

Flujo:
  1. Usuario describe la tarea en lenguaje natural
  2. El LLM decide qué herramienta(s) usar y con qué parámetros
  3. El orquestador ejecuta la herramienta real y devuelve el resultado al LLM
  4. El LLM interpreta el resultado y propone siguiente paso o responde al usuario
  5. Cada transición (contexto, acción, resultado, recompensa) se loggea para RL

Uso:
    python .bago/rl/adapters/bago_tool_orchestrator.py --model qwen2.5:1.5b --interactive
    python .bago/rl/adapters/bago_tool_orchestrator.py --model llama3.2:3b --task "busca errores de configuración"

Requiere: Ollama corriendo en 127.0.0.1:11434
"""
from __future__ import annotations

import argparse

from orchestrator.core import orchestrate_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Orquestador BAGO + LLM local")
    parser.add_argument("--model", default="qwen2.5:1.5b", help="Modelo Ollama (max 5B recomendado)")
    parser.add_argument("--task", help="Tarea en lenguaje natural (modo no-interactivo)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo conversación interactivo")
    parser.add_argument("--max-steps", type=int, default=5, help="Máximo de pasos de herramienta")
    args = parser.parse_args()

    if args.task:
        result = orchestrate_task(args.model, args.task, max_steps=args.max_steps, interactive=True)
        print("\n=== RESULTADO FINAL ===")
        print(result[:3000])
        return

    if args.interactive:
        print(f"🧠 Orquestador BAGO + {args.model}")
        print("Escribe 'salir' para terminar.\n")
        while True:
            user_input = input("👤 Tú: ").strip()
            if user_input.lower() in ("salir", "exit", "quit", "q"):
                break
            if not user_input:
                continue
            orchestrate_task(args.model, user_input, max_steps=args.max_steps, interactive=True)
        print("👋 Sesión finalizada.")
        return

    # Demo por defecto
    demo_task = "Busca todos los archivos que contengan 'config' y muéstrame cómo se define la configuración global"
    print(f"🧠 Demo: {demo_task}")
    print(f"   Modelo: {args.model}")
    result = orchestrate_task(args.model, demo_task, max_steps=3, interactive=True)
    print("\n=== RESUMEN ===")
    print(result[:2000])


if __name__ == "__main__":
    main()
