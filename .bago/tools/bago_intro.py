#!/usr/bin/env python3
"""
bago_intro.py — Animación de inicio estilo Copilot para BAGO

Secuencia:
  1. Limpia pantalla
  2. Logo BAGO aparece línea a línea (efecto scan descendente)
  3. Pulso de color (respiración 2 ciclos)
  4. Tagline aparece debajo
  5. Mensajes de arranque con spinner → ✓
  6. "◆ BAGO — ACTIVO" centrado en verde
  7. Pausa breve → limpia → devuelve control

Uso directo:
  python3 .bago/tools/bago_intro.py
  python3 .bago/tools/bago_intro.py --fast   (sin pulso, para tests)
  python3 .bago/tools/bago_intro.py --skip   (skip inmediato, solo imprime '◆ BAGO')
"""
import os, sys, time
from pathlib import Path

# ── Windows VT ───────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        _k32 = ctypes.windll.kernel32
        _h   = _k32.GetStdHandle(-11)
        _m   = ctypes.c_ulong(0)
        if _k32.GetConsoleMode(_h, ctypes.byref(_m)):
            _k32.SetConsoleMode(_h, _m.value | 0x0004)
    except Exception:
        pass

# ── Soporte color ─────────────────────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty()
USE_TC    = USE_COLOR and os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")

def _esc(code: str) -> str:   return f"\033[{code}m" if USE_COLOR else ""
def _rgb(r: int, g: int, b: int) -> str:
    if not USE_COLOR: return ""
    if not USE_TC:    return "\033[1;36m"
    return f"\033[38;2;{r};{g};{b}m"

RST         = _esc("0")
DIM_CODE    = _esc("2")
BOLD_CODE   = _esc("1")
GREEN       = lambda t: f"\033[1;32m{t}\033[0m" if USE_COLOR else t
CYAN_B      = lambda t: f"\033[1;36m{t}\033[0m" if USE_COLOR else t
DIM_S       = lambda t: f"\033[2m{t}\033[0m"    if USE_COLOR else t

HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR       = "\033[2J\033[H"
CLEAR_LINE  = "\033[2K\r"

def _goto(row: int, col: int = 1) -> str:
    return f"\033[{row};{col}H"

def _term_size() -> tuple[int, int]:
    import shutil
    s = shutil.get_terminal_size((80, 24))
    return s.columns, s.lines

# ── Logo BAGO (block letters) ─────────────────────────────────────────────────
LOGO = [
    "██████╗  █████╗  ██████╗  ██████╗ ",
    "██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗",
    "██████╔╝███████║██║  ███╗██║   ██║",
    "██╔══██╗██╔══██║██║   ██║██║   ██║",
    "██████╔╝██║  ██║╚██████╔╝╚██████╔╝",
    "╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ",
]
LOGO_W  = max(len(l) for l in LOGO)
LOGO_H  = len(LOGO)
TAGLINE = "Balanceado · Adaptativo · Generativo · Organizativo"

# ── Spinner ───────────────────────────────────────────────────────────────────
_SPIN     = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
_SPIN_PLN = ["|", "/", "-", "\\"]

BOOT_MSGS = [
    "Escaneando proveedores...",
    "Cargando model field matrix...",
    "Verificando safeguards...",
    "Activando canon Shepard...",
    "Campo magnético estabilizado.",
]

# ── Render helpers ────────────────────────────────────────────────────────────
def _logo_line(line: str, y: int, intensity: float = 1.0) -> str:
    """Renderiza una línea del logo con gradiente cyan-azul e intensidad variable."""
    if not USE_COLOR:
        return line
    out = []
    w = max(1, LOGO_W)
    h = max(1, LOGO_H)
    for x, ch in enumerate(line):
        if ch == " ":
            out.append(" ")
        else:
            r = int(max(0, min(255, (30  + 20  * x / w) * intensity)))
            g = int(max(0, min(255, (170 + 75  * y / h) * intensity)))
            b = int(max(0, min(255, (210 + 45  * x / w) * intensity)))
            out.append(f"{_rgb(r,g,b)}{ch}{RST}")
    return "".join(out)

def _draw_logo(start_row: int, logo_col: int, intensity: float = 1.0):
    """Dibuja el logo completo en la posición indicada."""
    w = sys.stdout.write
    for i, line in enumerate(LOGO):
        rendered = _logo_line(line, i, intensity)
        w(_goto(start_row + i, logo_col) + CLEAR_LINE + " " * (logo_col - 1) + rendered)
    sys.stdout.flush()

