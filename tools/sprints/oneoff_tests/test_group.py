"""test_group_items.py — debug _group_items."""
import sys
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")

from pathlib import Path
import repl_inventory_nav as browser

data = browser._load_inventory(Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"))
print("data keys:", list(data.keys()))
print()

# Try the function directly
grouped = browser._group_items(data)
print("grouped:", list(grouped.keys()))
for kind, items in grouped.items():
    print(f"  {kind}: {len(items)} items")
