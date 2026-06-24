"""Fix the B in bago_logo_text so it actually reads as B."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

old_b = '''    B = [
        "████  ",
        "█   █ ",
        "█   █ ",
        "████  ",
        "█   █ ",
    ]'''

new_b = '''    B = [
        "█████",
        "█   █",
        "█████",
        "█   █",
        "█████",
    ]'''

if old_b not in text:
    print("OLD B NOT FOUND")
    raise SystemExit(1)
text = text.replace(old_b, new_b, 1)
P.write_text(text, encoding="utf-8")
print("patched")