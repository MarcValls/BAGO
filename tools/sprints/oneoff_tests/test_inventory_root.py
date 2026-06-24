"""test_inventory_root.py — verify inventory finds pieces in different roots."""
import sys, os
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\bago_v4.7.2\BAGO-4.7.2\.bago\tools")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\bago_v4.7.2\BAGO-4.7.2\bago_core")

from bago_inventory import gather_inventory, format_startup_text
from pathlib import Path

print("=== Inventory at different roots ===")
for root_label, root_path in [
    ("AppData BAGO", r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"),
    ("User home", r"C:\Users\AMTEC_Terminal_1º"),
    ("Release 4.7.2 extract", r"C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\bago_v4.7.2\BAGO-4.7.2"),
]:
    print(f"\n--- {root_label}: {root_path} ---")
    data = gather_inventory(Path(root_path))
    counts = data.get("counts", {})
    print(f"  tools={counts.get('tool', 0)} "
          f"agents={counts.get('agent', 0)} "
          f"scripts={counts.get('script', 0)} "
          f"modules={counts.get('module', 0)} "
          f"manifests={counts.get('manifest', 0)}")
    print(f"  startup_text: {format_startup_text(data, limit=4)}")
