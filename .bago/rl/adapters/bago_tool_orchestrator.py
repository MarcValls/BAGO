#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_tool_orchestrator.py — Enseña al modelo local a usar herramientas BAGO.

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
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import urllib.request

# ── Paths ────────────────────────────────────────────────────────────────────
BAGO_RL_DIR = Path(__file__).resolve().parent.parent
BAGO_ROOT = BAGO_RL_DIR.parent
TOOLS_DIR = BAGO_ROOT / "tools"
LOGS_DIR = BAGO_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Tool schemas (funciones expuestas al LLM) ──────────────────────────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bago_search",
            "description": (
                "Búsqueda semántica por palabra clave, sinónimos y metáforas "
                "en el código del proyecto. Útil cuando el usuario busca algo "
                "sin saber el nombre exacto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Palabra clave o concepto a buscar"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directorio raíz de búsqueda (default: repo root)"
                    },
                    "synonyms": {
                        "type": "boolean",
                        "description": "Expandir con sinónimos (es/en)"
                    },
                    "metaphors": {
                        "type": "boolean",
                        "description": "Incluir metáforas y expresiones relacionadas"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_list",
            "description": (
                "Lista archivos del proyecto con filtros contextuales. "
                "Útil para explorar estructura, tamaños, o estado git."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio a listar"
                    },
                    "tree": {
                        "type": "boolean",
                        "description": "Mostrar en formato árbol"
                    },
                    "git": {
                        "type": "boolean",
                        "description": "Incluir estado git (modified, untracked)"
                    },
                    "sizes": {
                        "type": "boolean",
                        "description": "Incluir tamaños de archivo"
                    },
                    "json": {
                        "type": "boolean",
                        "description": "Salida JSON para procesamiento"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_read",
            "description": (
                "Lee un archivo con resaltado de sintaxis y contexto inteligente. "
                "Útil cuando el usuario pregunta 'muestrame el codigo de X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Ruta al archivo a leer"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Número de líneas a mostrar (default: 50)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto adicional para resaltar (ej: 'function calls')",
                        "enum": ["none", "functions", "imports", "comments", "config"]
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_call_search",
            "description": (
                "Busca definiciones de funciones, clases, o llamadas API "
                "con análisis por lenguaje de programación. "
                "Útil para 'dónde se define X' o 'quién llama a Y'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nombre de función, clase, o patrón"
                    },
                    "lang": {
                        "type": "string",
                        "description": "Lenguaje: python, javascript, typescript, rust, go",
                        "enum": ["python", "javascript", "typescript", "rust", "go", "all"]
                    },
                    "def": {
                        "type": "boolean",
                        "description": "Buscar definiciones (True) o llamadas (False)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_grep_smart",
            "description": (
                "Grep inteligente con filtros de contexto de código. "
                "Útil para búsquedas de patrón avanzadas con contexto semántico."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Patrón regex a buscar"
                    },
                    "def": {
                        "type": "boolean",
                        "description": "Limitar a definiciones de función/clase"
                    },
                    "call": {
                        "type": "boolean",
                        "description": "Limitar a llamadas de función"
                    },
                    "import": {
                        "type": "boolean",
                        "description": "Limitar a imports/usos de módulo"
                    },
                    "ext": {
                        "type": "string",
                        "description": "Extensiones a filtrar, ej: py,ts,md"
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]

# ── Tool execution ──────────────────────────────────────────────────────────

def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una herramienta BAGO y devuelve resultado estructurado."""
    cmd = [sys.executable, str(TOOLS_DIR / f"{name}.py")]

    if name == "bago_search":
        cmd.extend([arguments.get("keyword", "")])
        if arguments.get("directory"):
            cmd.append(arguments["directory"])
        if arguments.get("synonyms"):
            cmd.append("--synonyms")
        if arguments.get("metaphors"):
            cmd.append("--metaphors")

    elif name == "bago_list":
        if arguments.get("directory"):
            cmd.append(arguments["directory"])
        for flag in ("tree", "git", "sizes", "json"):
            if arguments.get(flag):
                cmd.append(f"--{flag}")

    elif name == "bago_read":
        cmd.append(arguments.get("filepath", ""))
        if arguments.get("lines"):
            cmd.extend(["--lines", str(arguments["lines"])])
        if arguments.get("context") and arguments["context"] != "none":
            cmd.extend(["--context", arguments["context"]])

    elif name == "bago_call_search":
        cmd.append(arguments.get("query", ""))
        if arguments.get("lang") and arguments["lang"] != "all":
            cmd.extend(["--lang", arguments["lang"]])
        if arguments.get("def"):
            cmd.append("--def")

    elif name == "bago_grep_smart":
        cmd.append(arguments.get("pattern", ""))
        for flag in ("def", "call", "import"):
            if arguments.get(flag):
                cmd.append(f"--{flag}")
        if arguments.get("ext"):
            cmd.extend(["--ext", arguments["ext"]])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(BAGO_ROOT.parent)
        )
        stdout = result.stdout[:8000]  # truncar para no saturar contexto LLM
        stderr = result.stderr[:2000]
        return {
            "tool": name,
            "arguments": arguments,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "success": result.returncode == 0
        }
    except Exception as exc:
        return {
            "tool": name,
            "arguments": arguments,
            "exit_code": -1,
            "error": str(exc),
            "success": False
        }


# ── Ollama API ──────────────────────────────────────────────────────────────

def ollama_chat(model: str, messages: list[dict], tools: list[dict] | None = None, timeout: int = 60) -> dict:
    """Envía chat request a Ollama local."""
    url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        }
    }
    if tools:
        payload["tools"] = tools

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Logging for RL ─────────────────────────────────────────────────────────

def log_transition(transition: dict) -> None:
    """Append transition to RL log for future training."""
    log_file = LOGS_DIR / "tool_orchestrator_transitions.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(transition, ensure_ascii=False) + "\n")


# ── Core loop ───────────────────────────────────────────────────────────────

def compute_reward(tool_result: dict, user_satisfaction: int | None = None) -> float:
    """Recompensa compuesta: éxito técnico + calidad de salida + feedback usuario."""
    r = 0.0
    if tool_result.get("success"):
        r += 0.5
    stdout_len = len(tool_result.get("stdout", ""))
    if 100 < stdout_len < 4000:
        r += 0.3  # output con contenido pero no saturado
    if user_satisfaction is not None:
        r += (user_satisfaction / 5.0) * 0.5  # 0-5 escala
    return min(r, 1.0)


def orchestrate_task(model: str, user_task: str, max_steps: int = 5, interactive: bool = False) -> str:
    """Orquesta una tarea del usuario usando el LLM local como router de herramientas."""
    messages = [
        {
            "role": "system",
            "content": (
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
        },
        {"role": "user", "content": user_task}
    ]

    outputs = []
    for step in range(max_steps):
        try:
            resp = ollama_chat(model, messages, tools=TOOL_SCHEMAS, timeout=120)
        except Exception as exc:
            outputs.append(f"[ERROR Ollama] {exc}")
            break

        msg = resp.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            # LLM respondió directamente sin usar herramientas
            outputs.append(content)
            if interactive:
                print(f"\n🤖 {content}")
            break

        # Ejecutar todas las herramientas que pidió el LLM
        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            if interactive:
                print(f"\n🔧 Ejecutando: {tool_name}({json.dumps(args, ensure_ascii=False)})")

            result = run_tool(tool_name, args)

            if interactive:
                print(f"   → exit_code={result['exit_code']}, stdout={len(result['stdout'])} chars")

            # Log transition para RL
            transition = {
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "model": model,
                "user_task": user_task,
                "step": step,
                "context": [m["content"] for m in messages[-3:]],
                "action": {"tool": tool_name, "args": args},
                "result": {
                    "success": result["success"],
                    "exit_code": result["exit_code"],
                    "output_length": len(result["stdout"])
                },
                "reward": compute_reward(result)
            }
            log_transition(transition)

            # Devolver resultado al LLM como mensaje de "tool"
            tool_msg = (
                f"Resultado de {tool_name}:\n"
                f"```\n{result['stdout'][:3000]}\n```"
            )
            if result["stderr"]:
                tool_msg += f"\n[stderr] {result['stderr'][:500]}"

            messages.append({
                "role": "tool",
                "content": tool_msg,
                "name": tool_name
            })
            outputs.append(tool_msg)

        # Añadir mensaje de assistant con tool_calls para que Ollama lo entienda
        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls
        })

    return "\n".join(outputs)


# ── CLI ─────────────────────────────────────────────────────────────────────

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
