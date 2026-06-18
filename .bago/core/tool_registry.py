#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
tool_registry.py — BAGO 4.1.5 Tool Registry

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


def _tool_retrain_intents() -> str:
    """Regenera el dataset de few-shot intents desde el historial de sesiones."""
    import sqlite3
    store_db = Path.home() / ".copilot" / "session-store.db"
    if not store_db.exists():
        return f"[retrain_intents] No se encontró la base de datos de sesiones: {store_db}"

    keywords = {
        "chat": ["hola", "hey", "saludos", "continua", "gracias", "adios", "bago", "bago next", "bago start", "español", "hello", "hi"],
        "review": ["revisa", "mira", "reune", "busca", "chequea", "examina", "verifica", "analiza esto", "mira esto", "mira ahora", "list_directory", "read_file", "dame el contenido"],
        "execute": ["ejecuta", "corre", "lanza", "dispara", "run", "execute", "corre el comando", "ejecuta el script", "corre el script"],
        "work": ["trabaja", "modulariza", "adapta", "crea", "modifica", "refactoriza", "estructurala", "ordena", "desarrolla", "implementa", "construye", "genera", "haz que", "hazme", "adaptalo", "modularizala", "estructuralo", "organiza"],
    }

    conn = sqlite3.connect(str(store_db))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT session_id, user_message, assistant_response FROM turns WHERE user_message IS NOT NULL AND user_message != '' AND LENGTH(user_message) < 800")
    rows = c.fetchall()
    conn.close()

    examples = {k: [] for k in keywords}
    for row in rows:
        msg = row["user_message"]
        if "══" in msg or "┌─" in msg or len(msg) > 400:
            continue
        low = msg.lower()
        matched = False
        for intent, words in keywords.items():
            if any(w in low for w in words):
                examples[intent].append({
                    "user": msg,
                    "assistant": (row["assistant_response"] or "")[:500],
                    "session": row["session_id"],
                })
                matched = True
                break
        if not matched and len(msg) < 60:
            examples["chat"].append({
                "user": msg,
                "assistant": (row["assistant_response"] or "")[:500],
                "session": row["session_id"],
            })

    for intent in examples:
        seen = set()
        deduped = []
        for ex in examples[intent]:
            if ex["user"] not in seen:
                seen.add(ex["user"])
                deduped.append(ex)
        examples[intent] = deduped[:15]

    current_examples: dict[str, list[dict[str, str]]] = {}
    for source in (_intent_examples_path(), Path(__file__).with_name("intent_examples.json")):
        if not source.exists():
            continue
        try:
            with open(source, "r", encoding="utf-8") as f:
                current_examples = json.load(f)
            break
        except Exception:
            continue

    for intent, rows in current_examples.items():
        if intent not in examples:
            examples[intent] = []
        examples[intent].extend(rows)

    for intent in examples:
        seen = set()
        merged: list[dict[str, Any]] = []
        for ex in examples[intent]:
            key = ex.get("user", "")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(ex)
        examples[intent] = merged[:30]

    out_path = _intent_examples_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in examples.values())
    return f"[retrain_intents] Dataset regenerado: {total} ejemplos guardados en {out_path}"


