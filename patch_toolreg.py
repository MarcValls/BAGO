from pathlib import Path
import os

with open('.bago/tools/tool_registry.py','r',encoding='utf-8') as f:
    lines = f.readlines()

out = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'def _resolve_module(stem: str) -> Path:' in line:
        out.append(line)
        out.append('        """Return the first existing path for module stem or package __main__.py."""\n')
        out.append('        candidates = [\n')
        out.append('            TOOLS_DIR / f"{stem}.py",\n')
        out.append('            TOOLS_DIR / stem / "__main__.py",\n')
        out.append('            BAGO_ROOT / "core" / f"{stem}.py",\n')
        out.append('            BAGO_ROOT / "core" / stem / "__main__.py",\n')
        out.append('        ]\n')
        out.append('        if "." in stem:\n')
        out.append('            dotted = stem.replace(".", os.sep)\n')
        out.append('            candidates += [\n')
        out.append('                TOOLS_DIR / f"{dotted}.py",\n')
        out.append('                BAGO_ROOT / f"{dotted}.py",\n')
        out.append('                BAGO_ROOT / "core" / f"{dotted}.py",\n')
        out.append('            ]\n')
        out.append('        for candidate in candidates:\n')
        out.append('            if candidate.exists():\n')
        out.append('                return candidate\n')
        out.append('        file_hits = list(BAGO_ROOT.rglob(f"{stem}.py"))\n')
        out.append('        if file_hits:\n')
        out.append('            return file_hits[0]\n')
        out.append('        package_hits = [p for p in BAGO_ROOT.rglob("__main__.py") if p.parent.name == stem]\n')
        out.append('        if package_hits:\n')
        out.append('            return package_hits[0]\n')
        out.append('        return TOOLS_DIR / f"{stem}.py"\n')
        i += 1
        while i < len(lines) and not lines[i].strip().startswith('def '):
            i += 1
        continue
    out.append(line)
    i += 1

with open('.bago/tools/tool_registry.py','w',encoding='utf-8') as f:
    f.writelines(out)
print('PATCHED tool_registry')
