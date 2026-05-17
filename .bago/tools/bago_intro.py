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

# ── Medallón pixel art (avispa azul en círculo teal) ─────────────────────────
# Cada carácter = 1 unidad de píxel → se renderiza como 2 espacios coloreados
#   '.' fuera del círculo  (terminal bg transparente)
#   'O' borde del círculo  (verde oscuro / teal)
#   ' ' interior blanco    (gris muy claro)
#   'W' cuerpo avispa      (azul del pixel art)
_MED = [
    "...OOOOOOOOOOOOOOOOOO...",   # arco superior
    "..OO                OO..",
    ".O    W          W    O.",   # antenas
    ".O      W      W      O.",
    ".O       WWWWWWW       O.",  # cabeza
    ".O      WWWWWWWWW      O.",  # tórax
    ".O   WWWWWWWWWWWWWWW   O.",  # alas arranque
    "OO  WWWWWWWWWWWWWWWWW  OO",  # alas máximo vuelo
    ".O   WWWWWWWWWWWWWWW   O.",  # alas inferiores
    ".O      WWWWWWWWW      O.",  # tórax inferior
    ".O        WWWWW        O.",  # abdomen superior
    ".O         WWW         O.",  # abdomen medio
    ".O          W          O.",  # aguijón superior
    "..OO                OO..",
    "...OOOOOOOOOOOOOOOOOO...",   # arco inferior
]
_MED_PX_W = len(_MED[0])    # píxeles de ancho (24)
MED_W     = _MED_PX_W * 2   # columnas de terminal (48)
MED_H     = len(_MED)        # filas (15)

# WASP_W / WASP_H: aliases para compatibilidad
WASP_W = MED_W
WASP_H = MED_H

# Colores del medallón (truecolor + fallback 256)
if USE_TC:
    _C_BORDER = "\033[48;2;0;85;75m"       # teal oscuro del borde
    _C_BG     = "\033[48;2;230;232;230m"   # blanco interior
    _C_WASP   = "\033[48;2;40;115;195m"    # azul del pixel art
else:
    _C_BORDER = "\033[42m"   # verde (256)
    _C_BG     = "\033[107m"  # blanco brillante (256)
    _C_WASP   = "\033[44m"   # azul (256)
_C_RST = "\033[0m"

def _render_med_row(row_str: str) -> str:
    """Convierte una fila del mapa pixel en caracteres de terminal coloreados."""
    buf = []
    for ch in row_str:
        if   ch == '.': buf.append("  ")
        elif ch == 'O': buf.append(f"{_C_BORDER}  {_C_RST}")
        elif ch == ' ': buf.append(f"{_C_BG}  {_C_RST}")
        elif ch == 'W': buf.append(f"{_C_WASP}  {_C_RST}")
        else:           buf.append("  ")
    return "".join(buf)

def _draw_medallion(start_row: int, col: int) -> None:
    """Renderiza el medallón completo en su posición."""
    out = sys.stdout.write
    for r, row_str in enumerate(_MED):
        out(_goto(start_row + r, col) + _render_med_row(row_str))
    sys.stdout.flush()

