#!/usr/bin/env python3
"""
bago_menu.py — Selector interactivo de comandos BAGO.

Muestra los comandos disponibles ordenados por relevancia al contexto actual.
Navega con ↑↓, selecciona con Enter, sal con q/Esc.

No requiere librerías externas — solo stdlib (tty, termios, ANSI).
"""

import json
import os
import re
import subprocess
import sys
import tty
import termios
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE     = BAGO_ROOT / "state"
TOOLS     = BAGO_ROOT / "tools"
BAGO_BIN  = BAGO_ROOT.parent / "bago"

# ─── ANSI helpers ─────────────────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m"

CYAN   = lambda t: _c("1;36", t)
GREEN  = lambda t: _c("1;32", t)
YELLOW = lambda t: _c("1;33", t)
RED    = lambda t: _c("1;31", t)
BOLD   = lambda t: _c("1", t)
DIM    = lambda t: _c("2", t)
INVERT = lambda t: _c("7", t)

def _vlen(s: str) -> int:
    return len(_ANSI_RE.sub("", s))


# ─── Lectura de contexto ──────────────────────────────────────────────────────

def _read_context() -> dict:
    ctx = {"health": -1, "workflow": None, "task": None, "first_run": False}

    gs_path = STATE / "global_state.json"
    if gs_path.exists():
        try:
            data = json.loads(gs_path.read_text("utf-8"))
            _hs = data.get("health_score", data.get("system_health", {}))
            if isinstance(_hs, dict):
                ctx["health"] = _hs.get("score", _hs.get("overall_score", -1))
            elif isinstance(_hs, (int, float)):
                ctx["health"] = int(_hs)
            aw = data.get("sprint_status", {}).get("active_workflow")
            if isinstance(aw, dict):
                ctx["workflow"] = aw.get("title") or aw.get("code")
        except Exception:
            pass

    task_file = STATE / "pending_w2_task.json"
    if task_file.exists():
        try:
            t = json.loads(task_file.read_text("utf-8"))
            if t.get("status") != "done":
                ctx["task"] = t.get("title") or t.get("task")
        except Exception:
            pass

    try:
        sys.path.insert(0, str(TOOLS))
        from bago_db import _connect, DB_PATH
        if DB_PATH.exists():
            conn = _connect()
            row = conn.execute("SELECT COUNT(*) FROM guardian_runs").fetchone()
            conn.close()
            ctx["first_run"] = (row[0] if row else 0) == 0
    except Exception:
        ctx["first_run"] = False

    return ctx


# ─── Catálogo de comandos con descripciones ───────────────────────────────────

# (cmd, descripción corta)
_ALL_CMDS = [
    ("next",        "Empezar nueva tarea  — elige idea + inicia flujo"),
    ("done",        "Cerrar tarea actual  — registra progreso y sugiere qué sigue"),
    ("status",      "Estado actual        — flujo, tarea y salud del sistema"),
    ("ideas",       "Ver todas las ideas  — motor de prioridades BAGO"),
    ("health",      "Salud del sistema    — detalle de métricas y alertas"),
    ("hello",       "Guía y onboarding    — recorrido interactivo"),
    ("flow start",  "Iniciar flujo        — abre sesión de trabajo manual"),
    ("flow done",   "Cerrar flujo         — cierra sesión activa"),
    ("task",        "Ver tarea actual     — detalle de la tarea W2 pendiente"),
    ("dashboard",   "Dashboard            — visión global del sistema"),
    ("history",     "Historial de sesiones"),
    ("help",        "Ayuda y todos los comandos disponibles"),
]


def _rank_commands(ctx: dict) -> list[tuple[str, str, bool]]:
    """
    Devuelve lista de (cmd, desc, recommended) ordenada por relevancia.
    `recommended=True` en el primer ítem.
    """
    cmds = list(_ALL_CMDS)  # copia

    # Ocultar "done" si no hay tarea activa
    if not ctx["task"]:
        cmds = [(c, d) for c, d in cmds if c != "done"]

    # Determinar el recomendado
    if ctx["first_run"]:
        top = "hello"
    elif ctx["health"] >= 0 and ctx["health"] < 55:
        top = "health"
    elif ctx["task"]:
        top = "done"           # hay tarea abierta → ciérrala
    elif ctx["workflow"]:
        top = "status"         # flujo activo → status
    else:
        top = "next"           # default: empezar ciclo

    # Poner el recomendado primero
    reordered = [(c, d) for c, d in cmds if c == top]
    reordered += [(c, d) for c, d in cmds if c != top]

    return [(c, d, i == 0) for i, (c, d) in enumerate(reordered)]


# ─── Input de tecla única (raw mode) ─────────────────────────────────────────

