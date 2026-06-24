"""Remove the duplicate `from __future__ import annotations` line."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\bago_core\evidence_generator.py")
text = P.read_text(encoding="utf-8")
lines = text.split("\n")

# Keep only the first `from __future__` line.
new_lines = []
seen_future = False
for line in lines:
    if line.startswith("from __future__"):
        if seen_future:
            continue
        seen_future = True
    new_lines.append(line)

P.write_text("\n".join(new_lines), encoding="utf-8")
print(f"fixed: {P.name}")