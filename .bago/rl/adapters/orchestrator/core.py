# -*- coding: utf-8 -*-
"""core.py — Loop principal de orquestación BAGO + LLM local.

Decide herramienta, ejecuta, loggea transición, y devuelve resultado al LLM.
"""
from __future__ import annotations

import json
from typing import Any

from . import ollama_client, rl_logger, tool_runner
from .tool_schemas import TOOL_NAMES, TOOL_SCHEMAS


SYSTEM_PROMPT = (
    "Eres el orquestador de herramientas BAGO. Tu trabajo es DECIDIR "
    "qué herramienta de análisis ejecutar para resolver la petición del usuario. "
    "Dispones de 5 herramientas especializadas:\n"
    "1. bago_search — búsqueda semántica por keyword/sinónimos/metáforas\n"
    "2. bago_list — listar archivos con tree/git/sizes\n"
    "3. bago_read — leer archivo con resaltado de sintaxis\n"
    "4. bago_call_search — buscar definiciones/llamadas de función por lenguaje\n"
    "5. bago_grep_smart — grep con filtros de contexto (def/call/import)\n"
    "\nREGLAS:\n"
    "- Siempre elige la herramienta más específica para la tarea.\n"
    "- No inventes rutas; usa 'bago_list' primero si no conoces la estructura.\n"
    "- Si necesitas leer un archivo específico, usa 'bago_read'.\n"
    "- Si el usuario busca algo sin saber el nombre exacto, usa 'bago_search'.\n"
    "- Si el usuario pregunta 'donde se define X', usa 'bago_call_search'.\n"
)


def _parse_tool_args(raw_args: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    try:
        return json.loads(raw_args)
    except json.JSONDecodeError:
        return {}


def _build_tool_result_message(tool_name: str, result: dict) -> str:
    msg = f"Resultado de {tool_name}:\n```\n{result['stdout'][:3000]}\n```"
    if result.get("stderr"):
        msg += f"\n[stderr] {result['stderr'][:500]}"
    return msg


def orchestrate_task(
    model: str,
    user_task: str,
    max_steps: int = 5,
    interactive: bool = False,
) -> str:
    """Orquesta una tarea del usuario usando el LLM local como router de herramientas."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_task}
    ]
    outputs = []

    for step in range(max_steps):
        try:
            resp = ollama_client.chat(model, messages, tools=TOOL_SCHEMAS, timeout=120)
        except Exception as exc:
            outputs.append(f"[ERROR Ollama] {exc}")
            break

        msg = resp.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            outputs.append(content)
            if interactive:
                print(f"\n🤖 {content}")
            break

        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            args = _parse_tool_args(fn.get("arguments", {}))

            if interactive:
                print(f"\n🔧 Ejecutando: {tool_name}({json.dumps(args, ensure_ascii=False)})")

            result = tool_runner.run_tool(tool_name, args)

            if interactive:
                print(f"   → exit_code={result['exit_code']}, stdout={len(result['stdout'])} chars")

            transition = rl_logger.build_transition(
                model=model,
                user_task=user_task,
                step=step,
                messages=messages,
                tool_name=tool_name,
                args=args,
                tool_result=result,
            )
            rl_logger.log_transition(transition)

            tool_msg = _build_tool_result_message(tool_name, result)
            messages.append({"role": "tool", "content": tool_msg, "name": tool_name})
            outputs.append(tool_msg)

        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

    return "\n".join(outputs)
