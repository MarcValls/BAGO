#!/usr/bin/env python3
"""
tool_registry.py — BAGO 4.0 Tool Registry

Registro simple de herramientas que los modelos pueden invocar.
Mantiene el formato estándar OpenAI (function calling) para compatibilidad.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from script_registry import ScriptRegistry


@dataclass
class ToolCall:
    """Representa una invocación de herramienta desde el modelo."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Resultado de ejecutar una herramienta."""
    call_id: str
    name: str
    output: str
    error: str = ""

    @property
    def content(self) -> str:
        if self.error:
            return f"Error: {self.error}"
        return self.output


@dataclass
class Tool:
    """Definición de una herramienta ejecutable."""
    name: str
    description: str
    parameters: dict[str, Any]
    function: Callable[..., str]

    def to_openai(self) -> dict[str, Any]:
        """Exporta al formato OpenAI function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Ejecuta la herramienta y retorna resultado."""
        try:
            output = self.function(**kwargs)
            return ToolResult(call_id="", name=self.name, output=output)
        except Exception as exc:
            return ToolResult(call_id="", name=self.name, output="", error=str(exc))


# ── Built-in tools ─────────────────────────────────────────────────

def _tool_read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe: {path}")
    return p.read_text(encoding="utf-8", errors="replace")


def _tool_write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Archivo escrito: {path} ({len(content)} chars)"


# ── Allowlist de comandos seguros ─────────────────────────────────────────────
# Cada entrada mapea un command_id a (executable, [args_fijos]).
# El modelo pasa command_id + args_extra; nunca pasa shell string libre.
# Para añadir comandos: extender este dict o cargarlo desde .bago/allowed_commands.json.
_COMMAND_ALLOWLIST: dict[str, tuple[str, list[str]]] = {
    "git-status":     ("git", ["status", "--short"]),
    "git-log":        ("git", ["log", "--oneline", "-10"]),
    "python-version": ("python", ["--version"]),
    "list-dir":       ("dir" if os.name == "nt" else "ls", []),
}


def _tool_run_allowed_command(command_id: str, args: list[str] | None = None) -> str:
    """Ejecuta solo comandos explícitamente aprobados en el allowlist."""
    if command_id not in _COMMAND_ALLOWLIST:
        known = ", ".join(sorted(_COMMAND_ALLOWLIST))
        raise ValueError(
            f"Comando '{command_id}' no está en el allowlist. "
            f"Comandos permitidos: {known}"
        )
    exe, fixed_args = _COMMAND_ALLOWLIST[command_id]
    cmd = [exe] + fixed_args + (args or [])
    result = subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        raise RuntimeError(f"Exit code {result.returncode}\n{stderr}")
    return stdout or "(sin salida)"


def _tool_list_directory(path: str = ".") -> str:
    p = Path(path)
    if not p.is_dir():
        raise NotADirectoryError(f"No es directorio: {path}")
    entries = []
    for item in sorted(p.iterdir()):
        marker = "📁" if item.is_dir() else "📄"
        entries.append(f"{marker} {item.name}")
    return "\n".join(entries) if entries else "(vacío)"


BUILTIN_TOOLS: list[Tool] = [
    Tool(
        name="read_file",
        description="Lee el contenido de un archivo de texto. Útil para inspeccionar código o documentos.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta al archivo a leer (absoluta o relativa)"},
            },
            "required": ["path"],
        },
        function=_tool_read_file,
    ),
    Tool(
        name="write_file",
        description="Escribe contenido en un archivo. Crea directorios intermedios si no existen.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta al archivo a escribir"},
                "content": {"type": "string", "description": "Contenido a escribir"},
            },
            "required": ["path", "content"],
        },
        function=_tool_write_file,
    ),
    Tool(
        name="execute_command",
        description=(
            "Ejecuta un comando de la lista aprobada (allowlist). "
            "Pasa command_id del allowlist y args_extra opcionales. "
            "No acepta comandos shell arbitrarios."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command_id": {
                    "type": "string",
                    "description": (
                        "ID del comando aprobado. Valores permitidos: "
                        + ", ".join(sorted(_COMMAND_ALLOWLIST))
                    ),
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Argumentos adicionales para el comando (opcional).",
                },
            },
            "required": ["command_id"],
        },
        function=lambda command_id, args=None: _tool_run_allowed_command(command_id, args),
    ),
    Tool(
        name="list_directory",
        description="Lista los archivos y directorios en una ruta.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta del directorio a listar (default: directorio actual)"},
            },
            "required": [],
        },
        function=_tool_list_directory,
    ),
]


