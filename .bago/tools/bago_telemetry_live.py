#!/usr/bin/env python3
"""bago_telemetry_live.py — Visor dinámico de telemetría BAGO.

TUI basado en curses. Sin dependencias externas.

Uso:
    python3 bago_telemetry_live.py          # refresco cada 2s
    python3 bago_telemetry_live.py --rate 5 # refresco cada 5s

Controles:
    q / ESC     → salir
    d           → vista Dashboard (por defecto)
    s           → vista Stats por comando
    e           → vista Errores
    r           → refrescar ahora
    ↑ / ↓       → scroll en lista de eventos
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import curses
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Ruta de datos ──────────────────────────────────────────────────────────────
_xdg = os.environ.get("XDG_DATA_HOME")
TELEMETRY_DIR: Path = (
    (Path(_xdg) / "bago" / "telemetry") if _xdg
    else (Path.home() / ".bago" / "telemetry")
)
EVENTS_FILE = TELEMETRY_DIR / "events.jsonl"

# ── Colores (índices de par) ───────────────────────────────────────────────────
C_HEADER   = 1   # fondo azul oscuro
C_TITLE    = 2   # cyan brillante
C_OK       = 3   # verde
C_FAIL     = 4   # rojo
C_WARN     = 5   # amarillo
C_DIM      = 6   # gris / normal atenuado
C_BAR      = 7   # azul para barras
C_SEL      = 8   # fila seleccionada / activa
C_EVENT    = 9   # blanco normal para eventos
C_METRIC   = 10  # magenta para métricas
C_BORDER   = 11  # borde gris


def _init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_HEADER,  curses.COLOR_WHITE,   curses.COLOR_BLUE)
    curses.init_pair(C_TITLE,   curses.COLOR_CYAN,    -1)
    curses.init_pair(C_OK,      curses.COLOR_GREEN,   -1)
    curses.init_pair(C_FAIL,    curses.COLOR_RED,     -1)
    curses.init_pair(C_WARN,    curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_DIM,     curses.COLOR_WHITE,   -1)
    curses.init_pair(C_BAR,     curses.COLOR_BLUE,    -1)
    curses.init_pair(C_SEL,     curses.COLOR_BLACK,   curses.COLOR_CYAN)
    curses.init_pair(C_EVENT,   curses.COLOR_WHITE,   -1)
    curses.init_pair(C_METRIC,  curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_BORDER,  curses.COLOR_WHITE,   -1)


# ── Helpers de dibujo ──────────────────────────────────────────────────────────

def _safe_addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """addstr que nunca lanza excepción por coordenadas fuera de límite."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    available = w - x - 1
    if available <= 0:
        return
    try:
        win.addstr(y, x, text[:available], attr)
    except curses.error:
        pass


