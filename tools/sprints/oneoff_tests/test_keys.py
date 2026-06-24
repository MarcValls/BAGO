import sys
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")
from bago_inventory import gather_inventory
from pathlib import Path
d = gather_inventory(Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"))
print("top-level keys:", list(d.keys()))
print("items count:", len(d.get("items", [])))
print("tools count:", len(d.get("tools", [])))
print("agents count:", len(d.get("agents", [])))
print("modules count:", len(d.get("modules", [])))
print("scripts count:", len(d.get("scripts", [])))
print("manifests count:", len(d.get("manifests", [])))
print("summary:", d.get("summary"))
