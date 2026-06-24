"""Improve B/A/G/O block letters."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

old = '''    # Block letters B / A / G / O. Cada letra: 5 filas x 5 cols.
    B = [
        "█████ ",
        "█   █ ",
        "█   █ ",
        "█████ ",
        "█   █ ",
    ]
    A = [
        " ███ ",
        "█   █",
        "█████",
        "█   █",
        "█   █",
    ]
    G = [
        " ████",
        "█    ",
        "█  ██",
        "█   █",
        " ███ ",
    ]
    O = [
        " ███ ",
        "█   █",
        "█   █",
        "█   █",
        " ███ ",
    ]'''

new = '''    # Block letters B / A / G / O. Cada letra: 5 filas x 5 cols.
    # Diseñadas para que cada letra tenga la misma altura visual
    # y las columnas coincidan fila a fila cuando se concatenan.
    B = [
        "████  ",
        "█   █ ",
        "█   █ ",
        "████  ",
        "█   █ ",
    ]
    A = [
        " ██  ",
        "█  █ ",
        "████ ",
        "█  █ ",
        "█  █ ",
    ]
    G = [
        " ███ ",
        "█    ",
        "█ ██ ",
        "█  █ ",
        " ██  ",
    ]
    O = [
        " ██  ",
        "█  █ ",
        "█  █ ",
        "█  █ ",
        " ██  ",
    ]'''

if old not in text:
    print("OLD NOT FOUND")
    raise SystemExit(1)

text = text.replace(old, new, 1)
P.write_text(text, encoding="utf-8")
print("patched")