class ToolRegistry:
    """Registro de herramientas disponibles para los modelos."""

    def __init__(self, script_registry: ScriptRegistry | None = None) -> None:
        self.script_registry = script_registry or ScriptRegistry()
        self._tools: dict[str, Tool] = {}
        for tool in BUILTIN_TOOLS:
            self.register(tool)
        self.register(
            Tool(
                name="list_scripts",
                description="Lista el índice explícito de scripts y baterías registradas.",
                parameters={
                    "type": "object",
                    "properties": {
                        "battery": {
                            "type": "string",
                            "description": "Batería opcional a filtrar.",
                        },
                    },
                    "required": [],
                },
                function=lambda battery="": self.script_registry.describe_catalog()
                if not battery
                else self._format_script_subset(battery),
            )
        )
        self.register(
            Tool(
                name="run_script",
                description=(
                    "Resuelve una tarea contra el índice explícito de scripts y ejecuta "
                    "el script Python registrado. Si no existe, devuelve qué script falta."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Descripción libre de la tarea a resolver.",
                        },
                        "script_id": {
                            "type": "string",
                            "description": "ID exacto del script registrado a ejecutar.",
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Argumentos adicionales para el script.",
                        },
                    },
                    "required": [],
                },
                function=lambda task="", script_id="", args=None: self.run_registered_script(
                    task=task,
                    script_id=script_id,
                    args=args,
                ),
            )
        )

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai(self) -> list[dict[str, Any]]:
        """Exporta todas las herramientas al formato OpenAI."""
        return [t.to_openai() for t in self._tools.values()]

    def execute_call(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call_id=call.id, name=call.name, output="", error=f"Herramienta '{call.name}' no encontrada.")
        result = tool.execute(**call.arguments)
        result.call_id = call.id
        result.name = call.name
        return result

    def list_script_batteries(self) -> list[dict[str, Any]]:
        return self.script_registry.list_batteries()

    def list_scripts(self, battery: str | None = None) -> list[dict[str, Any]]:
        return self.script_registry.list_scripts(battery)

    def run_registered_script(self, task: str = "", script_id: str = "", args: list[str] | None = None) -> str:
        if script_id:
            return self.script_registry.run_script(script_id, args)
        if task:
            return self.script_registry.run_task(task, args)
        raise ValueError("Debe indicar task o script_id.")

    def _format_script_subset(self, battery: str) -> str:
        battery_def = self.script_registry.get_battery(battery)
        if battery_def is None:
            known = ", ".join(sorted(item["id"] for item in self.script_registry.list_batteries()))
            raise ValueError(f"Batería '{battery}' no registrada. Disponibles: {known}")
        lines = [f"{battery_def.id}: {battery_def.description}"]
        for script in self.script_registry.list_scripts(battery_def.id):
            marker = "✓" if script["enabled"] and script["exists"] else "!"
            lines.append(f"  {marker} {script['id']} — {script['description']} ({script['path']})")
        if not self.script_registry.list_scripts(battery_def.id):
            lines.append("  (sin scripts registrados)")
        return "\n".join(lines)

    def parse_tool_calls(self, response_data: dict[str, Any]) -> list[ToolCall]:
        """Parsea tool_calls de respuestas OpenAI- y Ollama-compatible."""
        calls: list[ToolCall] = []
        for idx, tc in enumerate(response_data.get("tool_calls", []), start=1):
            tc_type = tc.get("type")
            if tc_type not in (None, "function"):
                continue
            func = tc.get("function", {})
            name = func.get("name") or tc.get("name", "")
            if not name:
                continue
            args_raw = func.get("arguments", tc.get("arguments", {}))
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {}
            elif isinstance(args_raw, dict):
                args = args_raw
            else:
                args = {}
            calls.append(ToolCall(
                id=tc.get("id") or f"call_{idx}",
                name=name,
                arguments=args,
            ))
        return calls

    def __len__(self) -> int:
        return len(self._tools)


def _run_tests() -> int:
    reg = ToolRegistry()
    assert len(reg) >= 4
    tools = reg.to_openai()
    assert all(t["type"] == "function" for t in tools)
    assert any(t["function"]["name"] == "read_file" for t in tools)
    assert any(t["function"]["name"] == "run_script" for t in tools)

    parsed = reg.parse_tool_calls({
        "tool_calls": [
            {
                "function": {
                    "name": "list_directory",
                    "arguments": {"path": "."},
                }
            }
        ]
    })
    assert len(parsed) == 1
    assert parsed[0].name == "list_directory"
    assert parsed[0].arguments["path"] == "."

    directory_output = reg.run_registered_script(task="analiza el directorio actual")
    assert "Directory:" in directory_output
    assert ".bago" in directory_output or "bago.cmd" in directory_output

    result = reg.get("execute_command").execute(command_id="python-version")
    assert "Python" in result.output
    print("tool_registry.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
