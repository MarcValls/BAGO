#!/usr/bin/env python3
"""
bago_intro.py — Animación de inicio estilo Copilot para BAGO

Secuencia:
  1. Limpia pantalla
  2. Logo BAGO aparece línea a línea (efecto scan descendente)
  3. Avispa vuela de izquierda a derecha, aterriza junto al logo
  4. Pulso de color (respiración 2 ciclos)
  5. Tagline aparece debajo con la avispa
  6. Mensajes de arranque con spinner → ✓
  7. ">≡ᗑ≡< ◆ BAGO — ACTIVO" centrado en verde
  8. Reset terminal → devuelve control

Uso directo:
  python3 .bago/tools/bago_intro.py
  python3 .bago/tools/bago_intro.py --fast   (sin pulso/vuelo, para tests)
  python3 .bago/tools/bago_intro.py --skip   (skip inmediato)
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
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
TERM_RESET  = "\033[0m\033[?25h"   # reset attrs + show cursor
CLEAR       = "\033[2J\033[H"
CLEAR_LINE  = "\033[2K\r"

def _goto(row: int, col: int = 1) -> str:
    return f"\033[{row};{col}H"

def _term_size() -> tuple:
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

# ── Logo de la avispa (pixel art → ASCII) ────────────────────────────────────
# Basado en el emblema: avispa asiática azul sobre círculo blanco
# Vista cenital: antenas, cabeza, alas extendidas, abdomen segmentado, aguijón
WASP_ART = [
    r"   ╲  ╱    ",   # antenas (divergen hacia arriba)
    r"  ─(◉)─    ",   # cabeza + raíz de antenas
    r" ╱══════╲  ",   # tórax + arranque de alas
    r"╪═══════╪  ",   # alas extendidas al máximo
    r" ╲══════╱  ",   # tórax inferior
    r"   │██│    ",   # abdomen
    r"   └─▼─┘   ",   # aguijón
]
WASP_W = max(len(l) for l in WASP_ART)
WASP_H = len(WASP_ART)   # 7 líneas — se centra verticalmente junto al logo

# ── Avispa volando (animación de vuelo — una línea) ───────────────────────────
#   ◉ = cuerpo/tórax  ╱╲ = alas en distintas posiciones
BEE_FRAMES = [
    r"╱\◉/╲",   # alas arriba
    r"──◉──",   # alas horizontal
    r"╲/◉\╱",   # alas abajo
    r"──◉──",   # alas horizontal
]
BEE_TRAIL = ["·", "·", " "]   # estela de vuelo

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

def _wasp_line(line: str, y: int, intensity: float = 1.0) -> str:
    """Renderiza una línea del logo de la avispa en azul (como el pixel art)."""
    if not USE_COLOR:
        return line
    # Azul del pixel art: R=26 G=106 B=191, con variación sutil por fila
    out = []
    for ch in line:
        if ch == " ":
            out.append(" ")
        else:
            r = int(max(0, min(255, (26  + 10 * y / max(1, WASP_H)) * intensity)))
            g = int(max(0, min(255, (106 + 30 * y / max(1, WASP_H)) * intensity)))
            b = int(max(0, min(255, (191 + 40 * y / max(1, WASP_H)) * intensity)))
            out.append(f"{_rgb(r,g,b)}{ch}{RST}")
    return "".join(out)

def _draw_logo(start_row: int, logo_col: int, intensity: float = 1.0):
    """Dibuja el logo BAGO con la avispa a su izquierda."""
    out = sys.stdout.write
    wasp_col = max(1, logo_col - WASP_W - 2)
    # Offset vertical para centrar la avispa (7 líneas) frente al logo (6 líneas)
    wasp_offset = max(0, (LOGO_H - WASP_H) // 2)
    for i, line in enumerate(WASP_ART):
        rendered = _wasp_line(line, i, intensity)
        out(_goto(start_row + wasp_offset + i, wasp_col) + rendered)
    for i, line in enumerate(LOGO):
        rendered = _logo_line(line, i, intensity)
        out(_goto(start_row + i, logo_col) + rendered)
    sys.stdout.flush()

def _draw_bee(row: int, col: int, frame: int, trail_len: int = 4, cols: int = 80):
    """Dibuja la abeja con su estela en la posición dada."""
    out = sys.stdout.write
    bee = BEE_FRAMES[frame % len(BEE_FRAMES)]
    # Estela de puntitos a la izquierda
    trail = ""
    if USE_COLOR:
        for t in range(trail_len, 0, -1):
            tc = col - t - 1
            if 1 <= tc <= cols:
                dim = t / trail_len
                trail_char = "·" if t > 1 else " "
                trail += _goto(row, tc) + f"\033[{int(2 + dim)}m{trail_char}\033[0m"
    if USE_COLOR:
        bee_colored = f"\033[1;33m{bee}\033[0m"
    else:
        bee_colored = bee
    out(trail + _goto(row, max(1, col)) + bee_colored)
    sys.stdout.flush()

def _clear_bee_row(row: int, cols: int):
    """Borra la fila de la abeja."""
    sys.stdout.write(_goto(row, 1) + " " * cols)
    sys.stdout.flush()

# ── Animación principal ───────────────────────────────────────────────────────
def play(fast: bool = False, skip: bool = False) -> None:
    if skip or not sys.stdout.isatty():
        return
    try:
        _animate(fast=fast)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        # Siempre restaurar terminal a estado limpio
        sys.stdout.write(TERM_RESET + CLEAR)
        sys.stdout.flush()


def _animate(fast: bool = False) -> None:
    cols, rows = _term_size()

    # Calcular posiciones centradas
    # Bloque visual: avispa+logo en la misma franja (max de ambos en altura)
    block_w   = WASP_W + 2 + LOGO_W        # avispa + gap + logo BAGO
    block_h   = max(LOGO_H, WASP_H)
    total_h   = block_h + 3 + len(BOOT_MSGS) + 3
    start_row = max(3, (rows - total_h) // 2)
    # Logo BAGO centrado respecto al bloque completo
    logo_col  = max(WASP_W + 3, (cols - block_w) // 2 + WASP_W + 3)
    bee_row   = start_row - 2           # fila de vuelo: encima del logo
    tag_row   = start_row + block_h + 1
    msg_row   = tag_row + 2
    act_row   = msg_row + len(BOOT_MSGS) + 1

    out = sys.stdout.write
    out(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()

    # ── 1. REVEAL: logo BAGO + avispa aparecen línea a línea ────────────────
    wasp_col   = max(1, logo_col - WASP_W - 2)
    wasp_offset = max(0, (LOGO_H - WASP_H) // 2)
    reveal_lines = max(LOGO_H, WASP_H)
    for i in range(reveal_lines):
        # Avispa (azul)
        if i < WASP_H:
            wline = _wasp_line(WASP_ART[i], i, intensity=1.0)
            if USE_COLOR:
                out(_goto(start_row + wasp_offset + i, wasp_col) +
                    f"\033[1;34m{'─' * WASP_W}\033[0m")
                sys.stdout.flush()
                time.sleep(0.012 if not fast else 0.0)
            out(_goto(start_row + wasp_offset + i, wasp_col) + wline)
        # Logo BAGO
        if i < LOGO_H:
            rline = _logo_line(LOGO[i], i, intensity=1.0)
            if USE_COLOR:
                out(_goto(start_row + i, logo_col) +
                    f"\033[1;96m{'─' * LOGO_W}\033[0m")
                sys.stdout.flush()
                time.sleep(0.018 if not fast else 0.0)
            out(_goto(start_row + i, logo_col) + rline)
        sys.stdout.flush()
        time.sleep(0.04 if not fast else 0.002)

    # ── 2. AVISPA VOLANDO de izquierda a derecha ─────────────────────────────
    if not fast:
        # La avispa entra por la izquierda y vuela hasta quedar a la izquierda del logo
        bee_target_col = logo_col - 3
        fly_steps = max(10, bee_target_col)
        step_size = max(1, bee_target_col // fly_steps)
        frame = 0
        for col in range(1, bee_target_col + 1, step_size):
            _draw_bee(bee_row, col, frame, trail_len=min(col, 5), cols=cols)
            frame += 1
            time.sleep(0.025)
        # Llega y da un pequeño rebote
        for bounce in [bee_target_col + 1, bee_target_col - 1, bee_target_col]:
            _draw_bee(bee_row, bounce, frame, trail_len=3, cols=cols)
            frame += 1
            time.sleep(0.05)
        # Hovering (bate las alas 3 veces)
        for flap in range(6):
            _draw_bee(bee_row, bee_target_col, flap, trail_len=0, cols=cols)
            time.sleep(0.08)

    # ── 3. PULSO (respiración de color) ──────────────────────────────────────
    if not fast:
        steps = 8
        for _pulse in range(2):
            for step in range(steps):
                _draw_logo(start_row, logo_col, intensity=1.0 - 0.5 * step / steps)
                time.sleep(0.022)
            for step in range(steps):
                _draw_logo(start_row, logo_col, intensity=0.5 + 0.5 * step / steps)
                time.sleep(0.022)
        _draw_logo(start_row, logo_col, intensity=1.0)

    # ── 4. TAGLINE ───────────────────────────────────────────────────────────
    tag_col = max(1, (cols - len(TAGLINE)) // 2 + 1)
    if USE_COLOR:
        tag_rendered = f"\033[2;36m{TAGLINE}\033[0m"
    else:
        tag_rendered = TAGLINE
    out(_goto(tag_row, tag_col) + tag_rendered)
    # Limpiar la fila de vuelo de la avispa
    if not fast:
        _clear_bee_row(bee_row, cols)
    sys.stdout.flush()
    time.sleep(0.12 if not fast else 0.01)

    # ── 5. BOOT MESSAGES con spinner ─────────────────────────────────────────
    spinner  = _SPIN if USE_COLOR else _SPIN_PLN
    spin_idx = 0
    msg_col  = max(1, (cols - len(max(BOOT_MSGS, key=len)) - 6) // 2 + 1)

    for idx, msg in enumerate(BOOT_MSGS):
        row   = msg_row + idx
        t0    = time.monotonic()
        delay = 0.38 if not fast else 0.04
        while time.monotonic() - t0 < delay:
            frame = spinner[spin_idx % len(spinner)]
            if USE_COLOR:
                line = f"\033[1;36m{frame}\033[0m  \033[2m{msg}\033[0m"
            else:
                line = f"{frame}  {msg}"
            out(_goto(row, msg_col) + CLEAR_LINE + " " * (msg_col - 1) + line)
            sys.stdout.flush()
            time.sleep(0.05)
            spin_idx += 1
        done = (f"\033[1;32m✓\033[0m  \033[2m{msg}\033[0m" if USE_COLOR
                else f"*  {msg}")
        out(_goto(row, msg_col) + CLEAR_LINE + " " * (msg_col - 1) + done)
        sys.stdout.flush()

    # ── 6. ◉ ◆ BAGO — ACTIVO ──────────────────────────────────────────────────
    active_msg = "◉  ◆  BAGO — ACTIVO"
    act_col    = max(1, (cols - len(active_msg)) // 2 + 1)
    if USE_COLOR:
        active_rendered = f"\033[1;32m{active_msg}\033[0m"
    else:
        active_rendered = active_msg
    out(_goto(act_row, act_col) + active_rendered)
    sys.stdout.flush()
    time.sleep(0.6 if not fast else 0.05)
    # Pequeño parpadeo final
    if not fast:
        for _ in range(2):
            out(_goto(act_row, act_col) + " " * len(active_msg))
            sys.stdout.flush(); time.sleep(0.08)
            out(_goto(act_row, act_col) + active_rendered)
            sys.stdout.flush(); time.sleep(0.08)

    time.sleep(0.3 if not fast else 0.01)
    # El finally en play() limpia pantalla y restaura terminal


# ── Badge avispa (pixel art) para barra de estado ────────────────────────────
# Frames minimalistas que evocan la avispa del logo: ◉ = cuerpo, ╱╲ = alas
_BEE_BAR_FRAMES = ["╱◉╲ ", "─◉─ ", "╲◉╱ ", "─◉─ "]

def bee_badge(tick: int = 0) -> str:
    """Retorna el badge con la avispa para la barra de estado. tick=int(time*2)%4."""
    wasp = _BEE_BAR_FRAMES[tick % len(_BEE_BAR_FRAMES)]
    return f"{wasp}◆ BAGO"


# ── Ejecución directa ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    fast = "--fast" in sys.argv
    skip = "--skip" in sys.argv
    if skip:
        print(bee_badge())
    else:
        play(fast=fast)
        if not fast:
            print("Animación completada.")
