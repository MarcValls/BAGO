#!/usr/bin/env python3
"""
bago menu — Menú interactivo de comandos BAGO jerarquizado por flujo de trabajo.

Interfaz curses con sidebar de grupos + lista de comandos + preview.
La jerarquía sigue el flujo real de una sesión BAGO:
  Sesión → Ideas → Tarea activa → Calidad → Código → Agentes → ...

Navegación:
  ↑↓         mover dentro del grupo activo
  → / Tab    entrar en lista / siguiente grupo
  ←          volver al sidebar de grupos
  Enter      ejecutar el comando seleccionado
  q / Esc    salir sin ejecutar

Uso:
  bago menu               → abre el menú interactivo
  bago menu --list        → lista todos los grupos y comandos (sin interacción)
"""
from __future__ import annotations

import curses
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BAGO = ROOT / ".bago"

# ── Jerarquía de menú — basada en el flujo real de trabajo BAGO ───────────────
# Cada entrada: (nombre_grupo, [(cmd, descripción_corta, descripción_larga)])
MENU: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("🚀  Sesión", [
        ("start",            "Arranca sesión BAGO",          "Panel visual completo: health, workspace, tarea activa, ideas priorizadas"),
        ("status",           "Estado actual del sistema",    "Flujo activo + tarea pendiente + health score en 3 líneas"),
        ("hello",            "Bienvenida y contexto",        "Resumen de estado: workflow, sprint, voces CAP activas"),
        ("next",             "Siguiente idea → tarea",       "Toma la idea top del backlog y abre una tarea de trabajo"),
        ("devmode",          "Dev / User mode toggle",       "Developer: vista framework completa. User: vista project-first limpia"),
        ("workspace-select", "Elige espacio de trabajo",     "Menú: framework (self) | directorio padre | ruta externa. Persiste en repo_context.json"),
        ("recent-projects",  "Proyectos recientes",          "Historial de repos visitados con sesiones e ideas implementadas"),
    ]),
    ("💡  Ideas", [
        ("ideas",   "Ver backlog priorizado",       "Lista ideas ordenadas por contexto, sprint y urgencia"),
        ("cosecha", "Capturar nueva idea",          "Registra una idea nueva en bago.db con título, contexto y prioridad"),
        ("next",    "Aceptar idea top como tarea",  "Shortcut: toma la idea #1 y la convierte en tarea activa"),
        ("assign",  "Asignar idea a tarea",         "Convierte una idea específica en la tarea activa del sprint"),
        ("select",  "Seleccionar idea del backlog", "Navegación interactiva del backlog con filtros"),
        ("inbox",   "Bandeja de entrada",           "Ideas capturadas sin clasificar pendientes de triaje"),
        ("promote", "Promover idea a sprint",       "Sube una idea al sprint activo con prioridad ajustada"),
        ("reopen",  "Reabrir tarea cerrada",        "Reabre una tarea done para revisión o continuación"),
    ]),
    ("📋  Tarea activa", [
        ("task",     "Ver tarea actual",     "Muestra la tarea activa: idea, contexto, pasos pendientes"),
        ("done",     "Cerrar tarea actual",  "Registra la tarea como completada con evidencia"),
        ("workflow", "Gestionar workflow",   "Inicia, avanza o cierra el workflow activo del sprint"),
        ("flow",     "Estado del flujo",     "Vista del grafo de workflow: nodos, transiciones, estado"),
        ("sprint",   "Panel del sprint",     "Resumen del sprint: ideas completadas, velocidad, próximos"),
        ("goals",    "Objetivos del sprint", "Define y revisa los objetivos cualitativos del sprint"),
        ("scope",    "Scope de la tarea",    "Define qué archivos/módulos están en scope para esta tarea"),
    ]),
    ("✅  Calidad & Salud", [
        ("health",    "Score de salud 0-100",        "5 dimensiones: integridad, disciplina, decisiones, stale, consistencia"),
        ("validate",  "Validación completa",         "GO/FAIL en manifest, state y pack — ejecutar antes de cada commit"),
        ("audit",     "Auditoría de sesión",         "Trail completo: roles, contratos, evidencias, decisiones"),
        ("stale",     "Detectar estado obsoleto",    "Encuentra workflows abandonados, tareas huérfanas, state desincronizado"),
        ("sincerity", "Detector de promesas vacías", "Analiza si el agente cumplió lo que prometió en la sesión"),
        ("stability", "Informe de estabilidad",      "Tendencia histórica del health score con alertas de regresión"),
        ("siembra",   "Semillas de mejora",          "Registra aprendizajes de la sesión como semillas para ideas futuras"),
        ("heal",      "Reparar inconsistencias",     "Auto-repair de problemas detectados por health/validate"),
    ]),
    ("🔍  Análisis de código", [
        ("code-metrics", "Métricas del código",      "Complejidad ciclomática, duplicaciones, líneas por módulo"),
        ("code-search",  "Búsqueda semántica",       "Busca en el historial de código del proyecto con contexto"),
        ("lint-runner",  "Linter configurable",      "Ejecuta pyflakes/ruff/eslint según el tipo de proyecto"),
        ("rubber-duck",  "Debug asistido",           "Explica el problema en voz alta — el sistema hace preguntas"),
        ("naming",       "Check de nomenclatura",    "Verifica convenciones de nombres en el codebase"),
        ("hardcode",     "Detectar hardcoding",      "Encuentra valores hardcodeados que deberían ser config"),
        ("secrets",      "Auditoría de secretos",    "Detecta API keys, passwords y tokens en el código"),
        ("deps",         "Análisis de dependencias", "Estado de dependencias: outdated, vulnerables, no usadas"),
    ]),
    ("🤖  Agentes & IA", [
        ("agent",          "Gateway de agentes",   "Lanza y coordina agentes especializados del sistema BAGO"),
        ("autonomous",     "Bucle autónomo",       "Ejecuta ciclos autónomos de mejora sin intervención humana"),
        ("neural",         "Motor neural",         "Bus de mensajes SSE inter-agente: nodos, mapas, estado"),
        ("neural-toolbox", "Toolbox adaptativo",   "Convierte contexto en lenguaje natural a un toolbox configurado"),
        ("llm",            "Configuración LLM",    "Gestiona el modelo activo, temperatura y parámetros del LLM"),
        ("advisor",        "Consejero estratégico","Recomendaciones de next steps basadas en el estado del sistema"),
        ("toolsmith",      "Creador de tools",     "Genera nuevas herramientas BAGO desde especificación en lenguaje natural"),
        ("route",          "Router de intención",  "Mapea texto libre a comandos BAGO: 'quiero ver mis ideas' → bago ideas"),
    ]),
    ("📁  Workspace & Repos", [
        ("repo-clone",  "Clonar repositorio",    "Clona un repo GitHub en el workspace con auto-setup BAGO"),
        ("repo-list",   "Listar repos clonados", "Lista repositorios en el workspace con estado y health"),
        ("repo-switch", "Cambiar repo activo",   "Cambia el contexto activo entre repositorios del workspace"),
        ("git",         "Contexto git",          "Detect, map, git status, stale — vista git del workspace"),
        ("git-status",  "Estado git detallado",  "Estado completo: branch, staged, unstaged, remotes"),
        ("project",     "Gestión de proyecto",   "Crea, vincula o consulta el estado del proyecto activo"),
        ("context",     "Detector de contexto",  "Identifica automáticamente el tipo de proyecto y sugiere workflow"),
        ("map",         "Mapa del workspace",    "Vista estructural completa del workspace y sus relaciones"),
    ]),
    ("📊  Informes & Conocimiento", [
        ("weekly-report",  "Informe semanal",       "Resumen de la semana: ideas implementadas, salud, velocidad"),
        ("recientes",      "Actividad reciente",    "Commits, sesiones e ideas de los últimos N días"),
        ("snapshot",       "Snapshot del estado",   "Captura y compara snapshots del estado del sistema"),
        ("dashboard",      "Panel principal",       "Dashboard interactivo con todas las métricas del sistema"),
        ("work_matrix",    "Matriz de trabajo",     "Visualiza el trabajo por agente, capa y tipo de tarea"),
        ("search-history", "Búsqueda en historial", "Busca en el historial completo de sesiones BAGO"),
        ("docs",           "Documentación generada","Documentación auto-generada de todos los comandos activos"),
        ("chronicle",      "Crónica del proyecto",  "Historia narrativa del proyecto: decisiones, hitos, aprendizajes"),
    ]),
    ("⚙️  Configuración", [
        ("devmode",           "Dev / User mode",    "Alterna entre vista de framework completa y vista de proyecto"),
        ("alias-manager",     "Gestión de alias",   "Crea, edita y elimina alias personalizados para comandos"),
        ("env-manager",       "Variables de entorno","Gestiona .env del proyecto con validación y diff"),
        ("personality-panel", "Perfil del agente",  "Configura el tono, verbosidad y estilo del agente BAGO"),
        ("version",           "Versión del sistema","Versión actual de BAGO con changelog y notas de upgrade"),
        ("setup",             "Configuración inicial","Wizard de configuración inicial de BAGO en un nuevo sistema"),
        ("install",           "Instalar BAGO",      "Instala BAGO en un repositorio externo"),
    ]),
    ("🛠️  Infraestructura", [
        ("net-scan",      "Escaneo de red",      "Descubre puertos y servicios activos en la red local"),
        ("ping-server",   "Check de servicio",   "Verifica disponibilidad y latencia de un endpoint"),
        ("state-manager", "Gestor de estado",    "Split, materialize y merge del estado por capas"),
        ("seed",          "Semillas del sistema", "Gestiona las semillas de conocimiento del motor BAGO"),
        ("notify-desktop","Notificación desktop", "Envía notificación al sistema operativo"),
        ("notify-bago",   "Notificación BAGO",   "Envía notificación interna al sistema de presencia"),
        ("build-clean",   "Limpiar build",       "Elimina artefactos de build: __pycache__, dist, .eggs"),
        ("build-run",     "Ejecutar build",      "Ejecuta el pipeline de build del proyecto activo"),
    ]),
]

