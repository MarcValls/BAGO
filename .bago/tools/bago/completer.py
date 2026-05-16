"""
bago/completer.py — Autocompletado de comandos / para el REPL BAGO.

Cuando el usuario escribe "/" aparece un popup navegable con todos los
comandos disponibles filtrado en tiempo real. Soporta sub-comandos.
"""
from prompt_toolkit.completion import Completer, Completion

# ── Catálogo completo de comandos ─────────────────────────────────────────────

BAGO_COMMANDS: dict[str, str] = {
    # Credenciales / providers
    "/login":       "Providers y credenciales (github · gpt · anthropic · ollama)",
    # Modelos
    "/switch":      "Cambiar modelo activo: /switch <modelo|provider>",
    "/models":      "Listar todos los modelos disponibles",
    "/autoroute":   "Auto-routing on/off",
    # Multi-modelo
    "/chain":       "Pipeline de modelos: /chain m1->m2: prompt",
    "/ensemble":    "Paralelo + síntesis: /ensemble m1 m2: prompt",
    # Artefactos
    "/agents":      "Gestión de agentes BAGO",
    "/skills":      "Gestión de skills",
    "/roles":       "Modos/roles del orquestador",
    "/routing":     "Matriz de enrutamiento",
    "/new":         "Fábrica de artefactos (wizard LM) — 7 tipos",
    "/wizard":      "Alias de /new",
    "/fabrica":     "Alias de /new",
    # Sesión
    "/session":     "Gestión de sesión (temporal · disco · letargo · repliegue)",
    "/auth":        "Auth avanzada + providers (superset de /login)",
    "/auto":        "Modo autónomo on/off + nivel de confirmaciones",
    "/mode":        "Cambio rápido del modo del orquestador",
    "/sync":        "Sincronizar GitHub/USB + post-sync",
    "/memory":      "Base de conocimiento + memoria episódica",
    "/config":      "Configuración global persistente",
    # Framework
    "/framework":   "Vista evolutiva del framework BAGO",
    "/workspaces":  "Gestión de workspaces",
    "/projects":    "Gestión de proyectos (dentro del workspace activo)",
    # Utilidades
    "/status":      "Estado de la sesión actual",
    "/save":        "Guardar sesión en disco",
    "/clear":       "Limpiar historial de chat",
    "/help":        "Mostrar ayuda completa",
    "/exit":        "Salir de BAGO",
}

