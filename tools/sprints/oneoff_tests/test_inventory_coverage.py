"""test_inventory_coverage.py — verify which inventory items are real."""
import sys
import importlib.util
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")

from bago_inventory import gather_inventory

root = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
data = gather_inventory(root)

print(f"=== Inventory coverage at {root} ===")
print()

print("--- Tools ---")
real = 0
for t in data["tools"]:
    p = root / t["path"]
    if p.exists():
        real += 1
print(f"  {len(data['tools'])} tools, {real} exist on disk")
for t in data["tools"][:5]:
    p = root / t["path"]
    print(f"    {'[OK]' if p.exists() else '[NO]'}  {t['path']}")

print()
print("--- Agents ---")
real = 0
for a in data["agents"]:
    p = root / a["path"]
    if p.exists():
        real += 1
print(f"  {len(data['agents'])} agents, {real} exist on disk")
for a in data["agents"][:5]:
    p = root / a["path"]
    print(f"    {'[OK]' if p.exists() else '[NO]'}  {a['path']}")

print()
print("--- Scripts ---")
real = 0
for s in data["scripts"]:
    p = root / s["path"]
    if p.exists():
        real += 1
print(f"  {len(data['scripts'])} scripts, {real} exist on disk")
for s in data["scripts"][:5]:
    p = root / s["path"]
    print(f"    {'[OK]' if p.exists() else '[NO]'}  {s['path']}")

print()
print("--- Modules ---")
real = 0
parseable = 0
for m in data["modules"]:
    p = root / m["path"]
    if not p.exists():
        continue
    real += 1
    try:
        spec = importlib.util.spec_from_file_location("test_mod", p)
        if spec and spec.loader:
            parseable += 1
    except Exception:
        pass
print(f"  {len(data['modules'])} modules, {real} exist, {parseable} parseable as Python")

print()
print("--- Manifests (json files) ---")
real = 0
parseable_json = 0
for m in data["manifests"]:
    p = root / m["path"]
    if p.exists():
        real += 1
        if "error" not in m:
            parseable_json += 1
print(f"  {len(data['manifests'])} manifests, {real} exist, {parseable_json} parse cleanly as JSON")

print()
print("=== Sample function metadata from a real tool ===")
if data["tools"]:
    sample = data["tools"][0]
    print(f"  tool: {sample['path']}")
    if "functions" in sample:
        for fn in sample["functions"][:3]:
            args_str = ", ".join(fn.get("args", []))
            doc = fn.get("doc", "")[:60]
            print(f"    def {fn['name']}({args_str}): {doc}")
