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

import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from session_manager import SessionManager
from switch_engine import SwitchEngine


class CommandError(Exception):
    pass


def _parse_args(args: list[str]) -> tuple[list[str], dict[str, str | bool]]:
    """Parsea argumentos posicionales y flags --key o --key=value."""
    positional: list[str] = []
    flags: dict[str, str | bool] = {}
    for arg in args:
        if arg.startswith("--"):
            if "=" in arg:
                key, val = arg[2:].split("=", 1)
                flags[key] = val
            else:
                flags[arg[2:]] = True
        else:
            positional.append(arg)
    return positional, flags


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
    data = {
        "provider": provider or mgr.provider,
        "mode": mgr.config.get("model_catalog.mode", "all"),
        "items": catalog,
    }
    if not models:
        return {"ok": True, "message": "No hay modelos disponibles.", "data": data}
    lines = [f"  • {m}" for m in models]
    return {
        "ok": True,
        "message": f"Modelos disponibles ({provider or mgr.provider}):\n" + "\n".join(lines),
        "data": data,
    }


def cmd_status(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    s = mgr.status()
    lines = [
        f"Session ID : {s['session_id']}",
        f"Provider   : {s['provider']}",
        f"Model      : {s['model']}",
        f"Health     : {'OK' if s['health']['ok'] else 'FAIL'} — {s['health']['detail']}",
        f"Messages   : {s['messages']}",
        f"Tokens     : {s['total_tokens']}",
        f"Calls      : {s['total_calls']}",
        f"Switches   : {s['switches']}",
    ]
    return {"ok": True, "message": "\n".join(lines), "data": s}


def cmd_session(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    s = mgr.status()
    data = {
        "session_id": s["session_id"],
        "provider": s["provider"],
        "model": s["model"],
        "created_at": s["created_at"],
        "total_calls": s["total_calls"],
        "total_tokens": s["total_tokens"],
        "switches": s["switches"],
    }
    lines = [
        f"Session ID : {data['session_id']}",
        f"Provider   : {data['provider']}",
        f"Model      : {data['model']}",
        f"Created    : {data['created_at']}",
        f"Total calls: {data['total_calls']}",
        f"Total tokens: {data['total_tokens']}",
    ]
    return {"ok": True, "message": "\n".join(lines), "data": data}


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
    mgr._providers_cache = None

    # Rebuild SwitchEngine with current registry
    engine.adapters = mgr.adapters
    return {"ok": True, "message": f"Sesión cargada: {sid}"}


def cmd_providers(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    providers = mgr.available_providers()
    lines = []
    for p in providers:
        status = "✓" if p["configured"] else "✗"
        lines.append(f"  [{status}] {p['name']:12} — {len(p['models'])} modelos")
    return {
        "ok": True,
        "message": "Providers registrados:\n" + "\n".join(lines),
        "data": {"providers": providers, "mode": mgr.config.get("model_catalog.mode", "all")},
    }


def cmd_menu(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    return {"ok": True, "message": "", "action": "menu"}


def cmd_help(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    text = """
Comandos disponibles:
  /menu                                    Abre menú interactivo de funciones
  /switch [provider] [modelo] [--force]   Cambia de provider/modelo (sin args = asistente guiado)
  /models [provider]                       Lista modelos disponibles
  /status                                  Estado de la sesión activa
  /session                                 Detalles de la sesión
  /save                                    Guarda sesión en disco
  /load [session_id]                       Carga sesión desde disco (sin args = asistente guiado)
  /providers                               Lista providers registrados
  /allow                                   Aprueba ejecución de herramientas pendientes
  /deny                                    Rechaza ejecución de herramientas pendientes
  /feedback [rating]                       Feedback explícito (-1 a 1; sin args = asistente)
  /suggest                                 Sugerencia RL de provider
  /good [índice]                           Marca mensaje como importante
  /config [list|get|set|reset]             Gestiona configuración (set sin args = asistente guiado)
  /credentials [list|set|delete]           Gestiona credenciales API (set sin args = asistente guiado)
  /tools [list|enable|disable]             Gestiona herramientas del modelo
  /plan <tarea>                           Genera plan paso a paso
  /autopilot <tarea>                       Ejecuta tarea autónomamente
  /evolve                                  Autoevoluciona: reentrena intenciones desde tu historial
  /agents                                  Lista agentes especializados
  /agent <nombre>                          Activa un agente (coder, reviewer, etc.; sin args = asistente)
  /memory [list|search|add|delete|hybrid-add|hybrid-search]  Gestiona base de conocimiento
  /update                                  Actualizar BAGO a la ultima version
  /help                                    Muestra esta ayuda
  /quit                                    Salir del chat
""".strip()
    return {"ok": True, "message": text}


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
            f"compression      : {mgr.config.feature_compression}",
            f"rl_learning      : {mgr.config.feature_rl}",
            f"prompt_on_start  : {mgr.config.get('ui.prompt_provider_on_start')}",
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
        mgr.config.set(args[1], parsed)
        return {"ok": True, "message": f"✓ {args[1]} = {parsed}"}
    if args[0] == "reset":
        mgr.config.reset()
        return {"ok": True, "message": "Configuración restaurada a defaults."}
    return {"ok": False, "message": "Uso: /config [list|get <clave>|set <clave> <valor>|reset]"}


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
    """Gestiona herramientas: /tools [list|enable|disable]."""
    if not args or args[0] == "list":
        tools = mgr.tool_registry.list_tools()
        if not tools:
            return {"ok": True, "message": "No hay herramientas registradas."}
        lines = []
        for t in tools:
            lines.append(f"  🔧 {t.name}: {t.description}")
        return {"ok": True, "message": f"Herramientas disponibles ({len(tools)}):\n" + "\n".join(lines)}
    if args[0] == "enable":
        mgr.config.set("features.tool_calling", True)
        return {"ok": True, "message": "Herramientas activadas. El modelo puede invocar tools."}
    if args[0] == "disable":
        mgr.config.set("features.tool_calling", False)
        return {"ok": True, "message": "Herramientas desactivadas. El modelo no invocará tools."}
    return {"ok": False, "message": "Uso: /tools [list|enable|disable]"}


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
    """Aprueba ejecución de herramientas pendientes: /allow."""
    result = mgr.approve_tools()
    return {"ok": True, "message": result}


def cmd_deny(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Rechaza ejecución de herramientas pendientes: /deny."""
    result = mgr.deny_tools()
    return {"ok": True, "message": result}


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
        step.status = "running"
        step_prompt = f"Ejecuta este paso del plan: {step.description}"
        result = mgr.send(step_prompt)
        step.status = "done"
        step.result = result[:500]  # Truncar para no saturar
        messages.append(f"  ✓ Paso {step.number}: {step.description}")
        messages.append(f"    → {result[:200]}...")

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


def cmd_memory(mgr: SessionManager, engine: SwitchEngine, args: list[str]) -> dict:
    """Gestiona la base de conocimiento: /memory [list|search|add|delete|hybrid-add|hybrid-search]."""
    if not args or args[0] == "list":
        recent = mgr.knowledge.list_recent(limit=10)
        if not recent:
            return {"ok": True, "message": "No hay recuerdos almacenados."}
        lines = [f"  {r['id']:3} | {r['created_at'][:19]} | {r['content'][:60]}..." for r in recent]
        return {"ok": True, "message": f"Recuerdos recientes ({len(recent)}):\n" + "\n".join(lines)}
    if args[0] == "search" and len(args) >= 2:
        query = " ".join(args[1:])
        results = mgr.knowledge.search(query, limit=5)
        if not results:
            return {"ok": True, "message": f"No se encontraron recuerdos para '{query}'."}
        lines = [f"  • {r['content'][:100]}... (sesión: {r['source_session']})" for r in results]
        return {"ok": True, "message": f"Resultados para '{query}':\n" + "\n".join(lines)}
    if args[0] == "add" and len(args) >= 2:
        content = " ".join(args[1:])
        mid = mgr.knowledge.add(content, source_session=mgr.session_id)
        return {"ok": True, "message": f"✓ Recuerdo añadido (ID: {mid})."}
    if args[0] == "hybrid-add" and len(args) >= 2:
        content = " ".join(args[1:])
        result = mgr.memory_add_hybrid(content)
        return {
            "ok": True,
            "message": (
                f"✓ Recuerdo híbrido añadido (ID: {result['memory_id']}, "
                f"embedding: {result['embedding_id']})."
            ),
        }
    if args[0] == "hybrid-search" and len(args) >= 2:
        query = " ".join(args[1:])
        results = mgr.memory_search_hybrid(query, limit=5)
        if not results:
            return {"ok": True, "message": f"No hay resultados híbridos para '{query}'."}
        lines = [
            f"  • score={r['score']:.3f} | memoria {r['memory_id']} | {r['content'][:80]}..."
            for r in results
        ]
        return {"ok": True, "message": f"Resultados híbridos para '{query}':\n" + "\n".join(lines)}
    if args[0] == "delete" and len(args) >= 2:
        try:
            mid = int(args[1])
            ok = mgr.knowledge.delete(mid)
            if ok:
                return {"ok": True, "message": f"✓ Recuerdo {mid} eliminado."}
            return {"ok": False, "message": f"No se encontró el recuerdo {mid}."}
        except ValueError:
            return {"ok": False, "message": "Uso: /memory delete <id>"}
    return {
        "ok": False,
        "message": (
            "Uso: /memory [list|search <query>|add <contenido>|hybrid-add <contenido>|"
            "hybrid-search <query>|delete <id>]"
        ),
    }


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
            "message": f"🧬 Autoevolución completada — {res.get('total', 0)} ejemplos ({detail}){bc_line}",
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
    """Verifica el dataset de entrenamiento de comandos en tiempo real dentro del chat.

    Uso: /train [demo|all|fallos|/comando]
    Sin args → demo rápido (15 frases).
    all / todo → suite completa + timeouts.
    fallos     → solo frases que fallan.
    /autopilot → filtra un comando concreto.

    La salida aparece línea a línea directamente en el chat (streaming).
    Retorna {"action": "streamed"} para que _handle_command no re-imprima nada.
    """
    import subprocess

    bago_root = Path(__file__).resolve().parents[2]
    script = bago_root / "test_command_intents.py"
    if not script.exists():
        return {"ok": False, "message": f"No se encontró {script}. Reinstala BAGO."}

    subcmd = (args[0] if args else "demo").strip().lower()
    argv = [sys.executable, "-u", str(script)]  # -u = unbuffered

    if subcmd in ("all", "todo", "todos", "--all"):
        argv += []                   # sin flags = demo + timeouts + suite completa
    elif subcmd in ("fallos", "fail", "--fail-only"):
        argv += ["--fail-only"]
    elif subcmd in ("demo", "--demo", ""):
        argv += ["--demo"]
    elif subcmd.startswith("/"):
        argv += [subcmd]             # filtrar un comando concreto, ej. /autopilot
    else:
        argv += ["--demo"]

    # Cabecera visual inline
    label = subcmd if subcmd else "demo"
    print(f"\033[1m\033[96m▶ /train {label}\033[0m", flush=True)

    try:
        env = {**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
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
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        print("\033[91mTimeout (60 s) — proceso detenido.\033[0m", flush=True)
        ok = False
    except Exception as exc:
        print(f"\033[91mError al ejecutar train: {exc}\033[0m", flush=True)
        ok = False

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
    "switch": cmd_switch,
    "models": cmd_models,
    "status": cmd_status,
    "session": cmd_session,
    "save": cmd_save,
    "load": cmd_load,
    "providers": cmd_providers,
    "feedback": cmd_feedback,
    "suggest": cmd_suggest,
    "good": cmd_good,
    "config": cmd_config,
    "credentials": cmd_credentials,
    "tools": cmd_tools,
    "scripts": cmd_scripts,
    "allow": cmd_allow,
    "deny": cmd_deny,
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

    parts = command_line[1:].split()
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
