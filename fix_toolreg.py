with open('.bago/tools/tool_registry.py','r',encoding='utf-8') as f:
    txt = f.read()

old = """        return TOOLS_DIR / f\"{stem}.py\"
def get_cmd_names() -> list[str]:"""
new = """        return TOOLS_DIR / f\"{stem}.py\"

    result = {}
    for name, entry in REGISTRY.items():
        module_path = _resolve_module(entry.module)
        cmd = [PYTHON, str(module_path)]
        if name in _extra_args:
            cmd += _extra_args[name]
        result[name] = cmd
    return result


def get_cmd_names() -> list[str]:"""

if old in txt:
    txt = txt.replace(old, new)
    with open('.bago/tools/tool_registry.py','w',encoding='utf-8') as f:
        f.write(txt)
    print('FIXED')
else:
    print('PATTERN NOT FOUND')
