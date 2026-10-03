"""Cross-platform key reader shared by BAGO terminal menus."""
from __future__ import annotations

import sys


def read_key() -> str:
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(msvcrt.getwch(), "")
        if ch == "\x03":
            raise KeyboardInterrupt
        return {"\r": "ENTER", "\x1b": "ESC", "\t": "TAB", " ": "SPACE"}.get(ch, ch)
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x1b":
            if not select.select([sys.stdin], [], [], 0.05)[0]:
                return "ESC"
            return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(sys.stdin.read(2), "ESC")
        return {"\r": "ENTER", "\n": "ENTER", "\t": "TAB", " ": "SPACE"}.get(ch, ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