SIDEBAR_W = 20
PREVIEW_H = 6


# ── Colores ───────────────────────────────────────────────────────────────────

def _init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    -1)                 # activo / resaltado
    curses.init_pair(2, 8,                    -1)                 # dim
    curses.init_pair(3, curses.COLOR_BLACK,   curses.COLOR_CYAN)  # seleccionado con foco
    curses.init_pair(4, curses.COLOR_YELLOW,  -1)                 # títulos / footer
    curses.init_pair(5, curses.COLOR_GREEN,   -1)                 # nombre de comando
    curses.init_pair(6, curses.COLOR_WHITE,   -1)                 # texto normal
    curses.init_pair(8, curses.COLOR_MAGENTA, -1)                 # preview cmd
    curses.init_pair(9, curses.COLOR_BLACK,   curses.COLOR_YELLOW)# header bar


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


# ── Renderizado TUI ───────────────────────────────────────────────────────────

def _draw(stdscr: "curses._CursesWindow") -> str | None:
    _init_colors()
    curses.curs_set(0)

    active_group = 0
    active_cmd   = 0
    focus        = "sidebar"
    scroll_cmd   = 0
    result: str | None = None

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        list_x    = SIDEBAR_W + 1
        list_w    = w - list_x - 1
        list_area = h - PREVIEW_H - 3

        group_name, cmds = MENU[active_group]

        # ── Header ───────────────────────────────────────────────────────────
        right = f" {active_group + 1}/{len(MENU)} · {group_name.split('  ', 1)[-1]} "
        stdscr.addstr(0, 0, " " * (w - 1), curses.color_pair(9))
        stdscr.addstr(0, 2, "BAGO", curses.color_pair(9) | curses.A_BOLD)
        stdscr.addstr(0, 7, "· Menú de Comandos", curses.color_pair(9))
        try:
            stdscr.addstr(0, w - len(right) - 1, right, curses.color_pair(9))
        except curses.error:
            pass

        # ── Sidebar de grupos ─────────────────────────────────────────────────
        for i, (gname, _) in enumerate(MENU):
            y = 2 + i
            if y >= h - PREVIEW_H - 2:
                break
            label = f" {gname}"[:SIDEBAR_W].ljust(SIDEBAR_W)
            if i == active_group:
                attr = (curses.color_pair(3) | curses.A_BOLD) if focus == "sidebar" else (curses.color_pair(1) | curses.A_BOLD)
                stdscr.addstr(y, 0, label, attr)
            else:
                stdscr.addstr(y, 0, label, curses.color_pair(2))

        # Separador vertical
        for y in range(1, h - 1):
            try:
                stdscr.addstr(y, SIDEBAR_W, "│", curses.color_pair(2))
            except curses.error:
                pass

        # ── Cabecera de lista ─────────────────────────────────────────────────
        gname_clean = group_name.split("  ", 1)[-1] if "  " in group_name else group_name
        stdscr.addstr(1, list_x, f" {gname_clean}  ({len(cmds)} comandos)"[:list_w], curses.color_pair(4) | curses.A_BOLD)
        stdscr.addstr(2, list_x, "─" * (list_w - 1), curses.color_pair(2))

        # ── Lista de comandos ─────────────────────────────────────────────────
        visible = cmds[scroll_cmd: scroll_cmd + list_area]
        for i, (cmd, short, _) in enumerate(visible):
            abs_i = scroll_cmd + i
            y = 3 + i
            if y >= h - PREVIEW_H - 1:
                break
            if abs_i == active_cmd and focus == "list":
                bar = f" ▶  bago {cmd}  ─  {short}"
                stdscr.addstr(y, list_x, bar[:list_w].ljust(list_w - 1), curses.color_pair(3) | curses.A_BOLD)
            elif abs_i == active_cmd:
                stdscr.addstr(y, list_x + 1, "▶ ", curses.color_pair(1))
                stdscr.addstr(y, list_x + 3, f"bago {cmd}", curses.color_pair(1) | curses.A_BOLD)
                desc_x = list_x + 3 + len(f"bago {cmd}") + 2
                if desc_x < w - 2:
                    stdscr.addstr(y, desc_x, short[:w - desc_x - 1], curses.color_pair(6))
            else:
                stdscr.addstr(y, list_x + 3, "bago ", curses.color_pair(2))
                stdscr.addstr(y, list_x + 8, cmd, curses.color_pair(5))
                desc_x = list_x + 8 + len(cmd) + 2
                if desc_x < w - 2:
                    stdscr.addstr(y, desc_x, short[:w - desc_x - 1], curses.color_pair(2))

        # Indicadores de scroll
        if scroll_cmd > 0:
            try:
                stdscr.addstr(3, w - 3, "↑", curses.color_pair(4))
            except curses.error:
                pass
        if scroll_cmd + list_area < len(cmds):
            try:
                stdscr.addstr(2 + list_area, w - 3, "↓", curses.color_pair(4))
            except curses.error:
                pass

        # ── Preview del comando seleccionado ──────────────────────────────────
        prev_y = h - PREVIEW_H - 1
        stdscr.addstr(prev_y, list_x, "─" * (list_w - 1), curses.color_pair(2))
        if 0 <= active_cmd < len(cmds):
            cmd, short, long_desc = cmds[active_cmd]
            stdscr.addstr(prev_y + 1, list_x + 1, f"bago {cmd}", curses.color_pair(8) | curses.A_BOLD)
            words = long_desc.split()
            line, lines = "", []
            for word in words:
                if len(line) + len(word) + 1 > list_w - 4:
                    lines.append(line)
                    line = word
                else:
                    line = (line + " " + word).strip()
            if line:
                lines.append(line)
            for li, ln in enumerate(lines[:3]):
                stdscr.addstr(prev_y + 2 + li, list_x + 3, ln[:list_w - 4], curses.color_pair(6))

        # ── Footer ────────────────────────────────────────────────────────────
        footer = "  ↑↓ navegar  →/Tab: lista  ←: grupos  Enter: ejecutar  q: salir  "
        stdscr.addstr(h - 1, 0, footer[:w - 1], curses.color_pair(4))

        stdscr.refresh()

        # ── Input ─────────────────────────────────────────────────────────────
        key = stdscr.getch()

        if key in (ord('q'), 27):
            break
        elif focus == "sidebar":
            if key == curses.KEY_DOWN:
                active_group = (active_group + 1) % len(MENU)
                active_cmd = 0
                scroll_cmd = 0
            elif key == curses.KEY_UP:
                active_group = (active_group - 1) % len(MENU)
                active_cmd = 0
                scroll_cmd = 0
            elif key in (ord('\t'), curses.KEY_RIGHT, 10, 13):
                focus = "list"
        else:
            if key == curses.KEY_DOWN:
                active_cmd = _clamp(active_cmd + 1, 0, len(cmds) - 1)
                if active_cmd >= scroll_cmd + list_area:
                    scroll_cmd += 1
            elif key == curses.KEY_UP:
                active_cmd = _clamp(active_cmd - 1, 0, len(cmds) - 1)
                if active_cmd < scroll_cmd:
                    scroll_cmd -= 1
            elif key == curses.KEY_LEFT:
                focus = "sidebar"
            elif key == ord('\t'):
                active_group = (active_group + 1) % len(MENU)
                active_cmd = 0
                scroll_cmd = 0
                focus = "list"
            elif key in (10, 13):
                result = f"bago {cmds[active_cmd][0]}"
                break

    return result


