"""
menus/main_menu.py — Menú principal de BAGO.

Se abre escribiendo "/" solo en el REPL.
Agrupa todos los comandos por categoría; navegable con ↑↓ + Enter.
"""

from ..ui import _menu_pick

# (key, label)  ─  key=None → separador visual
_ENTRIES = [
    (None,         "─── Chat / Modelos ───────────────────────────"),
    ("/login",     "🔑  Login / Providers"),
    ("/switch",    "🔀  Cambiar modelo"),
    ("/models",    "📋  Ver modelos disponibles"),
    ("/autoroute", "⚙   Auto-routing ON/OFF"),
    (None,         "─── Multi-modelo ─────────────────────────────"),
    ("/chain",     "⛓   Pipeline de modelos  (chain)"),
    ("/ensemble",  "🔗  Paralelo + síntesis   (ensemble)"),
    (None,         "─── Artefactos ───────────────────────────────"),
    ("/new",       "✨  Crear artefacto  (wizard LM)"),
    ("/agents",    "🤖  Agentes BAGO"),
    ("/skills",    "⚡  Skills"),
    ("/roles",     "🎭  Roles / modos del orquestador"),
    ("/routing",   "🗺   Matriz de enrutamiento"),
    (None,         "─── Sesión / Sistema ─────────────────────────"),
    ("/session",   "💾  Gestión de sesión"),
    ("/auto",      "🤖  Modo autónomo"),
    ("/mode",      "🎛   Cambio rápido de modo"),
    ("/sync",      "🔄  Sincronizar GitHub / USB"),
    ("/memory",    "🧠  Memoria y conocimiento"),
    ("/config",    "⚙   Configuración global"),
    (None,         "─── Framework ────────────────────────────────"),
    ("/framework", "🏗   Framework evolutivo"),
    ("/workspaces","📁  Workspaces"),
    ("/projects",  "📂  Proyectos"),
    (None,         "─── Utilidades ───────────────────────────────"),
    ("/status",    "📊  Estado de sesión"),
    ("/save",      "💾  Guardar sesión"),
    ("/clear",     "🧹  Limpiar historial"),
    ("/auth",      "🔑  Auth avanzada"),
]


def _cmd_main_menu(session) -> str | None:
    """
    Abre el menú principal navegable.
    Devuelve la línea de comando seleccionada (p.ej. '/login')
    o None si el usuario canceló con Esc.
    """
    result = _menu_pick("BAGO  /  Menú principal", _ENTRIES)
    return result