def _getch() -> str:
    """Lee una tecla (posiblemente secuencia de escape). No bloquea el eco."""
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Leer resto de secuencia ANSI (e.g., [A)
            try:
                tty.setraw(fd)
                ch2 = sys.stdin.read(2)
                return ch + ch2
            except Exception:
                return ch
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─── Renderizado del menú ─────────────────────────────────────────────────────

_W = 62  # ancho interior del panel

def _render_menu(items: list[tuple[str, str, bool]], selected: int, ctx: dict) -> list[str]:
    lines = []
    sep   = CYAN("─" * _W)

    def _hdr(txt: str) -> str:
        padded = txt + " " * max(0, _W - _vlen(txt))
        return f"  {CYAN('│')} {padded} {CYAN('│')}"

    def _row(i: int, cmd: str, desc: str, rec: bool) -> str:
        is_sel = (i == selected)
        star   = YELLOW("★") if rec else " "
        num    = DIM(f"{i + 1:2d}")

        cmd_w  = 14
        cmd_s  = f"bago {cmd}"
        if is_sel:
            cmd_fmt = BOLD(GREEN(f"{cmd_s:<{cmd_w}}"))
        else:
            cmd_fmt = GREEN(f"{cmd_s:<{cmd_w}}")

        desc_max = _W - 2 - cmd_w - 8
        plain_desc = desc if _vlen(desc) <= desc_max else desc[:desc_max - 1] + "…"
        desc_fmt  = (BOLD(plain_desc) if is_sel else DIM(plain_desc))

        inner = f" {star} {num}  {cmd_fmt}  {desc_fmt}"
        inner_padded = inner + " " * max(0, _W - _vlen(inner) + 1)

        if is_sel:
            inner_padded = INVERT(inner_padded)

        return f"  {CYAN('│')}{inner_padded}{CYAN('│')}"

    # ── cabecera ──────────────────────────────────────────────────────────────
    lines.append(f"  {CYAN('┌' + '─' * _W + '┐')}")
    title = BOLD("BAGO") + DIM("  ¿Qué quieres hacer?")
    lines.append(_hdr(title))

    # Estado contextual en una línea
    parts = []
    if ctx["workflow"]:
        parts.append(f"flujo: {GREEN(ctx['workflow'][:20])}")
    if ctx["task"]:
        parts.append(f"tarea: {YELLOW(ctx['task'][:22])}")
    h = ctx["health"]
    if h >= 0:
        hcol = GREEN if h >= 80 else (YELLOW if h >= 55 else RED)
        parts.append(f"salud: {hcol(str(h) + '%')}")
    if parts:
        lines.append(_hdr(DIM("  ") + "  ".join(parts)))

    lines.append(f"  {CYAN('├' + '─' * _W + '┤')}")

    # ── filas de comandos ─────────────────────────────────────────────────────
    for i, (cmd, desc, rec) in enumerate(items):
        lines.append(_row(i, cmd, desc, rec))

    # ── pie ───────────────────────────────────────────────────────────────────
    lines.append(f"  {CYAN('├' + '─' * _W + '┤')}")
    nav = DIM("  ↑↓ navegar · Enter ejecutar · número directo · q salir")
    lines.append(_hdr(nav))
    lines.append(f"  {CYAN('└' + '─' * _W + '┘')}")

    return lines


def _draw(lines: list[str], prev_count: int) -> int:
    """Dibuja el menú, borrando las líneas previas."""
    if prev_count:
        # Subir cursor al inicio del menú
        sys.stdout.write(f"\033[{prev_count}A\033[J")
    for line in lines:
        print(line)
    sys.stdout.flush()
    return len(lines)


# ─── Ejecución del comando seleccionado ───────────────────────────────────────

def _execute(cmd: str) -> int:
    parts = cmd.split()
    argv  = [sys.executable, str(BAGO_BIN)] + parts
    print()
    try:
        result = subprocess.run(argv)
        return result.returncode
    except FileNotFoundError:
        print(f"  ⚠️  No se encontró el ejecutable bago en {BAGO_BIN}")
        return 1


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    if not sys.stdin.isatty():
        # Sin TTY: imprimir lista plana y salir
        ctx   = _read_context()
        items = _rank_commands(ctx)
        print()
        for i, (cmd, desc, rec) in enumerate(items):
            star = "★" if rec else " "
            print(f"  {star} {i+1:2d}  bago {cmd:<14}  {desc}")
        print()
        return 0

    ctx   = _read_context()
    items = _rank_commands(ctx)

    selected  = 0   # el recomendado empieza seleccionado
    prev_rows = 0
    print()  # una línea en blanco antes del menú

    while True:
        lines     = _render_menu(items, selected, ctx)
        prev_rows = _draw(lines, prev_rows)

        key = _getch()

        # Navegación
        if key in ("\x1b[A", "k"):         # ↑
            selected = (selected - 1) % len(items)
        elif key in ("\x1b[B", "j"):        # ↓
            selected = (selected + 1) % len(items)

        # Selección directa por número
        elif key.isdigit() and key != "0":
            idx = int(key) - 1
            if 0 <= idx < len(items):
                selected = idx
                key = "\r"   # ejecutar inmediatamente

        # Ejecutar
        if key in ("\r", "\n"):
            cmd = items[selected][0]
            # Limpiar el menú
            sys.stdout.write(f"\033[{prev_rows + 1}A\033[J")
            sys.stdout.flush()
            print(f"  {GREEN('❯')} bago {BOLD(cmd)}\n")
            return _execute(cmd)

        # Salir
        elif key in ("q", "Q", "\x1b", "\x03"):
            sys.stdout.write(f"\033[{prev_rows + 1}A\033[J")
            sys.stdout.flush()
            print(f"  {DIM('Salido.')}\n")
            return 0


if __name__ == "__main__":
    sys.exit(main())
