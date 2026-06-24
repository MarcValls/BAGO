import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO")
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\tools")

BAGO_ROOT = Path(r"C:\Program Files\BAGO")
state_root = BAGO_ROOT / ".bago" / "state"

from extract_digest import extract_digest, format_digest_block
d = extract_digest(state_root)
text = format_digest_block(d)
print(text)
with open(r"C:\Program Files\BAGO\digest_check.txt", "w", encoding="utf-8") as f:
    f.write(text)