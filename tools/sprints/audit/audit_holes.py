"""audit_holes.py — audita todos los lugares donde aparece versión visible al usuario."""
import os, sys, json
from pathlib import Path

ROOT = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

print("=" * 70)
print("AUDITORÍA DE VERSIONES VISIBLES AL USUARIO")
print("=" * 70)

# 1. release_version.txt
rv = ROOT / "release_version.txt"
print(f"\n1. release_version.txt: {rv.read_text(encoding='utf-8').strip()!r}")

# 2. versions.json:current
vj = ROOT / "versions.json"
data = json.loads(vj.read_text(encoding='utf-8'))
print(f"2. versions.json:current: {data.get('current')!r}")

# 3. pyproject.toml version
pt = ROOT / "pyproject.toml"
for line in pt.read_text(encoding='utf-8').splitlines():
    if line.strip().startswith("version ="):
        print(f"3. pyproject.toml: {line.strip()}")
        break

# 4. Status del módulo version
sys.path.insert(0, str(ROOT / "bago_core"))
for k in list(sys.modules.keys()):
    if k == "version":
        del sys.modules[k]
from version import CURRENT
print(f"4. bago_core/version.py:CURRENT = {CURRENT!r}")

# 5. renderer banner
sys.path.insert(0, str(ROOT / ".bago" / "chat"))
for k in list(sys.modules.keys()):
    if k in ("renderer", "version"):
        del sys.modules[k]
import renderer as R
print(f"5. renderer._BAGO_VERSION = {R._BAGO_VERSION!r}")
b = R.banner()
# Extract the "vX.Y.Z" line
for line in b.splitlines():
    if "v" in line and "Session" in line:
        print(f"   banner version line: {line.strip()}")
        break

# 6. Repl.py welcome message uses which version?
os.chdir(ROOT)
for k in list(sys.modules.keys()):
    if k in ("renderer", "version"):
        del sys.modules[k]
import renderer as R2
welcome_template = "Bienvenido a BAGO {R._BAGO_VERSION}"
print(f"6. repl.py welcome template (if patched): Bienvenido a BAGO {R2._BAGO_VERSION}")

# 7. Hardcoded "4.1.5" o "4.7" en archivos que el usuario podría ver en arranque
print()
print("=" * 70)
print("BÚSQUEDA DE VERSIONES HARDCODEADAS EN CÓDIGO QUE EL USUARIO VE")
print("=" * 70)

# Search repl.py and renderer.py for hardcoded version literals
import re
version_pattern = re.compile(r'["\'](\d+\.\d+\.\d+)["\']|["\'](\d+\.\d+)["\']')

chat_files = list((ROOT / ".bago" / "chat").glob("*.py"))
for f in chat_files:
    src = f.read_text(encoding='utf-8', errors='replace')
    # Skip renderer.py (already patched) and repl.py (already patched)
    for m in version_pattern.finditer(src):
        v = m.group(1) or m.group(2)
        # Only flag hardcoded version-like strings in print/f-string contexts
        # (skip path-like strings like "4.1.5.tar.gz" or json data)
        ctx_start = max(0, m.start() - 60)
        ctx = src[ctx_start:m.end() + 20]
        if any(kw in ctx.lower() for kw in ['bago', 'version', 'welcome', 'banner']):
            rel = f.relative_to(ROOT)
            print(f"  {rel}:{src[:m.start()].count(chr(10))+1}: {v!r}")
            print(f"    ctx: ...{ctx.strip()[:80]}...")
