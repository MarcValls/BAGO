"""Square block letters: every letter is exactly 5x5.

B = vertical bar + top bump + middle bar + bottom bump
A = triangle + crossbar (filled center row)
G = C-shape with horizontal bar + right hook at row 3-4
O = rounded rectangle

All cells use '█' for solid, ' ' for background. Same dimensions so the
final logo has uniform height.
"""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

old_b = '''    B = [
        "█████",
        "█   █",
        "█████",
        "█   █",
        "█████",
    ]'''
old_a = '''    A = [
        " ██  ",
        "█  █ ",
        "████ ",
        "█  █ ",
        "█  █ ",
    ]'''
old_g = '''    G = [
        " ███ ",
        "█    ",
        "█ ██ ",
        "█  █ ",
        " ██  ",
    ]'''
old_o = '''    O = [
        " ██  ",
        "█  █ ",
        "█  █ ",
        "█  █ ",
        " ██  ",
    ]'''

# 5 cols of '█'/' ' each, all square 5x5.
new_b = '''    B = [
        "█████",
        "█   █",
        "█████",
        "█   █",
        "█████",
    ]'''
new_a = '''    A = [
        " ███ ",
        "█   █",
        "█████",
        "█   █",
        "█   █",
    ]'''
new_g = '''    G = [
        " ████",
        "█    ",
        "█ ███",
        "█   █",
        " ████",
    ]'''
new_o = '''    O = [
        " ███ ",
        "█   █",
        "█   █",
        "█   █",
        " ███ ",
    ]'''

for old, new in [(old_b, new_b), (old_a, new_a), (old_g, new_g), (old_o, new_o)]:
    if old not in text:
        print(f"OLD NOT FOUND: {old[:30]!r}...")
        raise SystemExit(1)
    text = text.replace(old, new, 1)
P.write_text(text, encoding="utf-8")
print("patched")