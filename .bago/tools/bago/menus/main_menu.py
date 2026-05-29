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

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import sys
from pathlib import Path
from ..ui import _menu_pick




# (key, label)  ─  key=None → separador visual (no navegable)
_ENTRIES = [

    # ── 1 · Providers & Login ────────────────────────────────────────
    (None,          "  -- Providers & Login --------------------------"),
    ("/scan",       "  Scan  -- disponibles / potenciales / missing + tokens"),
    ("/login",      "  Login / Providers  -- registrar y gestionar cuentas"),
    ("/logout",     "  Logout  -- cerrar sesión y borrar credencial activa"),
    ("/provider",   "  Activar/desactivar providers  -- ocultar servicios enteros"),
    ("/models",     "  Modelos disponibles / detectar accesibles"),

    # ── Modos BAGO ───────────────────────────────────────────────────
    (None,          "  -- Modos BAGO ---------------------------------"),
    ("!create",     "  Modo creación  — layout 3 paneles tipo AI Studio"),
    ("!focus",      "  Modo enfoque  — tarea activa minimalista"),
    ("!menu",       "  Menú interactivo curses  — navegación jerárquica"),

    # ── 2 · Modelo & Routing ─────────────────────────────────────────
    (None,          "  -- Modelo & Routing ---------------------------"),
    ("/switch",     "  Cambiar modelo activo"),
    ("/autoroute",  "  Auto-routing ON/OFF"),
    ("/routing",    "  Matriz de enrutamiento  -- ver y editar reglas"),
    ("/route-graph --task \"analizar routing actual\"", "  Grafo de routing  -- nodos, cadena y gate de contrato"),
    ("/roles",      "  Roles del orquestador  -- definir comportamiento"),
    ("/preset list","  Presets estaticos  -- balanced / local-first / review-heavy / contract-strict"),
    ("/contract show","  Contrato de salida  -- ver el contrato activo"),

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
    ("/cwd",        "  Carpeta de trabajo  -- ver / fijar ruta del chat"),
    ("/sync",       "  Sincronizar  -- GitHub / USB"),
    ("/sendnow",    "  Cliente send.now  -- account / upload / files / folder"),
    ("/memory",     "  Memoria y conocimiento"),
    ("/config",     "  Configuracion global"),

    # ── 7 · Workspace & Proyectos ────────────────────────────────────
    (None,          "  -- Workspace & Proyectos ----------------------"),
    ("/framework",  "  Framework evolutivo  -- sprint / health / componentes"),
    ("/workspaces", "  Workspaces"),
    ("/projects",   "  Proyectos"),

    # ── RL · Reinforcement Learning ──────────────────────────────────
    (None,          "  -- RL · Reinforcement Learning ----------------"),
    ("/rl-status",  "  RL Estado  -- transiciones, checkpoints, sugerencias"),
    ("/rl-demo",    "  RL Demo  -- ejecuta pipeline demo (sandbox, 0 riesgo)"),
    ("/rl-shadow",  "  RL Shadow  -- activar / desactivar recopilacion de datos reales"),
    ("/rl-train bc","  RL Entrenar BC  -- Behavioral Cloning con datos"),
    ("/rl-train ppo"," RL Entrenar PPO  -- online RL (~5 min)"),
    ("/rl-eval",    "  RL Evaluar  -- shadow mode con politica entrenada"),
    ("/rl-sandbox", "  RL Sandbox  -- activar / desactivar simulacion"),

    # ── 8 · Framework BAGO ─────────────────────────────────────────
    (None,          "  -- Framework BAGO (160 cmds) ------------------"),
    ("__all_cmds__","  > Todos los comandos BAGO..."),

    # ── 9 · Utilidades ───────────────────────────────────────────────
        # -- 10 . Sistema BAGO (v3.5) ----------------------------------
    (None,          "  -- Sistema BAGO -------------------------------"),
    ("/restart",    "  Reiniciar BAGO  -- recargar runtime y modulos"),
    ("!update",     "  update  -- buscar versiones nuevas y reparar entorno"),
    ("__all_cmds__","  > Catalogo completo de comandos..."),
    ("!validate",   "  validate  -- manifest + state + pack"),
    ("!health",     "  health  -- salud del sistema"),
    ("!audit",      "  audit  -- auditoria de contratos"),
    ("!version",    "  version  -- verificar truth lock"),
    ("!autonomous", "  autonomous  -- ciclo autonomo (dry-run)"),
    ("!git-dirty",  "  git dirty  -- estado del repo"),
    ("!test",       "  test  -- pytest suite"),
    ("!encoding",   "  encoding  -- guardia UTF-8"),
    ("!census",     "  census  -- catalogo de herramientas"),
    ("!map",        "  map  -- mapa del sistema"),
    ("!prompt-router", "  prompt-router  -- router de prompts WiFi"),
    ("!role-spiral",   "  role-spiral  -- roles en espiral"),
    ("!model-gate",    "  model-gate  -- fallback entre modelos"),
    ("!token-analytics", "  token-analytics  -- tracking de tokens"),
    ("!api-only",      "  api-only  -- modo solo API"),

    (None,          "  -- Portable -----------------------------------"),
    ("/portable",   "  BAGO Portable  -- detectar, crear o sincronizar pen drive"),
    (None,          "  -- Utilidades ---------------------------------"),
    ("/install-deps","  Instalar dependencias  -- prompt_toolkit, rich, etc."),
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
            stabs = {"core": [], "dangerous": [], "experimental": [], "legacy": [], "internal": [], "unknown": []}
            for name, entry in sorted(registry.items()):
                stab = getattr(entry, "stability", "unknown")
                stabs.setdefault(stab, []).append(entry)
            for stab in ("core", "dangerous", "experimental", "legacy", "internal", "unknown"):
                if not stabs.get(stab):
                    continue
                entries.append((None, f"  -- {stab.upper()} ({len(stabs[stab])}) ---"))
                for e in sorted(stabs[stab], key=lambda x: x.cmd):
                    desc = (getattr(e, "description", "") or "")[:45]
                    label = f"  /{e.cmd}  -- {desc}" if desc else f"  /{e.cmd}"
                    entries.append((f"!{e.cmd}", label))
        except Exception:
            pass
    chosen = _menu_pick(
        "BAGO  /  Todos los comandos",
        "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
        entries,
    )
    if chosen is None or chosen == "__back__":
        return "__back__"
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
            if sub and sub != "__back__":
                return sub
            continue
        return selected






