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
    (None,          "  -- Providers & Login --------------------------"),
    ("/scan",       "  Scan  -- disponibles / potenciales / missing + tokens"),
    ("/login",      "  Login / Providers  -- registrar y gestionar cuentas"),
    ("/models",     "  Modelos disponibles"),

    # ── 2 · Modelo & Routing ─────────────────────────────────────────
    (None,          "  -- Modelo & Routing ---------------------------"),
    ("/switch",     "  Cambiar modelo activo"),
    ("/autoroute",  "  Auto-routing ON/OFF"),
    ("/routing",    "  Matriz de enrutamiento  -- ver y editar reglas"),
    ("/roles",      "  Roles del orquestador  -- definir comportamiento"),

    # ── 3 · Agentes & Skills ─────────────────────────────────────────
    (None,          "  -- Agentes & Skills ---------------------------"),
    ("/new",        "  Crear artefacto  -- wizard asistido por LM"),
    ("/agents",     "  Agentes  -- ver / crear / editar / activar"),
    ("/skills",     "  Skills  -- ver / crear / editar"),

    # ── 4 · Estrategias multi-modelo ─────────────────────────────────
    (None,          "  -- Estrategias multi-modelo -------------------"),
    ("/chain",      "  Pipeline  -- m1 genera, m2 refina"),
    ("/ensemble",   "  Paralelo + sintesis  -- varios modelos a la vez"),

    # ── 5 · Modos ────────────────────────────────────────────────────
    (None,          "  -- Modos --------------------------------------"),
    ("/generative", "  Modo generativo  -- offline / eco / standard / full / auto"),
    ("/auto",       "  Modo autonomo  -- bucle: balanceado / adaptativo"),
    ("/plan",       "  Modo PLAN  -- razonar y proponer antes de actuar"),
    ("/brainstorm", "  Modo BRAINSTORM  -- explorar ideas sin restricciones"),

    # ── 6 · Sesion & Configuracion ───────────────────────────────────
    (None,          "  -- Sesion & Configuracion ---------------------"),
    ("/status",     "  Estado actual  -- modelo / routing / tokens / salud"),
    ("/session",    "  Gestion de sesion  -- guardar / cargar / repliegue"),
    ("/sync",       "  Sincronizar  -- GitHub / USB"),
    ("/memory",     "  Memoria y conocimiento"),
    ("/config",     "  Configuracion global"),

    # ── 7 · Workspace & Proyectos ────────────────────────────────────
    (None,          "  -- Workspace & Proyectos ----------------------"),
    ("/framework",  "  Framework evolutivo  -- sprint / health / componentes"),
    ("/workspaces", "  Workspaces"),
    ("/projects",   "  Proyectos"),

    # ── 8 · Framework BAGO ─────────────────────────────────────────
    (None,          "  -- Framework BAGO (160 cmds) ------------------"),
    ("__all_cmds__","  > Todos los comandos BAGO..."),

    # ── 9 · Utilidades ───────────────────────────────────────────────
        # -- 10 . Sistema BAGO (v3.5) ----------------------------------
    (None,          "  -- Sistema BAGO -------------------------------"),
    ("!validate",   "  validate  -- manifest + state + pack"),
    ("!health",     "  health  -- salud del sistema"),
    ("!audit",      "  audit  -- auditoria de contratos"),
    ("!version",    "  version  -- verificar truth lock"),
    ("!autonomous", "  autonomous  -- ciclo autonomo (dry-run)"),
    ("!git dirty",  "  git dirty  -- estado del repo"),
    ("!test",       "  test  -- pytest suite"),
    ("!encoding",   "  encoding  -- guardia UTF-8"),
    ("!census",     "  census  -- catalogo de herramientas"),
    ("!map",        "  map  -- mapa del sistema"),
    ("!prompt-router", "  prompt-router  -- router de prompts WiFi"),
    ("!role-spiral",   "  role-spiral  -- roles en espiral"),
    ("!model-gate",    "  model-gate  -- fallback entre modelos"),
    ("!token-analytics", "  token-analytics  -- tracking de tokens"),
    ("!api-only",      "  api-only  -- modo solo API"),

    (None,          "  -- Utilidades ---------------------------------"),
    ("/help",       "  Ayuda  -- todos los comandos con descripcion"),
    ("/clear",      "  Limpiar historial de chat"),
]


def _all_cmds_menu(session) -> str | None:
    import importlib.util
    reg_path = Path(__file__).resolve().parents[2] / "tool_registry.py"
    entries = [("__back__", "  ↩  Volver al menú principal")]
    if reg_path.exists():
        try:
            spec = importlib.util.spec_from_file_location("_tr_menu", str(reg_path))
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(reg_path.parent))
            spec.loader.exec_module(mod)
            registry = getattr(mod, "REGISTRY", {})
            stabs = {"core": [], "dangerous": [], "experimental": [], "legacy": [], "internal": []}
            for name, entry in sorted(registry.items()):
                stab = getattr(entry, "stability", "unknown")
                stabs.setdefault(stab, []).append(entry)
            for stab in ("core", "dangerous", "experimental", "legacy", "internal"):
                if not stabs.get(stab):
                    continue
                entries.append((None, f"  -- {stab.upper()} ({len(stabs[stab])}) ---"))
                for e in sorted(stabs[stab], key=lambda x: x.cmd):
                    desc = (getattr(e, "description", "") or "")[:45]
                    label = f"  /{e.cmd}  -- {desc}" if desc else f"  /{e.cmd}"
                    entries.append((f"/{e.cmd}", label))
        except Exception:
            pass
    chosen = _menu_pick(
        "BAGO  /  Todos los comandos",
        "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
        entries,
    )
    if chosen == "__back__":
        return None
    return chosen


def _cmd_main_menu(session) -> str | None:
    """
    Abre el menú principal navegable.
    Devuelve la línea de comando seleccionada (p.ej. '/login')
    o None si el usuario canceló con Esc.
    """
    while True:
        selected = _menu_pick(
            "BAGO  /  Menu principal",
            "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
            _ENTRIES,
        )
        if selected == "__all_cmds__":
            sub = _all_cmds_menu(session)
            if sub:
                return sub
            continue
        return selected


