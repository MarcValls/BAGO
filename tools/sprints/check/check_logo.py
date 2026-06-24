import sys
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
import renderer as R
logo = R.bago_logo_text()
lines = logo.split("\n")
out = []
for i, l in enumerate(lines, 1):
    out.append(f"L{i} len={len(l):2d}  |{l}|")
with open(r"C:\Program Files\BAGO\logo_check.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out))