# ── Animación principal ───────────────────────────────────────────────────────
def play(fast: bool = False, skip: bool = False) -> None:
    """
    Reproduce la animación de inicio BAGO.
    fast=True  → sin pulso (para tests)
    skip=True  → sin animación (entornos no interactivos)
    """
    if skip or not sys.stdout.isatty():
        return
    try:
        _animate(fast=fast)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()


def _animate(fast: bool = False) -> None:
    cols, rows = _term_size()

    # Centrar el logo + contenido verticalmente
    total_h   = LOGO_H + 2 + len(BOOT_MSGS) + 3  # logo + tagline gap + msgs + activo
    start_row = max(2, (rows - total_h) // 2)
    logo_col  = max(1, (cols - LOGO_W) // 2 + 1)
    tag_row   = start_row + LOGO_H + 1
    msg_row   = tag_row + 2
    act_row   = msg_row + len(BOOT_MSGS) + 1

    w = sys.stdout.write
    w(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()

    # ── 1. REVEAL: logo aparece línea a línea (efecto scan descendente) ────────
    for i, line in enumerate(LOGO):
        rendered = _logo_line(line, i, intensity=1.0)
        # Efecto scan: línea nueva en CYAN brillante, luego se queda
        if USE_COLOR:
            scan = f"\033[1;96m{'─' * LOGO_W}\033[0m"
            w(_goto(start_row + i, logo_col) + scan)
            sys.stdout.flush()
            time.sleep(0.018)
        w(_goto(start_row + i, logo_col) + rendered)
        sys.stdout.flush()
        time.sleep(0.04)

    time.sleep(0.1)

    # ── 2. PULSO (respiración de color) ────────────────────────────────────────
    if not fast:
        steps = 10
        for _pulse in range(2):
            for step in range(steps):              # fade out
                _draw_logo(start_row, logo_col, intensity=1.0 - 0.55 * step / steps)
                time.sleep(0.025)
            for step in range(steps):              # fade in
                _draw_logo(start_row, logo_col, intensity=0.45 + 0.55 * step / steps)
                time.sleep(0.025)
        _draw_logo(start_row, logo_col, intensity=1.0)

    # ── 3. TAGLINE ─────────────────────────────────────────────────────────────
    tag_col = max(1, (cols - len(TAGLINE)) // 2 + 1)
    if USE_COLOR:
        tag_rendered = f"\033[2;36m{TAGLINE}\033[0m"
    else:
        tag_rendered = TAGLINE
    w(_goto(tag_row, tag_col) + tag_rendered)
    sys.stdout.flush()
    time.sleep(0.12)

    # ── 4. BOOT MESSAGES con spinner ───────────────────────────────────────────
    spinner   = _SPIN if USE_COLOR else _SPIN_PLN
    spin_idx  = 0
    msg_col   = max(1, (cols - len(max(BOOT_MSGS, key=len)) - 6) // 2 + 1)

    for idx, msg in enumerate(BOOT_MSGS):
        row   = msg_row + idx
        t0    = time.monotonic()
        delay = 0.45 if not fast else 0.05
        while time.monotonic() - t0 < delay:
            frame = spinner[spin_idx % len(spinner)]
            if USE_COLOR:
                line = f"\033[1;36m{frame}\033[0m  \033[2m{msg}\033[0m"
            else:
                line = f"{frame}  {msg}"
            w(_goto(row, msg_col) + CLEAR_LINE + " " * (msg_col - 1) + line)
            sys.stdout.flush()
            time.sleep(0.05)
            spin_idx += 1
        # ✓ completado
        done = f"\033[1;32m✓\033[0m  \033[2m{msg}\033[0m" if USE_COLOR else f"*  {msg}"
        w(_goto(row, msg_col) + CLEAR_LINE + " " * (msg_col - 1) + done)
        sys.stdout.flush()

    # ── 5. ◆ BAGO — ACTIVO ─────────────────────────────────────────────────────
    active_msg = "◆  BAGO — ACTIVO"
    act_col    = max(1, (cols - len(active_msg)) // 2 + 1)
    active_rendered = GREEN(active_msg) if USE_COLOR else active_msg
    w(_goto(act_row, act_col) + active_rendered)
    sys.stdout.flush()
    time.sleep(0.7 if not fast else 0.1)

    # ── 6. Limpiar → devuelve control a bago_chat ──────────────────────────────
    w(CLEAR)
    sys.stdout.flush()


# ── Mini banner (para uso en otros módulos) ───────────────────────────────────
def mini_badge() -> str:
    """Retorna el texto del badge pequeño para la barra de estado."""
    return "◆ BAGO"


# ── Ejecución directa ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    fast = "--fast" in sys.argv
    skip = "--skip" in sys.argv
    if skip:
        print(mini_badge())
    else:
        play(fast=fast)
        print("Animación completada.")