# ── Avispa volando (animación de vuelo — una línea) ───────────────────────────
BEE_FRAMES = [r"╱\◉/╲", r"──◉──", r"╲/◉\╱", r"──◉──"]
BEE_TRAIL  = ["·", "·", " "]

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
    """Dibuja solo el logo BAGO (la avispa se gestiona por separado)."""
    out = sys.stdout.write
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

    # Layout vertical: medallón pixel art centrado arriba → logo BAGO centrado abajo
    # Si el terminal es pequeño (<35 filas), compactar medallón
    use_full_med = rows >= 35
    med_h   = MED_H if use_full_med else 7
    total_h = med_h + 1 + LOGO_H + 3 + len(BOOT_MSGS) + 3
    start_row = max(2, (rows - total_h) // 2)

    wasp_row  = start_row
    logo_row  = start_row + med_h + 1
    logo_col  = max(1, (cols - LOGO_W) // 2 + 1)
    tag_row   = logo_row + LOGO_H + 1
    msg_row   = tag_row + 2
    act_row   = msg_row + len(BOOT_MSGS) + 1

    out = sys.stdout.write
    out(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()

    # ── 1. REVEAL: medallón pixel art línea a línea ───────────────────────────
    if use_full_med:
        med_display_w = MED_W
        wasp_col = max(1, (cols - med_display_w) // 2 + 1)
        for i, row_str in enumerate(_MED):
            # Línea de scan antes del reveal
            if USE_COLOR and not fast:
                out(_goto(wasp_row + i, wasp_col) +
                    f"\033[1;36m{'──' * _MED_PX_W}\033[0m")
                sys.stdout.flush()
                time.sleep(0.012)
            out(_goto(wasp_row + i, wasp_col) + _render_med_row(row_str))
            sys.stdout.flush()
            time.sleep(0.035 if not fast else 0.001)
    else:
        # Fallback compacto para terminales pequeños
        _WASP_COMPACT = [
            r"   ╲  ╱   ",
            r"  ─(◉)─   ",
            r" ╱══════╲  ",
            r" ╪═══════╪ ",
            r" ╲══════╱  ",
            r"   │██│    ",
            r"   └─▼─┘   ",
        ]
        compact_w = max(len(l) for l in _WASP_COMPACT)
        wasp_col = max(1, (cols - compact_w) // 2 + 1)
        for i, line in enumerate(_WASP_COMPACT):
            if USE_COLOR:
                r2 = int(26 + 10 * i / 7)
                g2 = int(106 + 30 * i / 7)
                b2 = int(191 + 40 * i / 7)
                rendered = f"\033[38;2;{r2};{g2};{b2}m{line}\033[0m"
            else:
                rendered = line
            out(_goto(wasp_row + i, wasp_col) + rendered)
            sys.stdout.flush()
            time.sleep(0.04 if not fast else 0.002)

    # ── 2. REVEAL: logo BAGO línea a línea ───────────────────────────────────
    for i, line in enumerate(LOGO):
        rendered = _logo_line(line, i, intensity=1.0)
        if USE_COLOR:
            out(_goto(logo_row + i, logo_col) +
                f"\033[1;96m{'─' * LOGO_W}\033[0m")
            sys.stdout.flush()
            time.sleep(0.018 if not fast else 0.001)
        out(_goto(logo_row + i, logo_col) + rendered)
        sys.stdout.flush()
        time.sleep(0.04 if not fast else 0.002)

    # ── 3. PULSO (respiración de color en logo BAGO) ──────────────────────────
    if not fast:
        steps = 8
        for _pulse in range(2):
            for step in range(steps):
                _draw_logo(logo_row, logo_col, intensity=1.0 - 0.5 * step / steps)
                time.sleep(0.022)
            for step in range(steps):
                _draw_logo(logo_row, logo_col, intensity=0.5 + 0.5 * step / steps)
                time.sleep(0.022)
        _draw_logo(logo_row, logo_col, intensity=1.0)

    # ── 4. TAGLINE ───────────────────────────────────────────────────────────
    tag_col = max(1, (cols - len(TAGLINE)) // 2 + 1)
    if USE_COLOR:
        tag_rendered = f"\033[2;36m{TAGLINE}\033[0m"
    else:
        tag_rendered = TAGLINE
    out(_goto(tag_row, tag_col) + tag_rendered)
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

    # ── 7. ◉ ◆ BAGO — ACTIVO ──────────────────────────────────────────────────
    active_msg = "◉  ◆  BAGO — ACTIVO"
    act_col    = max(1, (cols - len(active_msg)) // 2 + 1)
    if USE_COLOR:
        active_rendered = f"\033[1;32m{active_msg}\033[0m"
    else:
        active_rendered = active_msg
    out(_goto(act_row, act_col) + active_rendered)
    sys.stdout.flush()
    time.sleep(0.6 if not fast else 0.05)
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
