#!/usr/bin/env python3
"""
bago_start_menu.py — Pantalla de inicio interactiva BAGO

Menú seleccionable con flechas (↑↓) y números (1-9).
Muestra modos de operación, proyectos recientes y acciones rápidas.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import subprocess
import sys
from pathlib import Path


import curses

BAGO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = BAGO_ROOT / ".bago" / "tools"
STATE = BAGO_ROOT / ".bago" / "state"
GS = STATE / "global_state.json"
RECENT_F = STATE / "recent_projects.json"

# Detección del ejecutable bago (platform-aware)
if sys.platform == "win32":
    _found = None
    for _ext in (".cmd", ".ps1", ".bat"):
        _cand = BAGO_ROOT / ("bago" + _ext)
        if _cand.exists():
            _found = _cand
            break
    if _found is None:
        _cand = BAGO_ROOT / "bago"
        if _cand.exists():
            _found = _cand
    BAGO_BIN = _found
else:
    BAGO_BIN = BAGO_ROOT / "bago"
    if not BAGO_BIN.exists():
        BAGO_BIN = None


def _read_global_state() -> dict:
    if not GS.exists():
        return {}
    try:
        return json.loads(GS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_recent_projects() -> list:
    if not RECENT_F.exists():
        return []
    try:
        data = json.loads(RECENT_F.read_text(encoding="utf-8"))
        return data.get("projects", [])[:5]
    except Exception:
        return []


def _is_devmode() -> bool:
    return bool(_read_global_state().get("devmode", False))


def _detect_install_mode() -> str:
    """Detecta si la instalación es portable, installed o project."""
    root = str(BAGO_ROOT)
    # Si hay runtime_contract.json en la raíz, es instalación oficial
    if (BAGO_ROOT / "runtime_contract.json").exists() or "Program Files" in root:
        return "installed"
    if "portable" in root.lower() or root.startswith(("E:\\", "D:\\", "F:\\")):
        return "portable"
    return "project"


def _detect_provider() -> str:
    """Detecta el provider activo."""
    gs = _read_global_state()
    provider = gs.get("provider", "")
    if provider:
        return provider
    # Fallback: comprobar variables de entorno o ejecutables
    if os.environ.get("COPILOT_CLI") or os.environ.get("GITHUB_TOKEN"):
        return "copilot"
    return "copilot"  # Default


def _health_status() -> tuple[str, str]:
    """Devuelve (emoji, texto) del estado de salud."""
    errors = []
    install_mode = _detect_install_mode()
    
    if not GS.exists():
        if install_mode == "portable":
            return "⚪", "inicializando (portable)"
        errors.append("global_state.json no existe")
    else:
        try:
            _read_global_state()
        except Exception:
            errors.append("global_state.json corrupto")
    
    if BAGO_BIN and not BAGO_BIN.exists():
        errors.append("ejecutable bago no encontrado")
    
    if errors:
        return "🔴", f"KO: {', '.join(errors[:2])}"
    return "🟢", "OK"


# ─── Logo ASCII ─────────────────────────────────────────────────────────────
LOGO = r"""
  ____    _    ____   ___
 |  _ \  / \  / ___| / _ \
 | |_) |/ _ \| |  _ | | | |
 |  _ </ ___ \ |_| || |_| |
 |____/_/   \_\____| \___/
