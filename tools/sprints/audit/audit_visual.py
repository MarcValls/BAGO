"""audit_visual.py — audita la estética del banner y cómo se imprime."""
import os, sys

ROOT = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"
os.chdir(ROOT)
sys.path.insert(0, r".bago\chat")
for k in list(sys.modules.keys()):
    if k in ("renderer", "version"):
        del sys.modules[k]

import renderer as R

print("=" * 70)
print("BANNER ACTUAL")
print("=" * 70)
b = R.banner()
print(b)
print()
print(f"len = {len(b)} chars")

print()
print("=" * 70)
print("ANÁLISIS LÍNEA POR LÍNEA")
print("=" * 70)
for i, line in enumerate(b.splitlines(), 1):
    visible = R._ANSI_RE.sub("", line)
    print(f"  L{i:2d} ({len(visible):3d} vis) |{visible}|")
