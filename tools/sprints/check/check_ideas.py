import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO")
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\tools")

BAGO_ROOT = Path(r"C:\Program Files\BAGO")
from generate_ideas import generate_ideas, format_ideas_block

state_root = BAGO_ROOT / ".bago" / "state"
ideas = generate_ideas(BAGO_ROOT, state_root, limit=6)
text = format_ideas_block(ideas)
print(text)
with open(r"C:\Program Files\BAGO\ideas_check.txt", "w", encoding="utf-8") as f:
    f.write(text)