"""
menus/main_menu.py — Menú principal de BAGO.

Se abre escribiendo "/" solo en el REPL.
Agrupa todos los comandos por categoría; navegable con ↑↓ + Enter.

Reglas:
  · Sin duplicados: cada comando aparece UNA sola vez.
  · Sin emojis repetidos dentro de la misma sección.
  · Ordenado por frecuencia de uso dentro de cada grupo.
"""

from ..ui import _menu_pick

# (key, label)  ─  key=None → separador visual
_ENTRIES = [
    # ── IA & Modelos ────────────────────────────────────────────────
    (None,          "─── 🤖  IA & Modelos ─────────────────────────"),
    ("/login",      "🔑  Login / Providers"),
    ("/switch",     "🔀  Cambiar modelo activo"),
    ("/models",     "📋  Ver modelos disponibles"),
    ("/status",     "📊  Estado de providers (salud en vivo)"),
    ("/autoroute",  "⚙   Auto-routing ON/OFF"),

    # ── Modos de conversación ────────────────────────────────────────
    (None,          "─── 🧠  Modos de conversación ────────────────"),
    ("/plan",       "📐  Modo PLAN  (razonar antes de actuar)"),
    ("/brainstorm", "💡  Modo BRAINSTORM  (explorar sin filtros)"),
    ("/mode",       "🎛   Modo del orquestador  (offline · full…)"),
    ("/auto",       "🌀  Modo autónomo  (bucle sin confirmaciones)"),

    # ── Multi-modelo ─────────────────────────────────────────────────
    (None,          "─── ⛓  Multi-modelo ──────────────────────────"),
    ("/chain",      "⛓   Pipeline de modelos  (chain)"),
    ("/ensemble",   "🔗  Paralelo + síntesis   (ensemble)"),

    # ── Herramientas & Artefactos ────────────────────────────────────
    (None,          "─── 🛠   Herramientas & Artefactos ────────────"),
    ("/new",        "✨  Crear artefacto  (wizard LM)"),
    ("/agents",     "🤖  Agentes BAGO"),
    ("/skills",     "⚡  Skills"),
    ("/roles",      "🎭  Roles / modos del orquestador"),
    ("/routing",    "🗺   Matriz de enrutamiento"),

    # ── Sesión & Sistema ─────────────────────────────────────────────
    (None,          "─── 💾  Sesión & Sistema ──────────────────────"),
    ("/session",    "💾  Gestión de sesión  (ver · guardar · cargar)"),
    ("/sync",       "🔄  Sincronizar GitHub / USB"),
    ("/memory",     "🧠  Memoria y conocimiento"),
    ("/config",     "⚙   Configuración global"),

    # ── Workspace ────────────────────────────────────────────────────
    (None,          "─── 📁  Workspace ────────────────────────────"),
    ("/framework",  "🏗   Framework evolutivo"),
    ("/workspaces", "📁  Workspaces"),
    ("/projects",   "📂  Proyectos"),

    # ── Utilidades ───────────────────────────────────────────────────
    (None,          "─── 🔧  Utilidades ───────────────────────────"),
    ("/clear",      "🧹  Limpiar historial de chat"),
    ("/help",       "❓  Ayuda y comandos"),
]


def _cmd_main_menu(session) -> str | None:
    """
    Abre el menú principal navegable.
    Devuelve la línea de comando seleccionada (p.ej. '/login')
    o None si el usuario canceló con Esc.
    """
    result = _menu_pick(
        "BAGO  /  Menú principal",
        "↑↓ navegar   Enter seleccionar   Esc volver",
        _ENTRIES,
    )
    return result
