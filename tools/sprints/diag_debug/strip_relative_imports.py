"""Strip 'from .repl_X' -> 'from repl_X' in repl.py."""
from pathlib import Path

p = Path(r"C:\Program Files\BAGO\.bago\chat\repl.py")
text = p.read_text(encoding="utf-8")
new = text.replace("from .repl_", "from repl_")
p.write_text(new, encoding="utf-8")
print("done")
print(f"replacements: {text.count('from .repl_')}")