import os
import sys
from pathlib import Path


def bootstrap_runtime_encoding() -> None:
    """Fuerza UTF-8 para stdio y variables de entorno del proceso."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    force_utf8_stdio()

def force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

def safe_print(text: str, ascii_mode: bool = False) -> None:
    if ascii_mode:
        # strip extended chars, keep basic ASCII
        text = text.encode("ascii", "ignore").decode("ascii")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "ignore").decode("ascii"))

def main():
    force_utf8_stdio()
    print("GO encoding")

if __name__ == "__main__":
    main()