""".strip()


def _build_options() -> list[dict]:
    """Construye la lista plana de opciones navegables."""
    opts: list[dict] = []

    opts.append({"type": "header", "label": "MODO DE OPERACIÓN"})

    chat_cmd = None
    if (TOOLS / "bago_chat.py").exists():
        chat_cmd = [sys.executable, str(TOOLS / "bago_chat.py")]
    elif BAGO_BIN and BAGO_BIN.suffix.lower() == ".cmd":
        chat_cmd = ["cmd", "/c", str(BAGO_BIN), "launch"]
    opts.append({"type": "action", "label": "💬  Modo CHAT", "cmd": chat_cmd, "desc": "Interfaz conversacional con BAGO"})

    create_cmd = None
    if (TOOLS / "bago" / "menus" / "wizard.py").exists():
        # Preferir wizard conversacional para crear TUI/agentes/skills
        create_cmd = [sys.executable, "-m", "bago.menus.wizard"]
    elif (TOOLS / "creation_mode.py").exists():
        create_cmd = [sys.executable, str(TOOLS / "creation_mode.py")]
    elif (BAGO_ROOT / "bago_core" / "launcher.py").exists():
        # Instalación completa: delegar a launcher.py next vía el wrapper .cmd
        if BAGO_BIN and BAGO_BIN.suffix.lower() == ".cmd":
            create_cmd = ["cmd", "/c", str(BAGO_BIN), "next"]
        elif BAGO_BIN:
            create_cmd = [sys.executable, str(BAGO_BIN), "next"]
    # Si no hay ni wizard ni creation_mode ni launcher.py, create_cmd sigue None (portable)
    opts.append({"type": "action", "label": "🛠️  Modo CREATE", "cmd": create_cmd, "desc": "Fábrica de artefactos BAGO (agentes, skills, TUI...)"})

    projects = _load_recent_projects()
    if projects:
        opts.append({"type": "header", "label": "PROYECTOS RECIENTES"})
        for i, p in enumerate(projects, start=1):
            name = p.get("repo_name", "?")[:28]
            mode = p.get("mode", "?")[:8]
            opts.append({
                "type": "project",
                "label": f"📁  {name}",
                "project": p,
                "desc": f"Modo: {mode}",
            })

    opts.append({"type": "header", "label": "ACCIONES RÁPIDAS"})
    opts.append({"type": "action", "label": "➕  Nuevo proyecto", "cmd": None, "desc": "bago siembra create <ruta>", "action": "new_project"})

    if _is_devmode() and BAGO_BIN:
        opts.append({"type": "action", "label": "🔧  Framework tools", "cmd": [sys.executable, str(BAGO_BIN), "devmode", "--info"], "desc": "Herramientas de desarrollo BAGO"})

    opts.append({"type": "header", "label": "INSTALACIONES Y LANZAMIENTO"})
    opts.append({"type": "action", "label": "🖥️  BAGO Dev Twin (desarrollo)", "cmd": None, "desc": "C:\\bago_true\\bago.ps1 dev twin", "action": "show_dev_twin_info"})
    opts.append({"type": "action", "label": "🖥️  BAGO Dev Twin (portable)", "cmd": None, "desc": "E:\\bago_portable\\bago.cmd twin", "action": "show_portable_info"})
    opts.append({"type": "action", "label": "🖥️  BAGO Dev Twin (usuario)", "cmd": None, "desc": "%LOCALAPPDATA%\\Programs\\BAGO\\bago.ps1 dev twin", "action": "show_user_info"})

    return opts


def _draw_menu(stdscr, opts: list[dict], selected: int):
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    # Colores
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)       # logo
    curses.init_pair(2, curses.COLOR_WHITE, -1)     # normal
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_CYAN)  # seleccionado
    curses.init_pair(4, curses.COLOR_YELLOW, -1)    # headers
    curses.init_pair(5, curses.COLOR_GREEN, -1)     # éxito / info
    curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_GREEN)   # seleccionado acción

    # Logo
    logo_lines = LOGO.splitlines()
    start_y = 1
    for i, line in enumerate(logo_lines):
        x = max(0, (w - len(line)) // 2)
        stdscr.addstr(start_y + i, x, line, curses.color_pair(1) | curses.A_BOLD)

    y = start_y + len(logo_lines) + 1

    # Versión / modo / instalación / provider / salud / fuente
    gs = _read_global_state()
    ver = gs.get("bago_version", "3.5.0")
    mode_tag = "DEV" if _is_devmode() else "USER"
    install_mode = _detect_install_mode()
    provider = _detect_provider()
    health_emoji, health_text = _health_status()

    info_lines = [
        f"BAGO {ver}  ·  {mode_tag} mode  ·  {install_mode.upper()}",
        f"Provider: {provider}  ·  Estado: {health_emoji} {health_text}",
        f"Fuente: {BAGO_ROOT}\\.bago",
    ]
    for line in info_lines:
        stdscr.addstr(y, max(0, (w - len(line)) // 2), line[:w-1], curses.color_pair(2))
        y += 1
    y += 1

    # Opciones
    visible_opts = [o for o in opts if o["type"] != "header"]
    action_idx = 0
    for i, opt in enumerate(opts):
        if y >= h - 3:
            break

        if opt["type"] == "header":
            stdscr.addstr(y, 4, f"── {opt['label']} ──", curses.color_pair(4) | curses.A_BOLD)
            y += 1
            continue

        is_sel = (action_idx == selected)
        num = action_idx + 1
        label = opt["label"]
        desc = opt.get("desc", "")

        if is_sel:
            line = f" ▶  {num}. {label}"
            stdscr.addstr(y, 4, line.ljust(w - 8), curses.color_pair(3) | curses.A_BOLD)
            if desc:
                stdscr.addstr(y + 1, 8, desc[:w - 10], curses.color_pair(5))
                y += 1
        else:
            line = f"    {num}. {label}"
            stdscr.addstr(y, 4, line[:w - 8], curses.color_pair(2))

        y += 1
        action_idx += 1

    # Footer
    footer = "  ↑↓ navegar  ·  1-9 seleccionar directo  ·  Enter ejecutar  ·  q salir"
    stdscr.addstr(h - 1, 0, footer[:w - 1], curses.color_pair(4))
    stdscr.refresh()


import time

def _run_command(cmd: list[str] | None, action: str | None = None, project: dict | None = None):
    """Ejecuta la acción seleccionada."""
    if action == "new_project":
        print("\n  Para crear un nuevo proyecto ejecuta:\n")
        print("    bago siembra create <ruta-del-proyecto>\n")
        input("  Pulsa Enter para volver al menú...")
        return

    if action == "show_dev_twin_info":
        print("\n  ═ BAGO Dev Twin — Instalación de DESARROLLO ═\n")
        print("    Ubicación : C:\\bago_true")
        print("    Launcher  : C:\\bago_true\\bago.ps1")
        print("    Comando   : C:\\bago_true\\bago.ps1 dev twin")
        print("    Nota      : Versión más actual con unimodel bridge + TimelineDB\n")
        input("  Pulsa Enter para volver al menú...")
        return

    if action == "show_portable_info":
        print("\n  ═ BAGO Dev Twin — Instalación PORTABLE ═\n")
        print("    Ubicación : E:\\bago_portable")
        print("    Launcher  : E:\\bago_portable\\bago.cmd")
        print("    Comando   : E:\\bago_portable\\bago.cmd twin")
        print("    Nota      : Para probar como usuario final sin instalar\n")
        input("  Pulsa Enter para volver al menú...")
        return

    if action == "show_user_info":
        print("\n  ═ BAGO Dev Twin — Instalación de USUARIO ═\n")
        print("    Ubicación : %LOCALAPPDATA%\\Programs\\BAGO")
        print("    Launcher  : %LOCALAPPDATA%\\Programs\\BAGO\\bago.ps1")
        print("    Comando   : %LOCALAPPDATA%\\Programs\\BAGO\\bago.ps1 dev twin")
        print("    Nota      : Instalada vía install.ps1 como usuario actual\n")
        input("  Pulsa Enter para volver al menú...")
        return

    if project:
        repo = project.get("repo_name", "")
        path = project.get("path", "")
        print(f"\n  ▶ Abriendo proyecto: {repo}\n")
        if path and Path(path).exists():
            try:
                os.chdir(path)
            except Exception:
                pass
        # Después de cambiar de proyecto, arrancamos chat
        cmd = [sys.executable, str(TOOLS / "bago_chat.py")]

    if not cmd:
        print("\n  ⚠ Esta opción no está disponible en esta instalación.\n")
        input("  Pulsa Enter para volver al menú...")
        return

    print("\n  ▶ Ejecutando...\n", flush=True)
    try:
        popen_kwargs: dict = {"cwd": str(BAGO_ROOT)}
        if sys.platform == "win32":
            # Aislar al hijo para que Ctrl+C no le llegue directamente
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(cmd, **popen_kwargs)
        try:
            while True:
                ret = process.poll()
                if ret is not None:
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n  ⏹ Interrumpido por usuario.", flush=True)
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            input("\n  Pulsa Enter para volver al menú...")
            return
    except FileNotFoundError as e:
        print(f"  ⚠ No se encontró el ejecutable: {e}", flush=True)
        input("\n  Pulsa Enter para continuar...")
    except Exception as e:
        print(f"  ⚠ Error al ejecutar: {e}", flush=True)
        input("\n  Pulsa Enter para continuar...")


def main() -> int:
    if not sys.stdout.isatty():
        print("BAGO start-menu requiere un terminal interactivo.")
        return 1

    opts = _build_options()
    visible = [o for o in opts if o["type"] != "header"]
    if not visible:
        print("No hay opciones disponibles.")
        return 1

    selected = 0
    chosen = None  # type: dict | None

    def _loop(stdscr):
        nonlocal selected, chosen
        curses.curs_set(0)
        while True:
            _draw_menu(stdscr, opts, selected)
            key = stdscr.getch()

            if key in (ord('q'), ord('Q'), 27):  # q, Q, Esc
                break
            elif key == curses.KEY_UP:
                selected = (selected - 1) % len(visible)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(visible)
            elif key in (10, 13):  # Enter
                chosen = visible[selected]
                break
            elif ord('1') <= key <= ord('9'):
                idx = key - ord('1')
                if 0 <= idx < len(visible):
                    chosen = visible[idx]
                    break

    while True:
        chosen = None
        try:
            curses.wrapper(_loop)
        except KeyboardInterrupt:
            print("\n  Saliendo del menú...")
            break
        except Exception as e:
            print(f"Error en menú de inicio: {e}")
            return 1

        if chosen is None:
            break  # usuario salió con q/Esc

        # Ejecutar FUERA de curses para no dejar el terminal roto
        try:
            _run_command(chosen.get("cmd"), chosen.get("action"), chosen.get("project"))
        except KeyboardInterrupt:
            print("\n  ⏹ Interrumpido. Volviendo al menú...")
            input("  Pulsa Enter...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
