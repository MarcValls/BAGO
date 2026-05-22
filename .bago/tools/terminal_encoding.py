import sys
from pathlib import Path

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