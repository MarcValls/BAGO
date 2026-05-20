import os
with open('bago_core/launcher.py','r',encoding='utf-8') as f:
    lines = f.readlines()

out = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'def _find_tool(stem: str) -> "Path | None":' in line:
        out.append(line)
        out.append('    """Locate a tool by stem: TOOLS first, then rglob fallback.\n')
        out.append('    Supports dotted module names (e.g. supervision.supervisor)."""\n')
        out.append('    direct = TOOLS / f"{stem}.py"\n')
        out.append('    if direct.exists():\n')
        out.append('        return direct\n')
        out.append('    if "." in stem:\n')
        out.append('        dotted = TOOLS / f"{stem.replace(\".\", os.sep)}.py"\n')
        out.append('        if dotted.exists():\n')
        out.append('            return dotted\n')
        out.append('        dotted2 = BAGO_ROOT / f"{stem.replace(\".\", os.sep)}.py"\n')
        out.append('        if dotted2.exists():\n')
        out.append('            return dotted2\n')
        out.append('    hits = list(BAGO_ROOT.rglob(f"{stem}.py"))\n')
        out.append('    return hits[0] if hits else None\n')
        i += 1
        # skip old body until blank line or next def
        while i < len(lines) and not lines[i].strip().startswith('def '):
            i += 1
        continue
    out.append(line)
    i += 1

with open('bago_core/launcher.py','w',encoding='utf-8') as f:
    f.writelines(out)
print('PATCHED')
