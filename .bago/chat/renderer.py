#!/usr/bin/env python3
"""
renderer.py — BAGO 4.0 Chat Visual Renderer

Utilidades de rendering para el REPL:
- Colores ANSI + fallback Windows
- Cajas de texto, banners, tablas
- Formateo de mensajes del sistema
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_SUPPORT = _supports_color()
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def colorize(text: str, *codes: str) -> str:
    if not _SUPPORT:
        return text
    return f"{''.join(codes)}{text}{Color.RESET}"


def dim(text: str) -> str:
    return colorize(text, Color.DIM)


def bold(text: str) -> str:
    return colorize(text, Color.BOLD)


def ok(text: str) -> str:
    return colorize(text, Color.BRIGHT_GREEN)


def warn(text: str) -> str:
    return colorize(text, Color.BRIGHT_YELLOW)


def error(text: str) -> str:
    return colorize(text, Color.BRIGHT_RED)


def info(text: str) -> str:
    return colorize(text, Color.BRIGHT_BLUE)


def accent(text: str) -> str:
    return colorize(text, Color.BRIGHT_CYAN)


def bright_black(text: str) -> str:
    return colorize(text, Color.BRIGHT_BLACK)


def magenta(text: str) -> str:
    return colorize(text, Color.BRIGHT_MAGENTA)


def box(title: str, lines: list[str], width: int = 60) -> str:
    """Dibuja una caja con título."""
    def visible_len(text: str) -> int:
        return len(_ANSI_RE.sub("", text))

    def pad(text: str, inner_width: int) -> str:
        return text + (" " * max(0, inner_width - visible_len(text)))

    inner_width = width - 3
    top = "┌" + "─" * (width - 2) + "┐"
    title_line = f"│ {pad(bold(title), inner_width)}│"
    sep = "├" + "─" * (width - 2) + "┤"
    body = []
    for line in lines:
        # Truncate or wrap if needed; keep simple for now
        body.append(f"│ {pad(line, inner_width)}│")
    bottom = "└" + "─" * (width - 2) + "┘"
    return "\n".join([top, title_line, sep] + body + [bottom])


def banner() -> str:
    """Banner de inicio de BAGO 4.0."""
    art = [
        r"  ____    _    ____   ___  ",
        r" | __ )  / \  / ___| / _ \ ",
        r" |  _ \ / _ \ \___ \| | | |",
        r" | |_) / ___ \ ___) | |_| |",
        r" |____/_/   \_\____/ \___/ ",
        r"           v4.0 — Session-First AI Chat",
    ]
    colored = [colorize(line, Color.BRIGHT_CYAN) for line in art[:-1]]
    colored.append(colorize(art[-1], Color.DIM))
    return "\n".join(colored)


def status_line(provider: str, model: str, tokens: int, health_ok: bool) -> str:
    """Línea compacta de estado."""
    h = ok("●") if health_ok else error("●")
    return f"{h} {accent(provider)}/{bold(model)} · {dim(str(tokens) + ' tok')}"


def print_message(role: str, content: str) -> None:
    """Imprime un mensaje del chat con color según rol."""
    if role == "user":
        prefix = bold("You")
        color = Color.BRIGHT_WHITE
    elif role == "assistant":
        prefix = bold(colorize("BAGO", Color.BRIGHT_CYAN))
        color = Color.RESET
    elif role == "system":
        prefix = dim("SYS")
        color = Color.DIM
    else:
        prefix = role
        color = Color.RESET

    lines = content.splitlines()
    for i, line in enumerate(lines):
        if i == 0:
            print(f"{prefix} {color}{line}{Color.RESET}")
        else:
            print(f"    {color}{line}{Color.RESET}")


def print_switch_notification(result: dict) -> None:
    """Notificación visual de cambio de provider."""
    if not result.get("ok"):
        print(error(f"❌ Switch fallido: {result.get('error', 'unknown')}"))
        return

    old = f"{result.get('old_provider')}/{result.get('old_model')}"
    new = f"{result.get('new_provider')}/{result.get('new_model')}"
    print(ok(f"✓ Switch: {dim(old)} → {bold(new)}"))
    for w in result.get("warnings", []):
        print(warn(f"  ⚠ {w}"))


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Tabla simple en consola."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt(row: list[str]) -> str:
        return " │ ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(row))

    sep = "─┼─".join("─" * (w + 2) for w in col_widths)
    print(bold(fmt(headers)))
    print(sep)
    for row in rows:
        print(fmt(row))


def _run_tests() -> int:
    print(banner())
    print()
    print(box("Test", ["Line 1", "Line 2"]))
    print()
    print(status_line("ollama-local", "qwen2.5:14b", 1234, True))
    print_message("user", "Hola")
    print_message("assistant", "Hola, ¿qué tal?")
    print_switch_notification({"ok": True, "old_provider": "codex", "old_model": "gpt-4o", "new_provider": "anthropic", "new_model": "claude-sonnet-4", "warnings": ["Downgrade detectado"]})
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