# Sub-comandos por comando (se activan al escribir, ej: "/agents ")
BAGO_SUBCOMMANDS: dict[str, list[tuple[str, str]]] = {
    "/login": [
        ("github",    "Login GitHub Copilot via gh CLI"),
        ("gpt",       "Login GPT / OpenAI API key"),
        ("openai",    "Alias de gpt"),
        ("codex",     "Alias de gpt"),
        ("anthropic", "API key de Anthropic → Claude"),
        ("ollama",    "Verificar Ollama local"),
    ],
    "/autoroute": [
        ("on",  "Activar auto-routing"),
        ("off", "Desactivar auto-routing"),
    ],
    "/agents": [
        ("add",    "Crear nuevo agente"),
        ("toggle", "Activar / desactivar agente"),
        ("set",    "Editar campo: set <nombre> <campo> <valor>"),
        ("del",    "Eliminar agente"),
    ],
    "/skills": [
        ("add",    "Crear nueva skill"),
        ("toggle", "Activar / desactivar skill"),
        ("set",    "Editar campo: set <nombre> <campo> <valor>"),
        ("del",    "Eliminar skill"),
    ],
    "/roles": [
        ("tasks",     "Ver preferencias por tipo de tarea"),
        ("offline",   "Detalle modo offline"),
        ("economico", "Detalle modo económico"),
        ("estandar",  "Detalle modo estándar"),
        ("full",      "Detalle modo full (todos los modelos)"),
    ],
    "/routing": [
        ("add",      "Añadir regla"),
        ("del",      "Eliminar regla"),
        ("move",     "Reordenar prioridad: move <id> up|down"),
        ("fallback", "Cambiar fallback: fallback <provider> <model>"),
    ],
    "/session": [
        ("temporal", "Activar modo sesión temporal (no escribe en disco)"),
        ("save",     "Guardar sesión en disco"),
        ("load",     "Cargar sesión anterior"),
        ("repliegue","Preparar repliegue (sync + hibernate)"),
        ("letargo",  "Letargo: sync + cerrar"),
    ],
    "/auto": [
        ("on",   "Activar modo autónomo (confirma solo lo crítico)"),
        ("off",  "Desactivar modo autónomo"),
        ("full", "Autónomo total: sin confirmaciones"),
    ],
    "/mode": [
        ("manual",    "Modo manual: tú eliges el modelo"),
        ("offline",   "Solo modelos locales (Ollama)"),
        ("economico", "Prioriza modelos baratos"),
        ("estandar",  "Balance coste/calidad"),
        ("full",      "Todos los modelos disponibles"),
    ],
    "/sync": [
        ("to-usb",   "Copiar estado al USB"),
        ("from-usb", "Importar estado desde USB"),
        ("github",   "Push al repositorio GitHub"),
        ("status",   "Ver estado de sincronización"),
    ],
    "/framework": [
        ("sprint",      "Estado del sprint actual"),
        ("health",      "Health check del framework"),
        ("ideas",       "Ideas de evolución pendientes"),
        ("componentes", "Listado de componentes registrados"),
    ],
    "/workspaces": [
        ("list",   "Listar workspaces"),
        ("new",    "Crear workspace"),
        ("switch", "Activar workspace"),
        ("del",    "Eliminar workspace"),
    ],
    "/projects": [
        ("list",   "Listar proyectos del workspace activo"),
        ("new",    "Crear proyecto"),
        ("switch", "Activar proyecto"),
        ("del",    "Eliminar proyecto"),
    ],
}

# Icono por categoría (se muestra junto a la descripción)
_ICONS: dict[str, str] = {
    "/login": "🔑", "/auth": "🔑",
    "/switch": "🔀", "/models": "📋", "/autoroute": "⚙", "/chain": "⛓", "/ensemble": "🔗",
    "/agents": "🤖", "/skills": "⚡", "/roles": "🎭", "/routing": "🗺", "/new": "✨",
    "/wizard": "✨", "/fabrica": "✨",
    "/session": "💾", "/auto": "🤖", "/mode": "🎛", "/sync": "🔄",
    "/memory": "🧠", "/config": "⚙", "/framework": "🏗", "/workspaces": "📁", "/projects": "📂",
    "/status": "📊", "/save": "💾", "/clear": "🧹", "/help": "❓", "/exit": "🚪",
}


class BagoCompleter(Completer):
    """
    Completer para el REPL BAGO.
    - Se activa cuando el buffer empieza con '/'
    - Primer token: filtra comandos
    - Segundo token: muestra sub-comandos si los hay
    """

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if not text.startswith("/"):
            return

        parts = text.split(None, 1)

        # ── Completando el comando principal ──────────────────────────────────
        if len(parts) == 1:
            typed = parts[0]
            for cmd, desc in BAGO_COMMANDS.items():
                if cmd.startswith(typed):
                    icon = _ICONS.get(cmd, "  ")
                    yield Completion(
                        cmd,
                        start_position=-len(typed),
                        display=cmd,
                        display_meta=f"{icon} {desc}",
                    )

        # ── Completando sub-comando ───────────────────────────────────────────
        elif len(parts) == 2:
            main_cmd = parts[0]
            sub_typed = parts[1]
            subs = BAGO_SUBCOMMANDS.get(main_cmd, [])
            for sub, sub_desc in subs:
                if sub.startswith(sub_typed):
                    yield Completion(
                        sub,
                        start_position=-len(sub_typed),
                        display=sub,
                        display_meta=sub_desc,
                    )
