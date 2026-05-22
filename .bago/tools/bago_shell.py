#!/usr/bin/env python3
"""
bago_shell.py — Shell interactivo persistente BAGO.

Se inicia con `bago` y se queda abierto, como `gh copilot`.

Vista en reposo — 2 secciones siempre presentes:
  AHORA   → comandos relevantes para el momento del ciclo (cambia con el contexto)
  SISTEMA → salvaguardas core siempre visibles (health/validate/stability/audit/help)

Al escribir → filtra los 43 comandos del registry en tiempo real.
  ↑↓  navegar        número + Enter  selección rápida
  Tab completar      Esc limpiar     q / Ctrl+C  salir
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import tty
import termios
from datetime import datetime, timezone
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE     = BAGO_ROOT / "state"
TOOLS     = BAGO_ROOT / "tools"
BAGO_BIN  = BAGO_ROOT.parent / "bago"

# ─── ANSI ─────────────────────────────────────────────────────────────────────

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


# ─── Comandos curados para la vista de reposo ─────────────────────────────────

# Descripciones cortas para la sección AHORA
_WORKFLOW: dict[str, str] = {
    "next":       "Nueva tarea — idea + acepta + inicia flujo",
    "done":       "Cerrar tarea — registra progreso y sigue",
    "status":     "Estado actual — flujo, tarea y salud",
    "task":       "Ver detalle de la tarea W2 pendiente",
    "ideas":      "Motor de ideas — qué conviene hacer ahora",
    "flow start": "Iniciar flujo de trabajo manualmente",
    "flow done":  "Cerrar flujo activo",
    "hello":      "Guía y onboarding — recorrido paso a paso",
}

# Orden de comandos según fase del ciclo
_PHASE_ORDER: dict[str, list[str]] = {
    "low-health":  ["health", "validate", "stability", "status", "next"],
    "task-active": ["done", "status", "task", "next", "ideas"],
    "wf-active":   ["next", "status", "ideas", "task", "flow done"],
    "idle":        ["next", "ideas", "status", "health", "hello"],
}

# SISTEMA: salvaguardas core — siempre visibles
_SYSTEM: list[tuple[str, str]] = [
    ("health",    "Salud del sistema — métricas y alertas detalladas"),
    ("validate",  "Verificar integridad del pack"),
    ("stability", "Resumen de estabilidad del sistema"),
    ("audit",     "Auditoría completa del proyecto"),
    ("help",      "Todos los comandos disponibles (43)"),
]


def _now_cmds(ctx: dict) -> list[tuple[str, str]]:
    h = ctx["health"]
    if h >= 0 and h < 55:
        key = "low-health"
    elif ctx["task"]:
        key = "task-active"
    elif ctx["workflow"]:
        key = "wf-active"
    else:
        key = "idle"
    return [(c, _WORKFLOW[c]) for c in _PHASE_ORDER[key] if c in _WORKFLOW]


# ─── Lista completa del registry (para filtrado en tiempo real) ───────────────

_REGISTRY_CACHE: list[tuple[str, str]] | None = None


def _load_registry() -> list[tuple[str, str]]:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_bago_tool_registry", str(TOOLS / "tool_registry.py")
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        result = []
        for name, entry in sorted(mod.REGISTRY.items()):
            desc = getattr(entry, "description", "") or ""
            result.append((name, desc))
        return result
    except Exception:
        return list(_WORKFLOW.items()) + _SYSTEM


def _registry() -> list[tuple[str, str]]:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None:
        _REGISTRY_CACHE = _load_registry()
    return _REGISTRY_CACHE


def _filter(text: str) -> list[tuple[str, str]]:
    """Prefix-match primero, luego substring — sobre los 43 comandos del registry."""
    t     = text.lower()
    all_c = _registry()
    exact   = [(c, d) for c, d in all_c if c.lower().startswith(t)]
    partial = [(c, d) for c, d in all_c if t in c.lower() and not c.lower().startswith(t)]
    return exact + partial


# ─── Contexto del sistema ─────────────────────────────────────────────────────

def _elapsed(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        s    = datetime.fromisoformat(iso)
        now  = datetime.now(timezone.utc)
        mins = max(0, int((now - s).total_seconds() / 60))
        return f"{mins // 60}h{mins % 60:02d}m" if mins >= 60 else f"{mins}m"
    except Exception:
        return None


def _ctx() -> dict:
    c = {"health": -1, "workflow": None, "wf_elapsed": None, "task": None}
    try:
        data = json.loads((STATE / "global_state.json").read_text("utf-8"))
        # Fuente correcta: guardian_findings.health_pct (valor numérico real)
        h = data.get("guardian_findings", {}).get("health_pct")
        if h is None:
            sh = data.get("system_health", {})
            h  = sh.get("overall_score") if isinstance(sh, dict) else None
        c["health"] = int(h) if h is not None else -1
        aw = data.get("sprint_status", {}).get("active_workflow")
        if isinstance(aw, dict):
            c["workflow"]   = aw.get("title") or aw.get("code")
            c["wf_elapsed"] = _elapsed(aw.get("started"))
    except Exception:
        pass
    try:
        t = json.loads((STATE / "pending_w2_task.json").read_text("utf-8"))
        if t.get("status") != "done":
            c["task"] = t.get("title") or t.get("task")
    except Exception:
        pass
    return c


def _recommend(ctx: dict) -> str:
    h = ctx["health"]
    if h >= 0 and h < 55:
        return "health"
    if ctx["task"]:
        return "done"
    if ctx["workflow"]:
        return "status"
    return "next"


# ─── Input raw con soporte ESC simple ────────────────────────────────────────

def _getch() -> str:
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        b  = sys.stdin.buffer.read(1)
        ch = b.decode("utf-8", errors="replace")
        if ch == "\x1b":
            # Non-blocking para distinguir ESC solo de secuencia (ej: \x1b[A)
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            try:
                rest = sys.stdin.buffer.read(2)
                if rest:
                    return ch + rest.decode("utf-8", errors="replace")
            except (BlockingIOError, OSError):
                pass
            finally:
                fcntl.fcntl(fd, fcntl.F_SETFL, fl)
            return ch  # ESC puro → limpiar buffer
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─── Render ───────────────────────────────────────────────────────────────────

_W = 66


def _row(txt: str = "") -> str:
    padded = txt + " " * max(0, _W - _vlen(txt))
    return f"  {CYAN('│')} {padded} {CYAN('│')}"


def _sep_label(label: str) -> str:
    dashes = max(1, _W - len(label) - 5)
    inner  = f" {DIM('┄' * 2)} {DIM(label)} {DIM('┄' * dashes)}"
    padded = inner + " " * max(0, _W - _vlen(inner))
    return f"  {CYAN('│')}{padded}{CYAN('│')}"


def _cmd_row(i: int, cmd: str, desc: str, is_sel: bool, is_rec: bool) -> str:
    star     = YELLOW("★") if is_rec else " "
    idx      = DIM(f"{i + 1:2d}")
    cmd_s    = f"bago {cmd}"
    cmd_w    = 20
    cmd_fmt  = (BOLD(GREEN(f"{cmd_s:<{cmd_w}}")) if is_sel
                else GREEN(f"{cmd_s:<{cmd_w}}"))
    desc_max = _W - cmd_w - 8
    d_plain  = desc if len(desc) <= desc_max else desc[:desc_max - 1] + "…"
    desc_fmt = (BOLD(d_plain) if is_sel else DIM(d_plain))
    inner    = f" {star} {idx}  {cmd_fmt}  {desc_fmt}"
    padded   = inner + " " * max(0, _W - _vlen(inner) + 1)
    return f"  {CYAN('│')}{INVERT(padded) if is_sel else padded}{CYAN('│')}"


def _header_lines(ctx: dict) -> list[str]:
    h    = ctx["health"]
    hcol = (GREEN if h >= 80 else YELLOW if h >= 55 else RED) if h >= 0 else DIM
    hstr = hcol(f"{h}%") if h >= 0 else DIM("—")
    wstr = GREEN(ctx["workflow"][:20]) if ctx["workflow"] else DIM("ninguno")
    estr = DIM(f" ({ctx['wf_elapsed']})") if ctx.get("wf_elapsed") else ""
    tstr = YELLOW(ctx["task"][:22]) if ctx["task"] else DIM("—")
    return [
        f"  {CYAN('┌' + '─' * _W + '┐')}",
        _row(BOLD("BAGO Shell") + DIM("  ·  q o Ctrl+C para salir")),
        _row(f"  salud {hstr}   flujo {wstr}{estr}   tarea {tstr}"),
        f"  {CYAN('├' + '─' * _W + '┤')}",
    ]


def _render(buf: str, sel: int, ctx: dict) -> list[str]:
    out = []
    rec = _recommend(ctx)
    out += _header_lines(ctx)

    if buf:
        # ── Modo filtro: muestra todos los comandos que coinciden ─────────────
        cmds    = _filter(buf)
        total   = len(_registry())
        visible = cmds[:10]

        for i, (cmd, desc) in enumerate(visible):
            out.append(_cmd_row(i, cmd, desc, i == sel, cmd == rec))

        if not visible:
            out.append(_row(DIM(f"  Sin resultados para '{buf}' — prueba con bago help")))

        out.append(f"  {CYAN('├' + '─' * _W + '┤')}")
        out.append(_row(f"  {CYAN('❯')} {GREEN(buf)}{BOLD(GREEN('▌'))}"))
        n = len(cmds)
        if n == 0:
            hint = DIM(f"  0 resultados · Esc para limpiar · bago help para ver todos")
        elif n == 1:
            hint = DIM(f"  1 de {total} comandos · Enter ejecutar · Esc limpiar")
        else:
            hint = DIM(f"  {n} de {total} comandos · ↑↓ navegar · Enter ejecutar · Esc limpiar")
        out.append(_row(hint))

    else:
        # ── Modo reposo: 2 secciones contextuales ────────────────────────────
        now_cmds = _now_cmds(ctx)
        now_set  = {c for c, _ in now_cmds}
        sys_cmds = [(c, d) for c, d in _SYSTEM if c not in now_set]
        all_vis  = now_cmds + sys_cmds
        total    = len(_registry())

        out.append(_sep_label("AHORA"))
        for i, (cmd, desc) in enumerate(now_cmds):
            out.append(_cmd_row(i, cmd, desc, i == sel, cmd == rec))

        out.append(_sep_label("SISTEMA"))
        for j, (cmd, desc) in enumerate(sys_cmds):
            gi = len(now_cmds) + j
            out.append(_cmd_row(gi, cmd, desc, gi == sel, False))

        out.append(f"  {CYAN('├' + '─' * _W + '┤')}")
        out.append(_row(f"  {CYAN('❯')} {BOLD('█')}"))
        out.append(_row(DIM("  ↑↓ navegar · número+Enter · escribe para filtrar (43 comandos) · Tab completar")))
        out.append(_row(DIM(f"  Mostrando {len(all_vis)} de {total} · bago help para ver todos")))

    out.append(f"  {CYAN('└' + '─' * _W + '┘')}")
    return out


# ─── Draw ─────────────────────────────────────────────────────────────────────

def _draw(lines: list[str], prev: int) -> int:
    if prev:
        sys.stdout.write(f"\033[{prev}A\033[J")
    for line in lines:
        sys.stdout.write(line + "\n")
    sys.stdout.flush()
    return len(lines)


# ─── Hints post-ejecución ─────────────────────────────────────────────────────

def _hint(cmd: str) -> None:
    """Muestra una línea de orientación tras ejecutar un comando."""
    _map = {
        "next":      f"Tarea iniciada ✅  Implementa y vuelve:  {GREEN('bago done')}",
        "done":      f"Ciclo completado ✅  Para el siguiente:   {GREEN('bago next')}",
        "health":    f"Salud revisada  →  detalle: {GREEN('bago stability')}  o  {GREEN('bago audit')}",
        "ideas":     f"Ideas revisadas  →  para empezar ciclo:  {GREEN('bago next')}",
        "validate":  f"Pack verificado  →  si hay KOs: {GREEN('bago doctor')}",
        "stability": f"Revisado  →  detalle: {GREEN('bago health')}  o  {GREEN('bago audit')}",
    }
    base = cmd.split()[0]
    msg  = _map.get(cmd) or _map.get(base)
    if msg:
        print(f"  {DIM('→')} {msg}\n")


# ─── Ejecución ────────────────────────────────────────────────────────────────

def _run(cmd: str) -> None:
    parts = cmd.strip().split()
    if parts:
        subprocess.run([sys.executable, str(BAGO_BIN)] + parts)


# ─── Shell loop ───────────────────────────────────────────────────────────────

def _visible_cmds(buf: str, ctx: dict) -> list[tuple[str, str]]:
    if buf:
        return _filter(buf)
    now_c   = _now_cmds(ctx)
    now_set = {c for c, _ in now_c}
    sys_c   = [(c, d) for c, d in _SYSTEM if c not in now_set]
    return now_c + sys_c


def _shell() -> int:
    buf       = []
    sel       = 0
    prev_rows = 0

    while True:
        ctx   = _ctx()
        cmds  = _visible_cmds("".join(buf), ctx)
        sel   = min(sel, max(0, len(cmds) - 1))

        prev_rows = _draw(_render("".join(buf), sel, ctx), prev_rows)
        key = _getch()

        if key == "\x1b[A":                    # ↑
            sel = max(0, sel - 1)

        elif key == "\x1b[B":                  # ↓
            sel = min(len(cmds) - 1, sel + 1)

        elif key == "\x1b":                    # ESC — limpiar buffer
            buf = []
            sel = 0

        elif key == "\t":                      # Tab — completar
            if cmds:
                buf = list(cmds[sel][0])
                sel = 0

        elif key.isdigit() and "1" <= key <= "9" and not buf:
            idx = int(key) - 1               # Número — mover selección
            if 0 <= idx < len(cmds):
                sel = idx

        elif key in ("\r", "\n"):              # Enter — ejecutar
            cmd = cmds[sel][0] if cmds else "".join(buf).strip()
            if not cmd:
                continue
            sys.stdout.write(f"\033[{prev_rows}A\033[J")
            sys.stdout.flush()
            prev_rows = 0
            print(f"\n  {CYAN('❯')} {BOLD(GREEN('bago ' + cmd))}\n")
            _run(cmd)
            _hint(cmd)
            buf = []
            sel = 0
            print()

        elif key == "\x7f":                    # Backspace
            if buf:
                buf.pop()
            sel = 0

        elif key in ("\x03", "\x04") or (key.lower() == "q" and not buf):
            sys.stdout.write(f"\033[{prev_rows}A\033[J")
            sys.stdout.flush()
            print(f"  {DIM('Saliendo de BAGO Shell.')}\n")
            return 0

        elif key.isprintable() and len(key) == 1:
            buf.append(key)
            sel = 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    if not sys.stdin.isatty():
        # Sin TTY: lista plana de todos los comandos del registry
        all_c = _registry()
        print()
        for i, (cmd, desc) in enumerate(all_c):
            d = desc[:58] + "…" if len(desc) > 58 else desc
            print(f"  {i + 1:2d}  bago {cmd:<22}  {d}")
        print(f"\n  Total: {len(all_c)} comandos · bago help para más info\n")
        return 0

    print()
    print(f"  {CYAN(BOLD('BAGO Shell'))} — "
          f"{DIM('escribe, usa flechas ↑↓, o pulsa un número · q para salir')}")
    print()
    return _shell()


if __name__ == "__main__":
    sys.exit(main())
