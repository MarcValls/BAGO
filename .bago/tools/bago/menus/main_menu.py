"""
menus/main_menu.py — Menú principal de BAGO.

Se abre escribiendo "/" solo en el REPL.
Agrupa todos los comandos por categoría; navegable con ↑↓ + Enter.

Reglas de renderizado multiplataforma:
  · Separadores SIN emoji en los guiones (emoji es 2 cols en Mac → desalinea ─)
  · Emoji solo en ítems, seguido de 2 espacios
  · Cada comando aparece UNA sola vez
  · Ordenado por frecuencia de uso dentro de cada grupo
"""

from ..ui import _menu_pick

# (key, label)  ─  key=None → separador visual (no navegable)
_ENTRIES = [

    # ── 1 · Providers & Login ────────────────────────────────────────
    (None,          "  ── Providers & Login ─────────────────────────"),
    ("/scan",       "🔍  Scan  — disponibles · potenciales · missing + tokens"),
    ("/login",      "🔑  Login / Providers  — registrar y gestionar cuentas"),
    ("/models",     "📋  Modelos disponibles"),

    # ── 2 · Modelo & Routing ─────────────────────────────────────────
    (None,          "  ── Modelo & Routing ───────────────────────────"),
    ("/switch",     "🔀  Cambiar modelo activo"),
    ("/autoroute",  "⚙   Auto-routing ON/OFF"),
    ("/routing",    "🗺   Matriz de enrutamiento  — ver y editar reglas"),
    ("/roles",      "🎭  Roles del orquestador  — definir comportamiento"),

    # ── 3 · Agentes & Skills ─────────────────────────────────────────
    (None,          "  ── Agentes & Skills ───────────────────────────"),
    ("/new",        "✨  Crear artefacto  — wizard asistido por LM"),
    ("/agents",     "🤖  Agentes  — ver · crear · editar · activar"),
    ("/skills",     "⚡  Skills  — ver · crear · editar"),

    # ── 4 · Estrategias multi-modelo ─────────────────────────────────
    (None,          "  ── Estrategias multi-modelo ───────────────────"),
    ("/chain",      "⛓   Pipeline  — m1 genera, m2 refina"),
    ("/ensemble",   "🔗  Paralelo + síntesis  — varios modelos a la vez"),

    # ── 5 · Modos de conversación ─────────────────────────────────────
    (None,          "  ── Modos de conversación ──────────────────────"),
    ("/plan",       "📐  Modo PLAN  — razonar y proponer antes de actuar"),
    ("/brainstorm", "💡  Modo BRAINSTORM  — explorar ideas sin restricciones"),
    ("/mode",       "🎛   Modo generativo  — offline · eco · full · standard"),
    ("/auto",       "🌀  Modo AUTONOMO  — bucle sin confirmaciones"),

    # ── 6 · Sesion & Configuracion ───────────────────────────────────
    (None,          "  ── Sesion & Configuracion ─────────────────────"),
    ("/status",     "📊  Estado actual  — modelo · routing · tokens · salud"),
    ("/session",    "💾  Gestion de sesion  — guardar · cargar · repliegue"),
    ("/sync",       "🔄  Sincronizar  — GitHub · USB"),
    ("/memory",     "🧠  Memoria y conocimiento"),
    ("/config",     "⚙   Configuracion global"),

    # ── 7 · Workspace & Proyectos ────────────────────────────────────
    (None,          "  ── Workspace & Proyectos ──────────────────────"),
    ("/framework",  "🏗   Framework evolutivo  — sprint · health · componentes"),
    ("/workspaces", "📁  Workspaces"),
    ("/projects",   "📂  Proyectos"),

    # ── 8 · Utilidades ───────────────────────────────────────────────
    (None,          "  ── Utilidades ─────────────────────────────────"),
    ("/help",       "❓  Ayuda  — todos los comandos con descripcion"),
    ("/clear",      "🧹  Limpiar historial de chat"),
]


def _cmd_main_menu(session) -> str | None:
    """
    Abre el menú principal navegable.
    Devuelve la línea de comando seleccionada (p.ej. '/login')
    o None si el usuario canceló con Esc.
    """
    return _menu_pick(
        "BAGO  /  Menu principal",
        "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
        _ENTRIES,
    )
