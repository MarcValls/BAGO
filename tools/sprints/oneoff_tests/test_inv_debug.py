"""test_inv_debug.py — directly call gather_inventory from AppData root."""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\bago_v4.7.2\BAGO-4.7.2\.bago\tools")

from bago_inventory import gather_inventory

root = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
data = gather_inventory(root)
print("counts:", data.get("counts", {}))
print("total items in 'items' field:", len(data.get("items", []) or []))
print("first 3 items:")
for item in (data.get("items", []) or [])[:3]:
    print(" ", item)