# ── Modo --list (no interactivo) ──────────────────────────────────────────────

def _cmd_list() -> int:
    use_color = sys.stdout.isatty()

    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if use_color else text

    for group_name, cmds in MENU:
        print()
        print(c("1;33", f"  {group_name}"))
        print(c("2", "  " + "─" * 52))
        for cmd, short, _ in cmds:
            print(f"  {c('1;32', f'bago {cmd}'):<35}  {c('2', short)}")
    print()
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if "--list" in args:
        sys.exit(_cmd_list())

    if not sys.stdout.isatty():
        print("bago menu requiere un terminal interactivo. Usa --list para salida de texto.")
        sys.exit(1)

    result = curses.wrapper(_draw)

    if result:
        print(f"\n  ▶  {result}\n")
        bago_script = ROOT / "bago"
        cmd_parts = result.split()[1:]
        if bago_script.exists():
            sys.exit(subprocess.run([sys.executable, str(bago_script)] + cmd_parts).returncode)
    else:
        sys.exit(0)


def _self_test() -> None:
    assert len(MENU) == 10, f"Se esperaban 10 grupos, hay {len(MENU)}"
    for group_name, cmds in MENU:
        assert cmds, f"Grupo '{group_name}' sin comandos"
        for entry in cmds:
            assert len(entry) == 3, f"Entrada malformada en '{group_name}': {entry}"
    total = sum(len(c) for _, c in MENU)
    print(f"  3/3 tests pasaron  ({len(MENU)} grupos, {total} entradas de menú)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
