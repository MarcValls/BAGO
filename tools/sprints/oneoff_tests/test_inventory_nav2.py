"""test_inventory_nav2.py — verify the inventory browser with AppData root."""
import sys, io
from pathlib import Path

# CRITICAL: import from the LOCAL bago_inventory.py in AppData (not the
# release extract that uses DIFFERENT paths).
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")

from bago_inventory import gather_inventory, format_text

root = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
data = gather_inventory(root)
print(f"Total pieces: {data['summary']['total_pieces']}")
print(f"Tools: {data['summary']['tool_files']}")
print(f"Agents: {data['summary']['agent_files']}")
print(f"Scripts: {data['summary']['script_files']}")
print(f"Modules: {data['summary']['module_files']}")
print(f"Manifests: {data['summary']['json_manifests']}")
print()
print("First 3 tools:")
for t in data["tools"][:3]:
    print(f"  {t['path']}")