def _hline(win, y: int, x: int, length: int, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if y < 0 or y >= h:
        return
    actual = min(length, w - x - 1)
    if actual <= 0:
        return
    try:
        win.hline(y, x, curses.ACS_HLINE, actual, attr)
    except curses.error:
        pass


def _vline(win, y: int, x: int, length: int, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if x < 0 or x >= w:
        return
    actual = min(length, h - y - 1)
    if actual <= 0:
        return
    try:
        win.vline(y, x, curses.ACS_VLINE, actual, attr)
    except curses.error:
        pass


# ── Carga de datos ─────────────────────────────────────────────────────────────

def _load_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events: list[dict] = []
    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return events


def _compute_stats(events: list[dict]) -> dict:
    """Precalcula métricas para evitar repetición en los draws."""
    cmds    = [e for e in events if e.get("type") == "command"]
    errors  = [e for e in events if e.get("type") == "exception"]
    custom  = [e for e in events if e.get("type") == "event"]
    metrics = [e for e in events if e.get("type") == "metric"]

    ok   = sum(1 for e in cmds if e.get("properties", {}).get("success") is True)
    fail = sum(1 for e in cmds if e.get("properties", {}).get("success") is False)

    cmd_counts: Counter = Counter(e.get("name", "?") for e in cmds)
    cmd_durations: dict = defaultdict(list)
    cmd_success: dict   = defaultdict(lambda: {"ok": 0, "fail": 0})
    for e in cmds:
        name = e.get("name", "?")
        dur  = e.get("metrics", {}).get("duration_s")
        if dur is not None:
            cmd_durations[name].append(dur)
        if e.get("properties", {}).get("success") is True:
            cmd_success[name]["ok"] += 1
        elif e.get("properties", {}).get("success") is False:
            cmd_success[name]["fail"] += 1

    oldest = events[0].get("ts", "")[:16].replace("T", " ") if events else "—"
    newest = events[-1].get("ts", "")[:16].replace("T", " ") if events else "—"

    return {
        "total": len(events),
        "cmds": cmds,
        "errors": errors,
        "custom": custom,
        "metrics": metrics,
        "ok": ok,
        "fail": fail,
        "cmd_counts": cmd_counts,
        "cmd_durations": cmd_durations,
        "cmd_success": cmd_success,
        "oldest": oldest,
        "newest": newest,
    }


# ── Vista: Dashboard ───────────────────────────────────────────────────────────

def _draw_dashboard(win, stats: dict, scroll: int) -> None:
    h, w = win.getmaxyx()
    row = 0

    # ── Fila de resumen rápido ──
    total   = stats["total"]
    ok      = stats["ok"]
    fail    = stats["fail"]
    n_err   = len(stats["errors"])
    n_cust  = len(stats["custom"])
    n_met   = len(stats["metrics"])

    summary = (f"  Cmds: {len(stats['cmds'])}  "
               f"✅ {ok}  ❌ {fail}  │  "
               f"Excepc: {n_err}  │  "
               f"Eventos: {n_cust}  │  "
               f"Métricas: {n_met}  │  "
               f"Total: {total}")
    _safe_addstr(win, row, 0, summary[:w-1], curses.color_pair(C_DIM))
    row += 1
    _hline(win, row, 0, w - 1, curses.color_pair(C_BORDER) | curses.A_DIM)
    row += 1

    mid = (w - 2) // 2  # columna divisoria

    # ── Cabeceras de columnas ──
    _safe_addstr(win, row, 2,       "TOP COMANDOS",  curses.color_pair(C_TITLE) | curses.A_BOLD)
    _safe_addstr(win, row, mid + 3, "EVENTOS RECIENTES", curses.color_pair(C_TITLE) | curses.A_BOLD)
    row += 1
    _hline(win, row, 1,       mid - 2, curses.color_pair(C_BORDER) | curses.A_DIM)
    _hline(win, row, mid + 2, w - mid - 3, curses.color_pair(C_BORDER) | curses.A_DIM)
    row += 1

    content_rows = h - row - 2  # espacio disponible para contenido

    # ── Columna izquierda: barras ──
    top_cmds = stats["cmd_counts"].most_common(content_rows)
    bar_max  = top_cmds[0][1] if top_cmds else 1
    bar_width = mid - 14  # espacio para la barra

    for i, (name, count) in enumerate(top_cmds):
        if i >= content_rows:
            break
        r = row + i
        suc  = stats["cmd_success"][name]
        fail_cmd = suc["fail"]
        avg_list = stats["cmd_durations"].get(name, [])
        avg      = sum(avg_list) / len(avg_list) if avg_list else None
        avg_s    = f"{avg:.1f}s" if avg is not None else "  —"

        bar_len = max(1, round(count / bar_max * bar_width))
        bar_col = curses.color_pair(C_FAIL if fail_cmd else C_BAR) | curses.A_BOLD
        name_col = curses.color_pair(C_OK if not fail_cmd else C_WARN)

        _safe_addstr(win, r, 2, f"{name:<14}", name_col)
        _safe_addstr(win, r, 16, "█" * bar_len, bar_col)
        _safe_addstr(win, r, 16 + bar_len + 1, f"{count:>3} {avg_s:>5}",
                     curses.color_pair(C_DIM))

    # ── Divisor vertical ──
    _vline(win, row, mid, content_rows + 1, curses.color_pair(C_BORDER) | curses.A_DIM)

    # ── Columna derecha: eventos recientes ──
    recent = (stats["cmds"] + stats["errors"] + stats["custom"])
    recent.sort(key=lambda e: e.get("ts", ""))
    recent = recent[-(content_rows + scroll):]
    if scroll > 0:
        recent = recent[:-scroll] if scroll < len(recent) else []

    right_w = w - mid - 3
    for i, e in enumerate(recent[-content_rows:]):
        r    = row + i
        ts   = e.get("ts", "?")[11:19]  # HH:MM:SS
        etype = e.get("type", "?")
        name  = e.get("name", "?")
        props = e.get("properties", {})
        metrics = e.get("metrics", {})

        success = props.get("success")
        if etype == "exception":
            icon = "💥"
            col  = curses.color_pair(C_FAIL)
        elif success is True:
            icon = "✓"
            col  = curses.color_pair(C_OK)
        elif success is False:
            icon = "✗"
            col  = curses.color_pair(C_FAIL)
        elif etype == "event":
            icon = "◆"
            col  = curses.color_pair(C_WARN)
        else:
            icon = "·"
            col  = curses.color_pair(C_DIM)

        dur = metrics.get("duration_s")
        dur_str = f" {dur:.2f}s" if dur is not None else ""
        line = f" {icon} {ts} {name:<14}{dur_str}"
        _safe_addstr(win, r, mid + 2, line[:right_w], col)


# ── Vista: Stats tabla ─────────────────────────────────────────────────────────

def _draw_stats(win, stats: dict, scroll: int) -> None:
    h, w = win.getmaxyx()
    row  = 0

    header = f"  {'COMANDO':<18} {'OK':>5} {'FAIL':>5} {'TOTAL':>6} {'AVG(s)':>8} {'MAX(s)':>8}"
    _safe_addstr(win, row, 0, header[:w-1], curses.color_pair(C_TITLE) | curses.A_BOLD)
    row += 1
    _hline(win, row, 0, w - 1, curses.color_pair(C_BORDER) | curses.A_DIM)
    row += 1

    entries = sorted(stats["cmd_counts"].items(), key=lambda x: -x[1])
    visible = entries[scroll: scroll + (h - row - 2)]

    for name, total in visible:
        suc   = stats["cmd_success"][name]
        durs  = stats["cmd_durations"].get(name, [])
        avg   = sum(durs) / len(durs) if durs else None
        mx    = max(durs) if durs else None
        avg_s = f"{avg:.2f}" if avg is not None else "  —"
        mx_s  = f"{mx:.2f}"  if mx  is not None else "  —"

        ok_s  = str(suc["ok"])
        fa_s  = str(suc["fail"])

        ok_col   = curses.color_pair(C_OK)
        fail_col = curses.color_pair(C_FAIL) if suc["fail"] else curses.color_pair(C_DIM)

        _safe_addstr(win, row, 2,  f"{name:<18}", curses.color_pair(C_EVENT))
        _safe_addstr(win, row, 20, f"{ok_s:>5}",  ok_col)
        _safe_addstr(win, row, 25, f"{fa_s:>5}",  fail_col)
        _safe_addstr(win, row, 30, f"{total:>6}", curses.color_pair(C_DIM))
        _safe_addstr(win, row, 36, f"{avg_s:>8}", curses.color_pair(C_METRIC))
        _safe_addstr(win, row, 44, f"{mx_s:>8}",  curses.color_pair(C_WARN))
        row += 1

    if not entries:
        _safe_addstr(win, row, 2, "Sin datos de comandos aún.", curses.color_pair(C_DIM))


# ── Vista: Errores ─────────────────────────────────────────────────────────────

def _draw_errors(win, stats: dict, scroll: int) -> None:
    h, w = win.getmaxyx()
    row  = 0

    title = f"  EXCEPCIONES RECIENTES  ({len(stats['errors'])} total)"
    _safe_addstr(win, row, 0, title[:w-1], curses.color_pair(C_FAIL) | curses.A_BOLD)
    row += 1
    _hline(win, row, 0, w - 1, curses.color_pair(C_BORDER) | curses.A_DIM)
    row += 1

    errors = stats["errors"]
    if not errors:
        _safe_addstr(win, row, 2, "✅  Sin excepciones registradas.", curses.color_pair(C_OK))
        return

    visible = errors[scroll: scroll + (h - row - 2) // 3]
    for e in visible:
        if row >= h - 3:
            break
        ts    = e.get("ts", "?")[:19].replace("T", " ")
        name  = e.get("name", "?")
        props = e.get("properties", {})
        cmd   = props.get("command", "?")
        msg   = props.get("message", "")
        tb    = props.get("traceback", "")

        _safe_addstr(win, row, 2,
                     f"● [{ts}]  {name}  cmd={cmd}"[:w-3],
                     curses.color_pair(C_FAIL) | curses.A_BOLD)
        row += 1
        _safe_addstr(win, row, 4, msg[:w-5], curses.color_pair(C_WARN))
        row += 1
        if tb:
            locs = [l.strip() for l in tb.splitlines() if "File " in l]
            loc  = locs[-1] if locs else ""
            if loc:
                _safe_addstr(win, row, 4, loc[:w-5], curses.color_pair(C_DIM))
        row += 1


# ── Header y footer ────────────────────────────────────────────────────────────

_VIEW_LABELS = {"d": "dashboard", "s": "stats", "e": "errores"}

def _build_fifo_string(stats: dict) -> str:
    """Construye la cadena del ticker FIFO con los eventos más recientes."""
    all_events = (stats["cmds"] + stats["errors"] + stats["custom"])
    all_events.sort(key=lambda e: e.get("ts", ""))

    parts: list[str] = []
    for e in all_events[-60:]:  # máximo 60 eventos en el buffer
        etype   = e.get("type", "?")
        name    = e.get("name", "?")
        metrics = e.get("metrics", {})
        props   = e.get("properties", {})
        ts      = e.get("ts", "")[:19][11:]  # HH:MM:SS

        success = props.get("success")
        if etype == "exception":
            icon = "💥"
        elif success is True:
            icon = "✓"
        elif success is False:
            icon = "✗"
        elif etype == "event":
            icon = "◆"
        else:
            icon = "·"

        dur = metrics.get("duration_s")
        dur_s = f" {dur:.2f}s" if dur is not None else ""
        parts.append(f"  {icon} {ts} {name}{dur_s}  ·")

    if not parts:
        return "  Sin eventos aún  ·  Ejecuta algún comando bago  ·"
    # Duplicar para scroll continuo sin fin
    base = "".join(parts) + "   "
    return base * 4  # copia suficiente para scroll sin saltos


def _draw_fifo_bar(win, ticker_str: str, pos: int) -> None:
    """Dibuja la barra FIFO como ticker scrolling en la fila dada."""
    h, w = win.getmaxyx()
    if w <= 4:
        return

    # Fondo de la barra
    try:
        win.hline(0, 0, " ", w - 1, curses.color_pair(C_SEL))
    except curses.error:
        pass

    label = " LIVE ▶ "
    _safe_addstr(win, 0, 0, label, curses.color_pair(C_SEL) | curses.A_BOLD)

    # Zona del ticker (tras el label)
    ticker_x  = len(label)
    ticker_w  = w - ticker_x - 1
    if ticker_w <= 0:
        return

    # Extraer ventana del string (ciclo continuo)
    slen = len(ticker_str)
    if slen == 0:
        return
    pos  = pos % slen
    # Necesitamos ticker_w caracteres a partir de pos (wrap-around)
    if pos + ticker_w <= slen:
        visible = ticker_str[pos: pos + ticker_w]
    else:
        visible = ticker_str[pos:] + ticker_str[: ticker_w - (slen - pos)]

    # Colorear por token: verde para ✓, rojo para ✗/💥, amarillo para ◆
    x = ticker_x
    i = 0
    while i < len(visible) and x < w - 1:
        ch = visible[i]
        if ch == "✓":
            col = curses.color_pair(C_OK) | curses.A_BOLD
        elif ch in ("✗", "💥"):
            col = curses.color_pair(C_FAIL) | curses.A_BOLD
        elif ch == "◆":
            col = curses.color_pair(C_WARN) | curses.A_BOLD
        elif ch == "·":
            col = curses.color_pair(C_DIM)
        else:
            col = curses.color_pair(C_SEL)
        try:
            win.addstr(0, x, ch, col)
        except curses.error:
            pass
        x += 1  # curses cuenta bytes, pero para ASCII/emoji simple funciona
        i += 1


def _draw_header(win, view: str, next_refresh: float) -> None:
    h, w = win.getmaxyx()
    now   = datetime.now().strftime("%H:%M:%S")
    left  = f" 📊 BAGO Telemetría Live  [{EVENTS_FILE}]"
    secs  = max(0, round(next_refresh - time.monotonic()))
    right = f" 🕐 {now}  ↻{secs:>2}s "

    win.hline(0, 0, " ", w - 1, curses.color_pair(C_HEADER) | curses.A_BOLD)
    _safe_addstr(win, 0, 0, left[:w-len(right)-1], curses.color_pair(C_HEADER) | curses.A_BOLD)
    _safe_addstr(win, 0, max(0, w - len(right) - 1), right, curses.color_pair(C_HEADER) | curses.A_BOLD)

    # Tabs de vista (fila 2, debajo del ticker FIFO)
    tabs_y = 2
    win.hline(tabs_y, 0, " ", w - 1, curses.color_pair(C_DIM))
    col = 1
    for key, label in _VIEW_LABELS.items():
        if view == label:
            attr = curses.color_pair(C_SEL) | curses.A_BOLD
        else:
            attr = curses.color_pair(C_DIM)
        tab = f" {key.upper()}:{label} "
        _safe_addstr(win, tabs_y, col, tab, attr)
        col += len(tab) + 1


def _draw_footer(win, scroll: int, total_items: int) -> None:
    h, w = win.getmaxyx()
    footer = (
        " [q] salir  [d] dashboard  [s] stats  [e] errores  "
        "[r] refrescar  [↑/↓] scroll "
    )
    scroll_info = f" scroll:{scroll}/{max(0,total_items-1)} "
    win.hline(h - 1, 0, " ", w - 1, curses.color_pair(C_HEADER))
    _safe_addstr(win, h - 1, 0, footer[:w-len(scroll_info)-1],
                 curses.color_pair(C_HEADER))
    _safe_addstr(win, h - 1, max(0, w - len(scroll_info) - 1), scroll_info,
                 curses.color_pair(C_HEADER) | curses.A_BOLD)


# ── Bucle principal ────────────────────────────────────────────────────────────

def _live_main(stdscr, refresh_s: float) -> None:
    _init_colors()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    view         = "dashboard"
    scroll       = 0
    ticker_pos   = 0
    ticker_str   = ""
    ticker_frame = 0   # avanza 1 char cada TICKER_SPEED frames
    TICKER_SPEED = 3   # a 50ms/frame → 1 char cada 150ms ≈ ticker cómodo

    events   = _load_events()
    stats    = _compute_stats(events)
    ticker_str = _build_fifo_string(stats)
    next_ref = time.monotonic() + refresh_s

    while True:
        # ── Lectura de tecla ──
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key in (ord("q"), ord("Q"), 27):  # ESC
            break
        elif key == ord("d"):
            view = "dashboard"; scroll = 0
        elif key == ord("s"):
            view = "stats";     scroll = 0
        elif key == ord("e"):
            view = "errores";   scroll = 0
        elif key == ord("r"):
            next_ref = 0
        elif key in (curses.KEY_UP, ord("k")):
            scroll = max(0, scroll - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            scroll += 1

        # ── Refresh periódico de datos ──
        now = time.monotonic()
        if now >= next_ref:
            events     = _load_events()
            stats      = _compute_stats(events)
            ticker_str = _build_fifo_string(stats)
            next_ref   = now + refresh_s

        # ── Avance del ticker ──
        ticker_frame += 1
        if ticker_frame >= TICKER_SPEED:
            ticker_frame = 0
            ticker_pos  += 1

        # ── Dibujo (siempre, para animar el ticker) ──
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        # Fila 0: header
        _draw_header(stdscr, view, next_ref)

        # Fila 1: FIFO ticker
        try:
            ticker_win = stdscr.subwin(1, w, 1, 0)
            _draw_fifo_bar(ticker_win, ticker_str, ticker_pos)
        except curses.error:
            pass

        # Filas 3..h-2: contenido (content_y=3 porque fila 1=ticker, fila 2=tabs)
        content_y = 3
        content_h = h - content_y - 1
        total_scroll_items = 0
        if content_h > 2:
            try:
                sub = stdscr.subwin(content_h, w, content_y, 0)
                if view == "dashboard":
                    total_scroll_items = len(stats["cmds"])
                    _draw_dashboard(sub, stats, scroll)
                elif view == "stats":
                    total_scroll_items = len(stats["cmd_counts"])
                    _draw_stats(sub, stats, scroll)
                else:
                    total_scroll_items = len(stats["errors"])
                    _draw_errors(sub, stats, scroll)
            except curses.error:
                pass

        scroll = max(0, min(scroll, max(0, total_scroll_items - 1)))

        _draw_footer(stdscr, scroll, total_scroll_items)

        stdscr.noutrefresh()
        curses.doupdate()
        time.sleep(0.05)


def run(refresh_s: float = 2.0) -> None:
    """Punto de entrada público para el visor live."""
    try:
        curses.wrapper(_live_main, refresh_s)
    except KeyboardInterrupt:
        pass


# ── CLI standalone ─────────────────────────────────────────────────────────────

def main() -> None:
    args  = sys.argv[1:]
    rate  = 2.0
    if "--rate" in args:
        idx = args.index("--rate")
        if idx + 1 < len(args):
            try:
                rate = float(args[idx + 1])
            except ValueError:
                pass
    run(refresh_s=rate)


if __name__ == "__main__":
    main()
