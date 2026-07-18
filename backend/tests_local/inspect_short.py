"""inspect_short.py — Versión corta: solo SYSTEM, TEMPLATE, PARAMETER,
LICENSE y detalles básicos por modelo.
"""
import json
import urllib.request


def show(name: str) -> dict:
    body = json.dumps({"name": name, "verbose": True}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/show", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def short(s: str, n: int = 300) -> str:
    s = s.replace("\r", "")
    return s if len(s) <= n else s[:n] + f"... <{len(s)} chars>"


for m in [
    "qwen3.6:latest",
    "bago-llama32-bago-persona:latest",
    "bago-orchestrator:latest",
    "bago-eyes:latest",
    "minicpm-v:latest",
    "granite3.2:8b",
    "llama3.2:1b",
    "llama3.2:3b",
    "qwen2.5:1.5b",
]:
    d = show(m)
    print(f"\n=== {m} ===")
    if "error" in d:
        print(f"  ERROR: {d['error']}")
        continue

    mf = d.get("modelfile", "")
    has_system = "SYSTEM " in mf or "SYSTEM \"" in mf
    has_template = "TEMPLATE " in mf
    has_params = any(l.strip().startswith("PARAMETER ") for l in mf.splitlines())
    has_messages = "MESSAGE " in mf
    has_adapter = "ADAPTER " in mf
    print(f"  modelfile_lines={len(mf.splitlines())}  system={has_system}  template={has_template}  params={has_params}  messages={has_messages}  adapter={has_adapter}")

    # Extraer SYSTEM
    if has_system:
        in_sys = False
        buf = []
        for line in mf.splitlines():
            if line.strip().startswith("SYSTEM"):
                in_sys = True
                rest = line.split("SYSTEM", 1)[1].strip()
                if rest.startswith('"""') or rest.startswith('"'):
                    rest = rest.lstrip('"').lstrip("'")
                    if rest.endswith('"""') or rest.endswith('"'):
                        rest = rest.rstrip('"').rstrip("'")
                        buf.append(rest)
                        break
                buf.append(rest)
            elif in_sys:
                if line.strip().endswith('"""'):
                    buf.append(line.strip().rstrip('"'))
                    break
                buf.append(line)
        sys_text = "\n".join(buf).strip()
        print(f"  >>> SYSTEM ({len(sys_text)} chars):")
        for ln in sys_text.splitlines()[:30]:
            print(f"      {ln[:160]}")
        if len(sys_text.splitlines()) > 30:
            print(f"      ... <{len(sys_text.splitlines())} lines total>")

    # Parameters
    params = [l.strip() for l in mf.splitlines() if l.strip().startswith("PARAMETER ")]
    if params:
        print(f"  PARAMETERS ({len(params)}):")
        for p in params:
            print(f"    {p[:200]}")

    # Template snippet
    if has_template:
        in_t = False
        buf = []
        for line in mf.splitlines():
            if line.strip().startswith("TEMPLATE"):
                in_t = True
                rest = line.split("TEMPLATE", 1)[1].strip().lstrip('"')
                if rest.endswith('"""'):
                    rest = rest.rstrip('"')
                    buf.append(rest)
                    break
                buf.append(rest)
            elif in_t:
                if line.strip().endswith('"""'):
                    buf.append(line.strip().rstrip('"'))
                    break
                buf.append(line)
        tpl = "".join(buf)
        print(f"  TEMPLATE ({len(tpl)} chars): {tpl[:300]}")

    # Capabilities
    caps = d.get("capabilities")
    if caps:
        print(f"  capabilities: {caps}")