def _intent_examples_path() -> Path:
    """Ruta escribible para el dataset aprendido de intenciones."""
    override = os.environ.get("BAGO_INTENT_EXAMPLES_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".bago" / "state" / "intent_examples.json"


def _tool_clean_bago_installs(
    backup_root: str = "C:\\BAGO_INSTALLS",
    execute: bool = False,
    reinstall: bool = False,
    fresh_package: str = "",
    skip_install_tests: bool = False,
) -> str:
    """Inventaría/respaldar instalaciones BAGO y opcionalmente limpia/reinstala."""
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "clean_bago_installs.py"
    if not script.exists():
        raise FileNotFoundError(f"No existe herramienta: {script}")
    cmd = [
        sys.executable,
        str(script),
        "--backup-root",
        backup_root,
        "--json",
    ]
    if fresh_package:
        cmd += ["--fresh-package", fresh_package]
    if execute:
        cmd.append("--execute")
    if reinstall:
        cmd.append("--reinstall")
    if skip_install_tests:
        cmd.append("--skip-install-tests")
    result = subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=1800,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        raise RuntimeError(f"Exit code {result.returncode}\n{stderr or stdout or '(sin salida)'}")
    return stdout or "(sin salida)"


def _tool_deploy_to_vercel(project_path: str = ".", production: bool = False, yes: bool = False) -> str:
    """Despliega un proyecto a Vercel usando la CLI de Vercel.

    Requiere que 'vercel' esté instalado y autenticado (vercel login).
    """
    import shutil
    if not shutil.which("vercel"):
        raise RuntimeError(
            "Vercel CLI no encontrado. Instálalo con: npm i -g vercel\n"
            "Y autentícate con: vercel login"
        )
    cmd = ["vercel", str(Path(project_path).resolve())]
    if production:
        cmd.append("--prod")
    if yes:
        cmd.append("--yes")
    result = subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        raise RuntimeError(f"Deploy falló (exit {result.returncode}):\n{stderr or stdout}")
    # Extraer URL de salida
    for line in stdout.splitlines():
        if line.startswith("https://") and "vercel.app" in line:
            return f"[deploy_to_vercel] Desplegado exitosamente: {line}"
    return f"[deploy_to_vercel] Desplegado. Salida:\n{stdout}"


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
        description="Lists files and directories in a path. Only use this when the user explicitly asks to see files, directories, or contents of a folder.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta del directorio a listar (default: directorio actual)"},
            },
            "required": [],
        },
        function=_tool_list_directory,
    ),
    Tool(
        name="retrain_intents",
        description=(
            "Regenera el dataset de entrenamiento de intenciones (intent_examples.json) "
            "escaneando todo el historial de conversaciones del usuario. "
            "Úsalo cuando quieras que BAGO aprenda de nuevas interacciones."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=_tool_retrain_intents,
    ),
    Tool(
        name="clean_bago_installs",
        description=(
            "Inventaría instalaciones BAGO verificadas y no verificadas en C:, "
            "crea ZIP/manifiesto en C:\\BAGO_INSTALLS y, solo si execute=true, "
            "limpia rutas BAGO y puede reinstalar una copia fresca."
        ),
        parameters={
            "type": "object",
            "properties": {
                "backup_root": {
                    "type": "string",
                    "description": "Directorio de backup/manifiestos. Default: C:\\BAGO_INSTALLS",
                },
                "execute": {
                    "type": "boolean",
                    "description": "false solo inventario+backup; true borra targets después del ZIP.",
                },
                "reinstall": {
                    "type": "boolean",
                    "description": "Si execute=true, reinstala BAGO v4 desde paquete local.",
                },
                "fresh_package": {
                    "type": "string",
                    "description": "ZIP local bago-v4-local-*.zip opcional.",
                },
                "skip_install_tests": {
                    "type": "boolean",
                    "description": "Omite tests del instalador en reinstalación.",
                },
            },
            "required": [],
        },
        function=_tool_clean_bago_installs,
    ),
    Tool(
        name="deploy_to_vercel",
        description=(
            "Despliega un proyecto local a Vercel. Requiere 'vercel' CLI instalado y autenticado. "
            "Usa production=true para desplegar a producción; yes=true para saltar confirmaciones."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Ruta al proyecto a desplegar. Default: directorio actual.",
                },
                "production": {
                    "type": "boolean",
                    "description": "Si true, despliega a producción (--prod).",
                },
                "yes": {
                    "type": "boolean",
                    "description": "Si true, confirma automáticamente (--yes).",
                },
            },
            "required": [],
        },
        function=_tool_deploy_to_vercel,
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

    def retrain_intents(self) -> str:
        """Regenera el dataset de few-shot intents desde el historial de sesiones."""
        return _tool_retrain_intents()

    def deploy_to_vercel(self, project_path: str = ".", production: bool = False, yes: bool = False) -> str:
        """Despliega un proyecto a Vercel usando la CLI de Vercel."""
        return _tool_deploy_to_vercel(project_path=project_path, production=production, yes=yes)

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
    cleaner = reg.get("clean_bago_installs")
    assert cleaner is not None
    assert "C:\\BAGO_INSTALLS" in cleaner.description
    print("tool_registry.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
