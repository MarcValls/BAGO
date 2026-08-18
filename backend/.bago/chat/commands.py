#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
commands.py — BAGO 4.1.5 Chat Command Parser

Parsea y ejecuta comandos slash del REPL.
Todos los comandos son funciones puras que reciben el SessionManager
y retornan un dict con {ok, message, action}.

Comandos soportados:
  /menu
  /switch <provider> [modelo] [--force]
  /models [provider]
  /status
  /session
  /mode [B|A|G|O]
  /save
  /load <session_id>
  /providers
  /scripts [battery]
  /allow
  /deny
  /memory
  /help
  /quit
"""

from __future__ import annotations

import json
import os
import sys
import shlex
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import user_read_candidates

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# CANON[CHAT-001]: this module owns the slash-command registry for the chat layer.
# LEGACY[CHAT-L001]: keep local module resolution for spec-loaded tests and flat imports.
CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from session_manager import SessionManager
from switch_engine import SwitchEngine
from contract_state import build_menu_state, build_model_catalog_state, build_roadmap_state, build_welcome_state
from reflexive_interpreter import analyze_question, format_reflexive_report, rules_contract_info
from command_utils import load_tool_module as _load_tool_module, parse_args as _parse_args
import renderer as R
from context_commands import cmd_context
from memory_commands import cmd_memory as _cmd_memory_impl
from project_commands import cmd_project as _cmd_project_impl
from tool_approval_commands import (
    current_tool_approval_policy,
    handle_allow_command,
    handle_deny_command,
    handle_tools_command,
)


def cmd_project(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    return _cmd_project_impl(mgr, engine, args, load_module=_load_tool_module)


def cmd_memory(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    return _cmd_memory_impl(mgr, engine, args)


class CommandError(Exception):
    pass


def _install_roles_read_path() -> Path:
    candidates = user_read_candidates("install_selection.json")
    return next((path for path in candidates if path.is_file()), candidates[0])


MENU_SECTIONS: list[dict[str, Any]] = [
    {
        "title": "Sesion y estado",
        "description": "Estado de la conversacion y sesiones guardadas.",
        "items": [
            {"command": "/menu", "description": "Abre menu interactivo de funciones"},
            {"command": "/commands", "description": "Exporta catalogo de comandos", "args_prompt": "[json]"},
            {"command": "/doctor", "description": "Diagnostico rapido del entorno BAGO"},
            {"command": "/turn.submit", "description": "Envía la respuesta final de un turno"},
            {"command": "/status", "description": "Estado de la sesion activa"},
            {"command": "/session", "description": "Detalles de la sesion"},
            {"command": "/context", "description": "Inspecciona, adjunta y certifica contexto", "args_prompt": "[inspect|attach|measure|benchmark|certify|history|invalidate|calibrate|tune]"},
            {"command": "/mode", "description": "Consulta o cambia el modo BAGO", "args_prompt": "[B|A|G|O]"},
            {"command": "/save", "description": "Guarda sesion en disco"},
            {"command": "/load", "description": "Carga una sesion desde disco", "wizard": "load"},
        ],
    },
    {
        "title": "Roadmap y verificacion",
        "description": "Iteraciones, fases y evidencia de cierre.",
        "items": [
            {"command": "/roadmap", "description": "Muestra el megaplan por iteraciones y su evidencia"},
        ],
    },
    {
        "title": "Proyectos y directorio",
        "description": "Analiza un proyecto local y prepara su memoria portable.",
        "items": [
            {"command": "/project", "description": "Analiza, siembra, sincroniza o vincula el proyecto", "args_prompt": "[analyze|status|init|link|seed|sync]", "wizard": "project"},
        ],
    },
    {
        "title": "Providers y modelos",
        "description": "Centro de providers, modelos y bridges del orquestador.",
        "items": [
            {"command": "/switch", "description": "Cambia provider y modelo", "args_prompt": "<provider> [modelo] [--force]"},
            {"command": "/models", "description": "Lista modelos disponibles", "args_prompt": "[provider]"},
            {"command": "/providers", "description": "Centro de providers/modelos/bridges y cambio de modelo", "wizard": "switch"},
            {"command": "/bridges", "description": "Lista bridges activos y soporte"},
            {"command": "/orchestrate", "description": "Envia un prompt a los bridges activos", "args_prompt": "<prompt>"},
            {"command": "/suggest", "description": "Sugerencia RL de provider"},
        ],
    },
    {
        "title": "Herramientas y automatizacion",
        "description": "Tools, planes y ejecucion autonoma.",
        "items": [
            {"command": "/tools", "description": "Centro de tools, aprobacion y estado en una sola pantalla", "wizard": "tools"},
            {"command": "/scripts", "description": "Lista scripts y baterias registradas"},
            {"command": "/inventory", "description": "Inventario de piezas usables de BAGO", "wizard": "inventory"},
            {"command": "/allow", "description": "Aprueba ejecucion de herramientas pendientes", "args_prompt": "[once|always]"},
            {"command": "/deny", "description": "Rechaza ejecucion de herramientas pendientes", "args_prompt": "[once|ask]"},
            {"command": "/interpret", "description": "Descompone preguntas, auditorias y reglas reflexivas", "args_prompt": "<pregunta|history|rules>"},
            {"command": "/plan", "description": "Genera un plan paso a paso", "args_prompt": "<tarea>"},
            {"command": "/autopilot", "description": "Ejecuta una tarea autonomamente", "args_prompt": "<tarea>"},
            {"command": "/evolve", "description": "Reentrena intenciones desde el historial, sin certificación"},
            {"command": "/train", "description": "Verifica frases nuevas y regresión de comandos", "args_prompt": "[split|all|fallos|/comando]"},
        ],
    },
    {
        "title": "Agentes y memoria",
        "description": "Agentes especializados y base de conocimiento.",
        "items": [
            {"command": "/agents", "description": "Lista agentes especializados"},
            {"command": "/agent", "description": "Activa un agente", "wizard": "agent"},
            {"command": "/memory", "description": "Previsualiza, marca y borra recuerdos en una sola pantalla", "wizard": "memory"},
            {"command": "/good", "description": "Marca un mensaje como importante"},
            {"command": "/feedback", "description": "Feedback explicito (-1 a 1)", "wizard": "feedback"},
        ],
    },
    {
        "title": "Configuracion y control",
        "description": "Config, credenciales y ayuda del chat.",
        "items": [
            {"command": "/config", "description": "Edita defaults y flags en una sola pantalla", "wizard": "config"},
            {"command": "/ui", "description": "Configura la interfaz React (tema, layout, version)", "wizard": "ui"},
            {"command": "/credentials", "description": "Gestiona credenciales API"},
            {"command": "/update", "description": "Actualiza BAGO a la ultima version", "confirm": True},
            {"command": "/help", "description": "Muestra esta ayuda"},
            {"command": "/quit", "description": "Salir del chat", "confirm": True},
        ],
    },
]


def menu_state_for_manager(mgr: SessionManager) -> dict[str, Any]:
    workspace_state = getattr(mgr, "workspace_state", lambda: {})()
    menu_state = build_menu_state(workspace_state, MENU_SECTIONS)
    menu_state["sections"] = [
        {
            "title": section["title"],
            "description": section["description"],
            "items": list(section["items"]),
        }
        for section in MENU_SECTIONS
    ]
    return menu_state


def welcome_state_for_manager(mgr: SessionManager) -> dict[str, Any]:
    workspace_state = getattr(mgr, "workspace_state", lambda: {})()
    return build_welcome_state(workspace_state)


def roadmap_state_for_manager(mgr: SessionManager) -> dict[str, Any]:
    roadmap_state = getattr(mgr, "roadmap_state", None)
    if callable(roadmap_state):
        return roadmap_state()
    return build_roadmap_state()


def model_catalog_state_for_manager(mgr: SessionManager, provider: str | None = None) -> dict[str, Any]:
    provider_name = provider or mgr.provider
    catalog = mgr.list_model_catalog(provider_name)
    return build_model_catalog_state(
        provider_name,
        catalog,
        selected_model=mgr.model if provider_name == mgr.provider else "",
        effective_model=mgr.model if provider_name == mgr.provider else "",
    )


def _build_help_text() -> str:
    lines = ["Comandos disponibles:"]
    for section in MENU_SECTIONS:
        lines.append(f"")
        lines.append(f"[{section['title']}]")
        for item in section["items"]:
            command = item["command"]
            if item.get("args_prompt"):
                command = f"{command} {item['args_prompt']}"
            description = item["description"]
            lines.append(f"  {command:<44} {description}")
    lines.extend([
        "",
        "Modo no interactivo:",
        "  bago exec /comando [args...]                 Ejecuta cualquier comando slash sin abrir el REPL",
        "  bago exec /status                            Ejemplo headless",
        "  bago exec /switch ollama-local llama3.2:3b   Ejemplo con argumentos",
    ])
    return "\n".join(lines)


def _catalog_payload() -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    catalog_commands: list[str] = []
    for section in MENU_SECTIONS:
        items: list[dict[str, Any]] = []
        for item in section["items"]:
            command = str(item["command"])
            catalog_commands.append(command.split()[0].lstrip("/"))
            items.append({
                "command": command,
                "description": item["description"],
                "args": item.get("args_prompt", ""),
                "wizard": item.get("wizard", ""),
                "confirm": bool(item.get("confirm", False)),
            })
        sections.append({
            "title": section["title"],
            "description": section["description"],
            "items": items,
        })

    registered = sorted(COMMAND_REGISTRY) if "COMMAND_REGISTRY" in globals() else sorted(set(catalog_commands))
    return {
        "schema": "bago.command_catalog.v1",
        "headless_entrypoint": "bago exec /comando [args...]",
        "sections": sections,
        "registered_commands": registered,
        "catalog_commands": sorted(set(catalog_commands)),
    }



def _parse_project_args(args: list[str]) -> tuple[str, str]:
    actions = {"analyze", "status", "init", "link"}
    if not args:
        return "analyze", ""
    first = args[0].lower()
    if first in actions:
        return first, (args[1] if len(args) > 1 else "")
    root = args[0]
    action = args[1].lower() if len(args) > 1 and args[1].lower() in actions else "analyze"
    return action, root


def cmd_switch(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    positional, flags = _parse_args(args)
    if not positional:
        return {"ok": False, "message": "Uso: /switch <provider> [modelo] [--force]"}

    new_provider = positional[0]
    new_model = positional[1] if len(positional) > 1 else None
    force = bool(flags.get("force"))

    result = engine.execute(mgr, new_provider, new_model, force=force)
    return {
        "ok": result.ok,
        "message": result.message,
        "result": result,
    }


def cmd_models(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    provider = args[0] if args else None
    catalog = mgr.list_model_catalog(provider)
    models = [item["id"] for item in catalog]
    provider_name = provider or mgr.provider
    data = {
        "provider": provider_name,
        "mode": mgr.config.get("model_catalog.mode", "all"),
        "items": catalog,
    }
    if not models:
        return {"ok": True, "message": f"No hay modelos disponibles para {provider_name}.", "data": data}
    lines = [f"  • {m}" for m in models]
    return {
        "ok": True,
        "message": f"Modelos disponibles ({provider_name}, actual: {mgr.model}):\n" + "\n".join(lines),
        "data": data,
    }


def cmd_project(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    mod = _load_tool_module("project_memory", "project_memory.py")
    action, root = _parse_project_args(args)
    project_root = Path(root or mgr.base_path).expanduser().resolve()

    if action == "init":
        report = mod.init_project(project_root)
        message = (
            f"Initialized project memory at: {report['bago_dir']}\n"
            f"Created directories: {len(report['created_dirs'])}\n"
            f"Created files: {len(report['created_files'])}"
        )
        return {"ok": True, "message": message, "data": report}
    if action == "status":
        data = mod.status_data(project_root)
        return {"ok": True, "message": mod.format_status(data), "data": data}
    if action == "link":
        data = mod.link_project(project_root)
        message = (
            f"Linked project memory at: {data['root']}\n"
            f"Link mode: {data['link_mode']}\n"
            f"Marker: {data['marker']}"
        )
        return {"ok": True, "message": message, "data": data}
    if action == "analyze":
        data = mod.analyze_data(project_root)
        return {"ok": True, "message": mod.format_analysis(data), "data": data}
    return {"ok": False, "message": "Uso: /project [analyze|status|init|link] [ruta]"}


def cmd_status(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    s = mgr.status()
    lines = [
        f"Session ID : {s['session_id']}",
        f"Project    : {s.get('project_root', '—')}",
        f"Workspace  : {s.get('workspace_state_root', '—')}",
        f"Provider   : {s['provider']}",
        f"Model      : {s['model']}",
        f"Tool policy: {s.get('tool_approval_policy', 'ask')} (auto_allow_tools={s.get('auto_allow_tools', False)})",
        f"Modo BAGO  : [{s['bago_mode']}]",
        f"Agente     : {s['active_agent']}",
        f"Bridges    : {', '.join(s['active_bridges'])}",
        f"Health     : {'OK' if s['health']['ok'] else 'FAIL'} — {s['health']['detail']}",
        f"Messages   : {s['messages']}",
        f"Tokens     : {s['total_tokens']}",
        f"Calls      : {s['total_calls']}",
        f"Switches   : {s['switches']}",
    ]
    return {"ok": True, "message": "\n".join(lines), "data": s}


def cmd_roadmap(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    roadmap = roadmap_state_for_manager(mgr)
    lines = [
        f"Roadmap      : {roadmap['summary']}",
        f"Estado       : {roadmap['status']}",
        f"Version      : {roadmap['roadmap_version']}",
    ]
    for iteration in roadmap.get("iterations", []):
        lines.append(f"- {iteration['title']} [{iteration['status']}]")
        for phase in iteration.get("phases", []):
            lines.append(f"  · {phase}")
    return {"ok": True, "message": "\n".join(lines), "data": roadmap}


def cmd_session(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    s = mgr.status()
    data = {
        "session_id": s["session_id"],
        "project_root": s.get("project_root", ""),
        "workspace_state_root": s.get("workspace_state_root", ""),
        "provider": s["provider"],
        "model": s["model"],
        "tool_approval_policy": s.get("tool_approval_policy", "ask"),
        "auto_allow_tools": s.get("auto_allow_tools", False),
        "bago_mode": s["bago_mode"],
        "active_agent": s["active_agent"],
        "created_at": s["created_at"],
        "total_calls": s["total_calls"],
        "total_tokens": s["total_tokens"],
        "switches": s["switches"],
    }
    lines = [
        f"Session ID : {data['session_id']}",
        f"Project    : {data['project_root'] or '—'}",
        f"Workspace  : {data['workspace_state_root'] or '—'}",
        f"Provider   : {data['provider']}",
        f"Model      : {data['model']}",
        f"Tool policy: {data['tool_approval_policy']} (auto_allow_tools={data['auto_allow_tools']})",
        f"Modo BAGO  : [{data['bago_mode']}]",
        f"Agente     : {data['active_agent']}",
        f"Created    : {data['created_at']}",
        f"Total calls: {data['total_calls']}",
        f"Total tokens: {data['total_tokens']}",
    ]
    return {"ok": True, "message": "\n".join(lines), "data": data}


def cmd_mode(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Consulta o cambia el modo operativo BAGO."""
    if not args:
        return {
            "ok": True,
            "message": f"Modo BAGO activo: [{mgr.bago_mode}]\nUso: /mode B|A|G|O",
            "data": {"bago_mode": mgr.bago_mode},
        }
    try:
        result = mgr.set_bago_mode(args[0])
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}
    return {
        "ok": True,
        "message": f"Modo BAGO: [{result['previous_mode']}] -> [{result['mode']}]",
        "data": result,
    }


