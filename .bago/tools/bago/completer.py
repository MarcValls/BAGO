"""
bago/completer.py — Autocompletado de comandos / para el REPL BAGO.

Cuando el usuario escribe "/" aparece un popup navegable con todos los
comandos disponibles filtrado en tiempo real. Soporta sub-comandos.
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from prompt_toolkit.completion import Completer, Completion

# ── Catálogo completo de comandos ─────────────────────────────────────────────

BAGO_COMMANDS: dict[str, str] = {
    # -- Providers & Login
    "/scan":        "[Providers] Scan: disponibles · potenciales · missing + tokens",
    "/login":       "[Providers] Registrar y gestionar cuentas de providers",
    "/logout":      "[Providers] Cerrar sesión y borrar credencial activa",
    "/models":      "[Providers] Listar modelos o detectar accesibles: /models detect",
    "/catalog":     "[Providers] Catálogo de modelos locales — instalar, comparar, joyas ocultas ✨",
    # -- Modelo & Routing
    "/switch":      "[Routing] Cambiar modelo activo: /switch <modelo|provider>",
    "/autoroute":   "[Routing] Auto-routing on/off",
    "/routing":     "[Routing] Matriz de enrutamiento — ver y editar reglas",
    "/route-graph": "[Routing] Grafo ASCII del routing, modelos candidatos y gate de contrato",
    "/roles":       "[Routing] Roles del orquestador — definir comportamiento",
    "/preset":      "[Routing] Presets estaticos del runtime: list | show | apply",
    "/contract":    "[Routing] Contrato activo de salida: show | set | clear",
    # -- Agentes & Skills
    "/new":         "[Agentes] Crear artefacto — wizard asistido por LM",
    "/agents":      "[Agentes] Ver / crear / editar / activar agentes",
    "/skills":      "[Agentes] Ver / crear / editar skills",
    # -- Multi-modelo
    "/chain":       "[Multi] Pipeline: m1 genera, m2 refina",
    "/ensemble":    "[Multi] Paralelo + sintesis — varios modelos a la vez",
    # -- Modos
    "/generative":  "[Modo] Modo generativo: offline / eco / standard / full / auto",
    "/gen":         "[Modo] Alias de /generative",
    "/mode":        "[Modo] Alias legacy de /generative",
    "/auto":        "[Modo] Modo autonomo — bucle: balanceado / adaptativo",
    "/plan":        "[Modo] Modo PLAN — razonar y proponer antes de actuar",
    "/brainstorm":  "[Modo] Modo BRAINSTORM — explorar ideas sin restricciones",
    "/tumba":       "[Modo] Modo TUMBA — copiar secretos sin enviárselos al LLM",
    # -- Sesion & Config
    "/session":     "[Sesion] Gestion de sesion (temporal · disco · letargo · repliegue)",
    "/sync":        "[Sesion] Sincronizar GitHub/GitLab/Codeberg/USB + snapshot nube",
    "/sendnow":     "[Cloud] Cliente explícito send.now: account | upload | files | folder",
    "/memory":      "[Sesion] Memoria y conocimiento",
    "/cwd":         "[Sesion] Ver o fijar la carpeta de trabajo actual",
    "/config":      "[Sesion] Configuracion global persistente",
    "/restart":     "[Sesion] Reiniciar BAGO y recargar runtime/modulos",
    # -- Workspace & Proyectos
    "/framework":   "[Workspace] Vista evolutiva del framework BAGO",
    "/workspaces":  "[Workspace] Gestion de workspaces",
    "/projects":    "[Workspace] Gestion de proyectos (dentro del workspace activo)",
    # -- Utilidades
    "/help":        "[Util] Mostrar ayuda completa con descripcion de comandos",
    "/clear":       "[Util] Limpiar historial de chat",
    "/status":      "[Util] Estado de la sesion actual",
    "/save":        "[Util] Guardar sesion en disco",
    "/exit":        "[Util] Salir de BAGO",
    # Aliases legacy
    "/wizard":      "[Alias] Alias de /new",
    "/fabrica":     "[Alias] Alias de /new",
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
        ("eco",       "Detalle modo eco"),
        ("standard",  "Detalle modo standard"),
        ("full",      "Detalle modo full (todos los modelos)"),
    ],
    "/routing": [
        ("add",      "Añadir regla"),
        ("del",      "Eliminar regla"),
        ("move",     "Reordenar prioridad: move <id> up|down"),
        ("fallback", "Cambiar fallback: fallback <provider> <model>"),
    ],
    "/route-graph": [
        ("--list-presets", "Listar presets del grafo/routing"),
        ("--task ", "Renderizar grafo para una tarea concreta"),
        ("--json", "Emitir el grafo y decision en JSON"),
        ("--preset contract-strict", "Usar preset contract-strict"),
    ],
    "/preset": [
        ("list", "Listar presets disponibles"),
        ("show", "Ver preset activo"),
        ("apply balanced", "Activar preset balanced"),
        ("apply local-first", "Activar preset local-first"),
        ("apply review-heavy", "Activar preset review-heavy"),
        ("apply contract-strict", "Activar preset contract-strict"),
    ],
    "/contract": [
        ("show", "Ver contrato activo"),
        ("set ", "Fijar contrato explicito"),
        ("clear", "Eliminar contrato activo"),
    ],
    "/session": [
        ("temporal", "Activar modo sesión temporal (no escribe en disco)"),
        ("save",     "Guardar sesión en disco"),
        ("load",     "Cargar sesión anterior"),
        ("repliegue","Preparar repliegue (sync + hibernate)"),
        ("letargo",  "Letargo: sync + cerrar"),
    ],
    "/cwd": [
        ("workspace", "Usar la ruta del workspace activo"),
        ("clear",     "Borrar el cwd persistido y volver al cwd normal"),
    ],
    "/auto": [
        ("on",   "Activar modo autónomo (confirma solo lo crítico)"),
        ("off",  "Desactivar modo autónomo"),
        ("full", "Autónomo total: sin confirmaciones"),
    ],
    "/generative": [
        ("offline",  "Solo modelos locales — sin red"),
        ("eco",      "Modelos economicos — rapido y barato"),
        ("standard", "Balance coste/calidad (por defecto)"),
        ("full",     "Todos los modelos — maxima calidad"),
        ("auto",     "BAGO decide segun contexto y complejidad"),
    ],
    "/tumba": [
        ("list",    "Ver claves guardadas (sin mostrar valores)"),
        ("listar",  "Alias de list"),
        ("del",     "Eliminar clave: /tumba del NombreClave"),
        ("rm",      "Alias de del"),
        ("clear",   "Vaciar la tumba completa"),
        ("vaciar",  "Alias de clear"),
        ("schema",  "Ver slots predefinidos por provider: /tumba schema telegram"),
        ("fill",    "Rellenar slots de un provider guiado: /tumba fill telegram"),
        ("check",   "Estado de slots de un provider: /tumba check stripe"),
        # providers más comunes como atajo rápido
        ("fill github",     "Rellenar slots de GitHub"),
        ("fill openai",     "Rellenar slots de OpenAI"),
        ("fill anthropic",  "Rellenar slots de Anthropic"),
        ("fill telegram",   "Rellenar slots de Telegram Bot"),
        ("fill discord",    "Rellenar slots de Discord Bot"),
        ("fill slack",      "Rellenar slots de Slack"),
        ("fill stripe",     "Rellenar slots de Stripe (pagos)"),
        ("fill supabase",   "Rellenar slots de Supabase"),
        ("fill aws",        "Rellenar slots de AWS"),
    ],
    "/mode": [
        ("offline",  "Solo modelos locales — sin red"),
        ("eco",      "Modelos economicos — rapido y barato"),
        ("standard", "Balance coste/calidad (por defecto)"),
        ("full",     "Todos los modelos — maxima calidad"),
        ("auto",     "BAGO decide segun contexto y complejidad"),
    ],
    "/sync": [
        ("to-usb",   "Copiar estado al USB"),
        ("from-usb", "Importar estado desde USB"),
        ("github",   "Push al repositorio GitHub"),
        ("status",   "Ver estado de sincronización"),
    ],
    "/sendnow": [
        ("account info", "Mostrar información de cuenta"),
        ("account stats", "Mostrar estadísticas de cuenta"),
        ("account dmca", "Ver reportes DMCA"),
        ("account trash", "Ver archivos eliminados"),
        ("upload file", "Subir archivo local"),
        ("upload remote", "Subir desde URL"),
        ("files list", "Listar archivos"),
        ("folder list", "Listar contenido de carpeta"),
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

# Icono por categoria (se muestra junto a la descripcion)
_ICONS: dict[str, str] = {
    "/login": ">>", "/auth": ">>",
    "/switch": "->", "/models": "=", "/autoroute": "*", "/chain": "+", "/ensemble": "+",
    "/agents": "~", "/skills": "~", "/roles": "~", "/routing": "~", "/new": "+",
    "/wizard": "+", "/fabrica": "+",
    "/session": "=", "/auto": "~", "/mode": "~", "/generative": "~", "/gen": "~", "/sync": ">>",
    "/route-graph": "=", "/preset": "=", "/contract": "=", "/restart": "x",
    "/memory": "~", "/cwd": "=", "/config": "=", "/framework": "=", "/workspaces": "=", "/projects": "=",
    "/status": "=", "/save": "=", "/clear": "x", "/help": "?", "/exit": "x",
    "/scan": ">>", "/plan": "~", "/brainstorm": "~", "/tumba": "x", "/sendnow": ">>",
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
            # "/" solo -> no mostrar popup; Enter abre el menu navegable (/cmd_main_menu)
            if typed == "/":
                return
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
