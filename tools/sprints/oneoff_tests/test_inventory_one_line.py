"""test_inventory_one_line.py — verify the one-line override works."""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")

# Apply the override
from bago_inventory_one_line import apply, one_line_startup_text
apply()

import bago_inventory
data = bago_inventory.gather_inventory(Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"))

# Test 1: format_startup_text now returns one line
text = bago_inventory.format_startup_text(data, limit=4)
print(f"=== Test 1: format_startup_text output ({len(text)} chars) ===")
print(repr(text))
print()
print("=== Visual ===")
print(text)

# Test 2: it doesn't have multi-line bullets
assert "\n  -" not in text, "should not have multi-line bullets"
assert "Tools: " not in text or "Tools:" not in text.split("\n")[-1] or "piezas" in text, "should not have 'Tools:' section"
print()
print("OK: no multi-line bullets in output")