def cmd_save(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    mgr.save()
    return {"ok": True, "message": f"Sesión guardada: {mgr.session_id}"}


def cmd_load(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    if not args:
        return {"ok": False, "message": "Uso: /load <session_id>"}
    sid = args[0]
    loaded = SessionManager.load(sid, base_path=str(mgr.base_path))

    # Cerrar recursos de la sesión anterior (knowledge y embeddings tienen
    # conexiones SQLite propias; store no necesita cierre explícito)
    try:
        mgr.knowledge.close()
    except Exception:
        pass
    try:
        mgr.embedding_store.close()
    except Exception:
        pass

    # Transferir TODO el estado al manager activo.
    # CRÍTICO: store debe coincidir con la sesión cargada, o los mensajes
    # se escribirían al context.jsonl incorrecto (violación de session-first).
    mgr.session_id = loaded.session_id
    mgr.provider = loaded.provider
    mgr.model = loaded.model
    mgr.system_prompt = loaded.system_prompt
    mgr.bago_mode = loaded.bago_mode
    mgr.active_bridges = loaded.active_bridges
    mgr.agent_gateway = loaded.agent_gateway
    mgr.store = loaded.store                     # ← context store de la sesión cargada
    mgr.config = loaded.config
    mgr.credentials = loaded.credentials
    mgr.knowledge = loaded.knowledge
    mgr.embedding_store = loaded.embedding_store
    mgr.rl_pref = loaded.rl_pref
    mgr.rl_feedback = loaded.rl_feedback
    mgr.total_tokens = loaded.total_tokens
    mgr.total_calls = loaded.total_calls
    mgr.last_switch_at = loaded.last_switch_at
    mgr.switch_log = loaded.switch_log
    mgr._adapter = loaded._adapter
    mgr._init_info = loaded._init_info

    # Limpiar estado pendiente de tool calls de la sesión anterior
    mgr._pending_tools = None
    mgr._pending_normalized = None
    mgr._pending_user_message = ""
    mgr._pending_tools_kwargs = {}
    mgr.invalidate_providers_cache()

    # Rebuild SwitchEngine with current registry
    engine.adapters = mgr.adapters
    return {"ok": True, "message": f"Sesión cargada: {sid}"}


def cmd_providers(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    providers = mgr.available_providers()
    lines = []
    for p in providers:
        status = "✓" if p["configured"] else "✗"
        bridge = "bridge" if p["name"] in mgr.active_bridges else "solo"
        current = "actual" if p["name"] == mgr.provider else "      "
        lines.append(f"  [{status}] {p['name']:12} — {len(p['models'])} modelos · {bridge} · {current}")
    return {
        "ok": True,
        "message": "Providers registrados:\n" + "\n".join(lines),
        "data": {
            "providers": providers,
            "mode": mgr.config.get("model_catalog.mode", "all"),
            "active_bridges": list(mgr.active_bridges),
            "current_provider": mgr.provider,
            "current_model": mgr.model,
        },
    }


def cmd_bridges(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    if args:
        result = mgr.set_active_bridges(args)
        mgr.save()
    else:
        result = {"ok": True, "bridges": list(mgr.active_bridges)}
    return {"ok": True, "message": "Bridges activos: " + ", ".join(result["bridges"]), "data": result}


def cmd_orchestrate(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    prompt = " ".join(args).strip()
    if not prompt:
        return {"ok": False, "message": "Uso: /orchestrate <prompt>"}
    responses = mgr.orchestrate(prompt)
    mgr.save()
    message = "\n\n".join(
        f"[{provider} {'OK' if result['ok'] else 'FAIL'}]\n{result['content']}"
        for provider, result in responses.items()
    )
    return {"ok": any(result["ok"] for result in responses.values()), "message": message, "data": {"responses": responses}}


def cmd_turn_submit(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Entrada única para la UI unificada: chat o slash command en una sola vía."""
    text = " ".join(args).strip()
    if not text:
        return {"ok": False, "message": "Uso: /turn.submit <texto>"}

    if text.startswith("/"):
        return execute(text, mgr, engine)

    response = mgr.send(text)
    return {
        "ok": True,
        "message": response,
        "data": {
            "response": response,
            "mode": "chat",
            "text": text,
        },
    }


def cmd_menu(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    return {"ok": True, "message": "", "action": "menu"}


def cmd_help(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    return {"ok": True, "message": _build_help_text()}


def cmd_commands(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    mode = args[0].lower() if args else "text"
    if mode in {"json", "--json"}:
        return {
            "ok": True,
            "message": json.dumps(_catalog_payload(), ensure_ascii=False, indent=2),
            "data": _catalog_payload(),
        }
    return {"ok": True, "message": _build_help_text(), "data": _catalog_payload()}


def cmd_doctor(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, level: str = "ok") -> None:
        checks.append({"name": name, "ok": ok, "level": level if ok else "fail", "detail": detail})

    payload = _catalog_payload()
    registered = set(payload["registered_commands"])
    catalog = set(payload["catalog_commands"])
    missing_in_help = sorted(registered - catalog)
    missing_handler = sorted(catalog - registered)
    add(
        "command_catalog",
        not missing_in_help and not missing_handler,
        f"{len(catalog)} catalogados / {len(registered)} registrados"
        + (f"; faltan en help: {', '.join(missing_in_help)}" if missing_in_help else "")
        + (f"; sin handler: {', '.join(missing_handler)}" if missing_handler else ""),
    )
    add("headless_exec", True, "bago exec /comando [args...]")

    base_path = Path(getattr(mgr, "base_path", Path.cwd()))
    add("base_path", base_path.exists(), str(base_path))
    add("base_writable", os.access(base_path, os.W_OK), str(base_path))

    roles_file = _install_roles_read_path()
    if roles_file.exists():
        add("install_roles", True, str(roles_file))
    else:
        checks.append({
            "name": "install_roles",
            "ok": True,
            "level": "warn",
            "detail": f"No existe {roles_file}; se usaran fallbacks.",
        })

    try:
        status = mgr.status()
        health = status.get("health", {})
        checks.append({
            "name": "provider_health",
            "ok": bool(health.get("ok")),
            "level": "ok" if health.get("ok") else "warn",
            "detail": f"{status.get('provider')} / {status.get('model')}: {health.get('detail', 'sin detalle')}",
        })
    except Exception as exc:
        checks.append({
            "name": "provider_health",
            "ok": False,
            "level": "warn",
            "detail": f"No se pudo comprobar provider: {exc}",
        })

    lines = ["BAGO DOCTOR"]
    for check in checks:
        lines.append(f"  [{check['level']}] {check['name']:<18} {check['detail']}")
    blocking = [check for check in checks if check["level"] == "fail"]
    lines.append("")
    lines.append("Resultado: listo" if not blocking else "Resultado: requiere correccion")
    return {"ok": not blocking, "message": "\n".join(lines), "data": {"checks": checks}}


def cmd_update(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Lanza el actualizador de BAGO elevado con UAC."""
    import subprocess
    import json

    # Version actual
    try:
        root = Path(__file__).resolve().parents[2]
        data = json.loads((root / "versions.json").read_text(encoding="utf-8"))
        current = data.get("current", "desconocida")
    except Exception:
        current = "desconocida"

    installer = Path(__file__).resolve().parents[2] / "install-remote.ps1"
    if not installer.exists():
        return {
            "ok": False,
            "message": (
                f"Version actual: {current}\n"
                "No se encontro install-remote.ps1.\n"
                "Descarga la ultima version manualmente desde:\n"
                "  https://github.com/MarcValls/BAGO/releases"
            ),
        }

    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-Command",
                (
                    f"Start-Process powershell.exe "
                    f"-ArgumentList '-ExecutionPolicy Bypass -File \"{installer}\"' "
                    f"-Verb RunAs"
                ),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "ok": True,
            "message": (
                f"Version actual: {current}\n"
                "Lanzando actualizador elevado (UAC)...\n"
                "Aprueba la solicitud de administrador que aparecera en pantalla.\n"
                "BAGO se reiniciara cuando termine la instalacion."
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": (
                f"Error al lanzar actualizador: {exc}\n"
                "Ejecuta manualmente (como admin):\n"
                f"  powershell -ExecutionPolicy Bypass -File \"{installer}\""
            ),
        }


def cmd_quit(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    return {"ok": True, "message": "Bye.", "action": "quit"}


def cmd_feedback(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    if not args:
        return {"ok": False, "message": "Uso: /feedback <rating> donde rating es -1, 0, o 1"}
    if not bool(mgr.config.get("features.rl_learning", True)):
        return {"ok": False, "message": "RL learning está desactivado en la configuración."}
    try:
        rating = float(args[0])
        if rating < -1 or rating > 1:
            raise ValueError
    except ValueError:
        return {"ok": False, "message": "Rating debe ser un número entre -1.0 y 1.0"}
    mgr.feedback(rating)
    return {"ok": True, "message": f"Feedback registrado: {rating}"}


def cmd_suggest(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Sugiere el mejor provider/modelo basado en RL."""
    candidates = [(p["name"], m) for p in mgr.available_providers() for m in p["models"]]
    if not candidates:
        return {"ok": False, "message": "No hay candidates disponibles."}
    query_text = " ".join(args).strip()
    fingerprint = ""
    scope = "global"
    if query_text:
        fingerprint = mgr.rl_feedback.fingerprint_for(query_text)
        scope = f"consulta='{query_text}'"
    else:
        history = mgr.store.get_history()
        for entry in reversed(history):
            if entry.get("role") == "user":
                fingerprint = mgr.rl_feedback.fingerprint_for(entry.get("content", ""))
                scope = "ultima tarea"
                break
    best = mgr.rl_pref.best(fingerprint=fingerprint, candidates=candidates)
    if best:
        score = mgr.rl_pref.score(best[0], best[1], fingerprint)
        observations = mgr.rl_pref.observations(best[0], best[1], fingerprint)
        return {
            "ok": True,
            "message": (
                f"Sugerencia RL ({scope}): {best[0]}/{best[1]} "
                f"(score={score:.2f}, muestras={observations})"
            ),
        }
    return {"ok": False, "message": "Aún no hay datos suficientes para sugerir."}


def cmd_good(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Marca el último mensaje o uno por índice como 'good' (no diluible)."""
    index = -1
    if args:
        try:
            index = int(args[0])
        except ValueError:
            return {"ok": False, "message": "Uso: /good [índice] (default: último mensaje)"}
    ok = mgr.store.mark_good(index)
    if ok:
        return {"ok": True, "message": f"Mensaje {index} marcado como 'good' — no se diluirá en compresión."}
    return {"ok": False, "message": "No se pudo marcar el mensaje."}


def cmd_config(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Gestiona configuración: /config [get|set|list|reset] [clave] [valor]."""
    if not args or args[0] == "list":
        lines = [
            f"default_provider : {mgr.config.default_provider}",
            f"default_model    : {mgr.config.default_model}",
            f"temperature      : {mgr.config.get('temperature')}",
            f"streaming        : {mgr.config.feature_streaming}",
            f"tool_calling     : {mgr.config.get('features.tool_calling')}",
            f"tool_approval    : {current_tool_approval_policy(mgr)} (auto_allow_tools={mgr.config.get('features.auto_allow_tools')})",
            f"compression      : {mgr.config.feature_compression}",
            f"rl_learning      : {mgr.config.feature_rl}",
            f"auto_evolve      : {mgr.config.feature_auto_evolve}",
            f"ui.color         : {mgr.config.get('ui.color')}",
            f"ui.history       : {mgr.config.get('ui.history')}",
            f"ui.multiline     : {mgr.config.get('ui.multiline')}",
            f"prompt_on_start  : {mgr.config.get('ui.prompt_provider_on_start')}",
            f"workspace_retrieval: {mgr.config.get('features.workspace_retrieval')}",
            f"directory_context : {mgr.config.get('features.directory_context')}",
        ]
        return {"ok": True, "message": "Configuración:\n" + "\n".join(lines)}
    if args[0] == "get" and len(args) >= 2:
        return {"ok": True, "message": str(mgr.config.get(args[1], "(no definido)"))}
    if args[0] == "set" and len(args) >= 3:
        val = " ".join(args[2:])
        if val.lower() in ("true", "yes", "1"):
            parsed: Any = True
        elif val.lower() in ("false", "no", "0"):
            parsed = False
        else:
            try:
                parsed = int(val)
            except ValueError:
                try:
                    parsed = float(val)
                except ValueError:
                    parsed = val
        if args[1] == "features.tool_approval_policy":
            normalized = str(parsed)
            if hasattr(mgr, "set_tool_approval_policy"):
                normalized = mgr.set_tool_approval_policy(normalized)
            else:
                normalized = "always" if normalized == "always" else "ask"
                mgr.config.set("features.tool_approval_policy", normalized)
                mgr.config.set("features.auto_allow_tools", normalized == "always")
            return {"ok": True, "message": f"✓ features.tool_approval_policy = {normalized}"}
        if args[1] == "features.auto_allow_tools":
            normalized = "always" if bool(parsed) else "ask"
            if hasattr(mgr, "set_tool_approval_policy"):
                normalized = mgr.set_tool_approval_policy(normalized)
            else:
                mgr.config.set("features.tool_approval_policy", normalized)
                mgr.config.set("features.auto_allow_tools", normalized == "always")
            return {"ok": True, "message": f"✓ features.auto_allow_tools -> {bool(parsed)} (tool_approval_policy={normalized})"}
        mgr.config.set(args[1], parsed)
        if args[1] == "ui.color":
            R.set_color_enabled(bool(parsed))
        return {"ok": True, "message": f"✓ {args[1]} = {parsed}"}
    if args[0] == "reset":
        mgr.config.reset()
        return {"ok": True, "message": "Configuración restaurada a defaults."}
    return {"ok": False, "message": "Uso: /config [list|get <clave>|set <clave> <valor>|reset]"}


def cmd_ui(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Expone la configuracion UI tambien en ejecucion headless."""
    backend_root = Path(__file__).resolve().parents[2]
    candidates = (
        backend_root.parent / "frontend" / "public" / "ui_config.json",
        backend_root / "ui-react" / "public" / "ui_config.json",
    )
    config_path = next((path for path in candidates if path.exists()), candidates[-1])
    try:
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "message": f"No se pudo leer la configuracion UI: {exc}"}

    return {
        "ok": True,
        "message": json.dumps(config, ensure_ascii=False, indent=2),
        "data": {"config": config, "path": str(config_path)},
    }


def cmd_credentials(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Gestiona credenciales: /credentials [list|set <provider> <key> <valor>|delete ...]."""
    if not args or args[0] == "list":
        lines = []
        for provider in mgr.credentials.all_providers():
            keys = mgr.credentials.list_for_provider(provider)
            for key in keys:
                masked = keys[key][:4] + "***" if len(keys[key]) > 4 else "****"
                lines.append(f"  {provider}/{key}: {masked}")
        if not lines:
            return {"ok": True, "message": "No hay credenciales almacenadas localmente."}
        return {"ok": True, "message": "Credenciales almacenadas:\n" + "\n".join(lines)}
    if args[0] == "set" and len(args) >= 4:
        provider = args[1]
        key = args[2]
        value = " ".join(args[3:])
        mgr.credentials.set(provider, key, value)
        return {"ok": True, "message": f"✓ Credencial guardada para {provider}/{key}"}
    if args[0] == "delete" and len(args) >= 3:
        ok = mgr.credentials.delete(args[1], args[2])
        if ok:
            return {"ok": True, "message": f"✓ Credencial eliminada: {args[1]}/{args[2]}"}
        return {"ok": False, "message": "No se encontró la credencial."}
    return {"ok": False, "message": "Uso: /credentials [list|set <provider> <key> <valor>|delete <provider> <key>]"}


def cmd_tools(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Gestiona herramientas: /tools [list|enable|disable|approval]."""
    return handle_tools_command(mgr, args)


def cmd_scripts(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Lista baterías/scripts explícitos o filtra una batería: /scripts [battery]."""
    if not args:
        return {"ok": True, "message": mgr.script_registry.describe_catalog()}
    battery_id = args[0]
    battery = mgr.script_registry.get_battery(battery_id)
    if battery is None:
        known = ", ".join(item["id"] for item in mgr.script_registry.list_batteries())
        return {"ok": False, "message": f"Batería '{battery_id}' no registrada. Disponibles: {known}"}
    lines = [f"{battery.id}: {battery.description}", f"  falta: {battery.missing_script}"]
    if battery.fallback_tool:
        lines.append(f"  fallback: {battery.fallback_tool}")
    scripts = mgr.script_registry.list_scripts(battery.id)
    if scripts:
        for script in scripts:
            marker = "✓" if script["enabled"] and script["exists"] else "!"
            lines.append(f"  {marker} {script['id']} — {script['description']} ({script['path']})")
    else:
        lines.append("  (sin scripts registrados)")
    return {"ok": True, "message": "\n".join(lines)}


def cmd_allow(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Aprueba ejecución de herramientas pendientes: /allow [once|always]."""
    return handle_allow_command(mgr, args)


def cmd_deny(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Rechaza ejecución de herramientas pendientes: /deny [once|ask]."""
    return handle_deny_command(mgr, args)


def cmd_inventory(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Inventario de piezas usables: /inventory [tools|agents|scripts]."""
    from repl_inventory import gather_usable_inventory, format_usable_summary, format_category_lines
    data = gather_usable_inventory()
    if not args:
        s = data["summary"]
        lines = [
            f"Inventario usable de BAGO",
            f"  {format_usable_summary(data)}",
            f"  Total: {s['total']} piezas usables",
            "",
            "Usa /inventory tools, /inventory agents o /inventory scripts para ver el detalle.",
        ]
        return {"ok": True, "message": "\n".join(lines)}
    cat = args[0].lower()
    valid = {"tools", "agents", "scripts"}
    if cat not in valid:
        return {"ok": False, "message": f"Categoría inválida '{cat}'. Disponibles: {', '.join(sorted(valid))}"}
    item_lines = format_category_lines(data, cat)
    if not item_lines:
        return {"ok": True, "message": f"No hay piezas en '{cat}'."}
    return {"ok": True, "message": f"{cat} ({len(item_lines)}):\n" + "\n".join(item_lines)}


def cmd_plan(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Genera un plan paso a paso: /plan <tarea>."""
    if not args:
        if mgr.plan_engine.current_plan:
            return {"ok": True, "message": mgr.plan_engine.current_plan.to_text()}
        return {"ok": False, "message": "Uso: /plan <tarea> — describe lo que quieres planificar."}
    task = " ".join(args)
    prompt = mgr.plan_engine.generate_prompt(task)
    response = mgr.send(prompt)
    plan = mgr.plan_engine.create_plan(task, response)
    return {"ok": True, "message": plan.to_text(), "plan": plan}


def cmd_interpret(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Descompone una pregunta: /interpret <pregunta>."""
    if args and args[0].lower() in {"rules", "reglas", "contract", "contrato"}:
        info = rules_contract_info()
        validation = info.get("validation") or {}
        lines = [
            "Reglas del Interprete Reflexivo",
            f"  contract_version: {info.get('contract_version', '-')}",
            f"  source          : {info.get('source', '-')}",
            f"  path            : {info.get('path', '-') or '-'}",
            f"  objetivos       : {info.get('objective_count', 0)}",
            f"  interrogativos  : {info.get('interrogative_marker_count', 0)}",
            f"  deicticos       : {info.get('deictic_term_count', 0)}",
            f"  autorreferencia : {info.get('self_reference_term_count', 0)}",
            f"  validacion      : {'ok' if validation.get('ok') else 'fail'}",
        ]
        errors = validation.get("errors") or []
        if errors:
            lines.append("  errores         : " + "; ".join(str(item.get("name", item)) for item in errors))
        warnings = validation.get("warnings") or []
        if warnings:
            lines.append("  avisos          : " + "; ".join(str(item) for item in warnings))
        return {"ok": bool(validation.get("ok", False)), "message": "\n".join(lines), "data": info}

    if args and args[0].lower() in {"history", "historial", "audit", "auditoria", "log"}:
        limit = 10
        if len(args) >= 2:
            try:
                limit = max(1, min(int(args[1]), 50))
            except ValueError:
                limit = 10
        if not hasattr(mgr, "reflexive_audit_tail"):
            return {"ok": False, "message": "Auditoria reflexiva no disponible en este runtime."}
        report = mgr.reflexive_audit_tail(limit)
        items = report.get("items", [])
        if not items:
            return {"ok": True, "message": f"Sin auditorias reflexivas. Ledger: {report.get('path', '-')}", "data": report}
        lines = [f"Auditorias reflexivas ({len(items)}):", f"Ledger: {report.get('path', '-')}"]
        for item in items:
            lines.append(
                f"  {item.get('audit_id', '-')}: {item.get('intent', '-')} "
                f"conf={float(item.get('confidence', 0) or 0):.2f} "
                f"q={item.get('question_id', '-')}"
            )
        return {"ok": True, "message": "\n".join(lines), "data": report}

    text = " ".join(args).strip()
    if not text:
        return {
            "ok": False,
            "message": (
                "Uso: /interpret <pregunta> | /interpret history [n] | /interpret rules\n"
                "Ejemplo: /interpret Como formalizo esta pregunta?"
            ),
        }
    if hasattr(mgr, "analyze_reflexive_turn"):
        data = mgr.analyze_reflexive_turn(text)
        message = format_reflexive_report(data)
        if hasattr(mgr, "record_reflexive_command_audit"):
            data["reflexive_audit"] = mgr.record_reflexive_command_audit(
                analysis=data,
                response_content=message,
                command="/interpret",
            )
        return {
            "ok": True,
            "message": message,
            "data": data,
        }
    context = {
        "domain": "bago-chat",
        "conversation_history": [],
        "constraints": [],
        "metadata": {
            "provider": getattr(mgr, "provider", ""),
            "model": getattr(mgr, "model", ""),
            "session_id": getattr(mgr, "session_id", ""),
        },
    }
    result = analyze_question(text, context)
    return {
        "ok": True,
        "message": format_reflexive_report(result),
        "data": result.to_dict(),
    }


def cmd_autopilot(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Ejecuta una tarea autónomamente: /autopilot <tarea>.

    Genera un plan y ejecuta cada paso enviándolo al modelo.
    El modelo puede usar herramientas en cada paso.
    """
    if not args:
        return {"ok": False, "message": "Uso: /autopilot <tarea> — describe la tarea a ejecutar."}
    task = " ".join(args)

    # Generar plan
    prompt = mgr.plan_engine.generate_prompt(task)
    response = mgr.send(prompt)
    plan = mgr.plan_engine.create_plan(task, response)

    messages = [f"📋 Plan generado ({len(plan.steps)} pasos):", plan.to_text(), "", "🚀 Ejecutando..."]

    for step in plan.steps:
        mgr.plan_engine.mark_step(step, "running")
        step_prompt = f"Ejecuta este paso del plan: {step.description}"
        result = mgr.send(step_prompt)
        evidence = (result[:500],) if str(result).strip() else ()
        try:
            mgr.plan_engine.mark_step(step, "done", result[:500], evidence=evidence)
            messages.append(f"  ✓ Paso {step.number}: {step.description}")
            messages.append(f"    → {result[:200]}...")
        except ValueError:
            mgr.plan_engine.block_step(step, "sin evidencia suficiente", code="missing_evidence")
            messages.append(f"  ⧖ Paso {step.number}: {step.description}")
            messages.append("    → bloqueado por falta de evidencia")

    if any(step.status == "blocked" for step in plan.steps):
        plan.status = "blocked"
    elif any(step.status == "failed" for step in plan.steps):
        plan.status = "failed"
    elif all(step.status == "done" for step in plan.steps):
        plan.status = "done"
    return {"ok": True, "message": "\n".join(messages), "plan": plan}


def cmd_agents(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Lista agentes disponibles: /agents."""
    agents = mgr.agent_gateway.list_agents()
    active = mgr.agent_gateway.active.name
    lines = []
    for a in agents:
        marker = "●" if a.name == active else "○"
        lines.append(f"  {marker} {a.name:12} — {a.description}")
    return {"ok": True, "message": f"Agentes disponibles ({len(agents)}):\n" + "\n".join(lines)}


def cmd_agent(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Activa un agente: /agent <nombre>."""
    if not args:
        return {"ok": False, "message": "Uso: /agent <nombre> — activa un agente especializado. Usa /agents para ver disponibles."}
    name = args[0]
    result = mgr.activate_agent(name)
    if result.get("ok"):
        msg = f"✓ Agente activado: {name}"
        if result.get("warnings"):
            msg += "\n  Notas:\n" + "\n".join(f"    ! {w}" for w in result["warnings"])
        return {"ok": True, "message": msg}
    return {"ok": False, "message": result.get("error", "Error desconocido")}


def cmd_evolve(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Dispara la autoevolución de BAGO: /evolve.

    Reentrena el clasificador de intenciones con todo el historial y recarga el
    few-shot en caliente para que mejore en la sesión actual."""
    res = mgr.auto_evolve()
    if res.get("ok"):
        counts = res.get("counts", {})
        detail = " · ".join(f"{k}:{v}" for k, v in counts.items()) or "sin datos"
        bc = res.get("bc") or {}
        bc_line = ""
        if bc.get("ok"):
            bc_line = (f"\n  🤖 Política BC: {bc.get('samples', 0)} muestras "
                       f"(fuente: {bc.get('source', '?')}, loss: {bc.get('loss', 0):.3f})")
        elif bc.get("reason"):
            bc_line = f"\n  🤖 BC no entrenada: {bc['reason']}"
        return {
            "ok": True,
            "message": (
                "🧬 Reentrenamiento aplicado sin certificación independiente — "
                f"{res.get('total', 0)} ejemplos ({detail}){bc_line}"
            ),
        }
    return {
        "ok": False,
        "message": (
            f"🧬 {res.get('message', 'Autoevolución no completada')}\n"
            f"  responsable: {res.get('responsable', '?')}\n"
            f"  causa: {res.get('causa', '?')}\n"
            f"  prevención: {res.get('prevencion', '?')}"
        ),
    }


def cmd_train(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Verifica el dataset de comandos y frases nuevas en tiempo real dentro del chat.

    Uso: /train [split|all|fallos|/comando]
    split      → evalúa particiones train/val/test con frases nuevas.
    all / todo → split + regresión exacta del catálogo.
    fallos     → solo frases que fallan en la regresión exacta.
    /autopilot → filtra un comando concreto en la regresión exacta.

    La salida aparece línea a línea directamente en el chat (streaming).
    Retorna {"action": "streamed"} para que _handle_command no re-imprima nada.
    """
    import subprocess

    bago_root = Path(__file__).resolve().parents[2]
    exact_script = bago_root / "test_command_intents.py"
    novel_script = bago_root / "test_novel_phrases.py"
    if not exact_script.exists():
        return {"ok": False, "message": f"No se encontró {exact_script}. Reinstala BAGO."}
    if not novel_script.exists():
        return {"ok": False, "message": f"No se encontró {novel_script}. Reinstala BAGO."}

    subcmd = (args[0] if args else "demo").strip().lower()
    env = {**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    def _run_script(script: Path, extra_args: list[str], label: str) -> bool:
        argv = [sys.executable, "-u", str(script), *extra_args]
        print(f"\033[1m\033[96m▶ /train {label}\033[0m", flush=True)
        proc = None
        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                sys.stdout.write(raw_line)
                sys.stdout.flush()
            proc.wait(timeout=60)
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            if proc is not None:
                proc.kill()
            print("\033[91mTimeout (60 s) — proceso detenido.\033[0m", flush=True)
            return False
        except Exception as exc:
            print(f"\033[91mError al ejecutar train: {exc}\033[0m", flush=True)
            return False

    if subcmd in ("all", "todo", "todos", "--all"):
        novel_ok = _run_script(novel_script, [], "novel")
        exact_ok = _run_script(exact_script, [], "all")
        ok = novel_ok and exact_ok
    elif subcmd in ("fallos", "fail", "--fail-only"):
        ok = _run_script(exact_script, ["--fail-only"], "fail-only")
    elif subcmd in ("demo", "--demo", "", "split"):
        ok = _run_script(novel_script, [], "novel")
    elif subcmd.startswith("/"):
        ok = _run_script(exact_script, [subcmd], subcmd)
    else:
        ok = _run_script(novel_script, [], "novel")

    # Pie visual
    if ok:
        print("\033[92m✓ /train completado\033[0m", flush=True)
    else:
        print("\033[91m✗ /train terminó con errores\033[0m", flush=True)

    # Retorna "streamed" → _handle_command no re-imprimirá nada
    return {"ok": ok, "action": "streamed", "message": ""}


# Registry de comandos
COMMAND_REGISTRY: dict[str, Any] = {
    "menu": cmd_menu,
    "commands": cmd_commands,
    "doctor": cmd_doctor,
    "project": cmd_project,
    "switch": cmd_switch,
    "models": cmd_models,
    "status": cmd_status,
    "roadmap": cmd_roadmap,
    "session": cmd_session,
    "context": cmd_context,
    "mode": cmd_mode,
    "save": cmd_save,
    "load": cmd_load,
    "providers": cmd_providers,
    "bridges": cmd_bridges,
    "orchestrate": cmd_orchestrate,
    "turn.submit": cmd_turn_submit,
    "feedback": cmd_feedback,
    "suggest": cmd_suggest,
    "good": cmd_good,
    "config": cmd_config,
    "ui": cmd_ui,
    "credentials": cmd_credentials,
    "tools": cmd_tools,
    "scripts": cmd_scripts,
    "inventory": cmd_inventory,
    "allow": cmd_allow,
    "deny": cmd_deny,
    "interpret": cmd_interpret,
    "plan": cmd_plan,
    "autopilot": cmd_autopilot,
    "agents": cmd_agents,
    "agent": cmd_agent,
    "memory": cmd_memory,
    "evolve": cmd_evolve,
    "train": cmd_train,
    "update": cmd_update,
    "help": cmd_help,
    "quit": cmd_quit,
}


def execute(command_line: str, mgr: SessionManager, engine: SwitchEngine) -> dict:
    """Parsea una línea de comando y la ejecuta."""
    command_line = command_line.strip()
    if not command_line.startswith("/"):
        return {"ok": False, "message": "Comando debe empezar con /", "is_chat": True}

    try:
        parts = shlex.split(command_line[1:])
    except ValueError as exc:
        return {"ok": False, "message": f"Comando inválido: {exc}"}
    if not parts:
        return {"ok": False, "message": "Comando vacío."}

    cmd_name = parts[0].lower()
    args = parts[1:]
    func = COMMAND_REGISTRY.get(cmd_name)
    if not func:
        return {"ok": False, "message": f"Comando desconocido: /{cmd_name}. Usa /help."}

    try:
        return func(mgr, engine, args)
    except Exception as exc:
        return {"ok": False, "message": f"Error ejecutando /{cmd_name}: {exc}"}


def _run_tests() -> int:
    import tempfile
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse
    from session_manager import ADAPTER_REGISTRY

    class HybridTestAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("hybrid-test", config)

        def chat(self, messages: list[dict], model: str, **kwargs: Any) -> ProviderResponse:
            return ProviderResponse(content="ok", provider=self.provider_name, model_used=model)

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("hybrid-1", "hybrid-1", self.provider_name, 4096, 1024, "test", "local")]

        def health_check(self, timeout: float = 5.0) -> HealthStatus:
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok", models_available=1)

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

        def supports_embeddings(self) -> bool:
            return True

        def embed(self, texts: list[str], *, model: str = "") -> list[list[float]]:
            vectors = []
            for text in texts:
                vectors.append([1.0 if "directorio" in text else 0.0, 0.0, 0.0])
            return vectors

    ADAPTER_REGISTRY["hybrid-test"] = HybridTestAdapter
    with tempfile.TemporaryDirectory() as td:
        mgr = SessionManager(base_path=td, provider="hybrid-test", model="hybrid-1")
        try:
            engine = SwitchEngine(mgr.adapters)
            r = execute("/help", mgr, engine)
            assert r["ok"]
            r = execute("/menu", mgr, engine)
            assert r["ok"]
            assert r["action"] == "menu"
            r = execute("/status", mgr, engine)
            assert r["ok"]
            assert isinstance(r["message"], str)
            assert "Modo BAGO" in r["message"]
            r = execute("/mode G", mgr, engine)
            assert r["ok"]
            assert mgr.bago_mode == "G"
            r = execute("/agent coder", mgr, engine)
            assert r["ok"]
            assert mgr.agent_gateway.active.name == "coder"
            assert mgr.provider == "hybrid-test"
            assert mgr.model == "hybrid-1"
            r = execute("/save", mgr, engine)
            assert r["ok"]
            assert "Sesión guardada" in r["message"]
            mgr.rl_pref.add_reward(mgr.session_id, mgr.provider, mgr.model, 0.8, "tema_4")
            r = execute("/suggest tema", mgr, engine)
            assert r["ok"]
            assert "muestras=" in r["message"]
            r = execute("/tools enable", mgr, engine)
            assert r["ok"]
            assert mgr.config.get("features.tool_calling") is True
            r = execute("/scripts", mgr, engine)
            assert r["ok"]
            assert "diagnostics" in r["message"]
            r = execute("/memory hybrid-add directorio estable", mgr, engine)
            assert r["ok"]
            assert "embedding:" in r["message"]
            r = execute("/memory hybrid-search directorio", mgr, engine)
            assert r["ok"]
            assert "score=" in r["message"]
            r = execute("/unknown", mgr, engine)
            assert not r["ok"]
            print("commands.py --test: ALL PASS")
        finally:
            mgr.close()
            ADAPTER_REGISTRY.pop("hybrid-test", None)
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
