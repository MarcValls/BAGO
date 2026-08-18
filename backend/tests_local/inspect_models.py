"""inspect_models.py — Saca la config completa (Modelfile, system prompt,
template, parámetros, licenses) de cada modelo Ollama. Útil para ver
'puertas' ocultas: system prompts impuestos, stop tokens, format constraints,
penalties, etc.
"""
import json
import sys
import urllib.request


def show(name: str) -> dict:
    body = json.dumps({"name": name, "verbose": True}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/show",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def short(s: str, n: int = 200) -> str:
    s = s.replace("\r", "")
    if len(s) <= n:
        return s
    return s[:n] + f"... <+{len(s)-n}>"


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


models = [
    "qwen3.6:latest",
    "bago-llama32-bago-persona:latest",
    "bago-orchestrator:latest",
    "bago-eyes:latest",
    "minicpm-v:latest",
    "granite3.2:8b",
    "llama3.2:1b",
    "llama3.2:3b",
    "qwen2.5:1.5b",
]

for m in models:
    section(m)
    d = show(m)
    if "error" in d:
        print(f"  ERROR: {d['error']}")
        continue

    # Modelfile raw
    mf = d.get("modelfile", "")
    if mf:
        print("--- Modelfile ---")
        for line in mf.splitlines():
            if not line.strip():
                continue
            # System prompt suele ser multi-línea, marcar
            if line.startswith("SYSTEM") or line.startswith('SYSTEM """'):
                print("  >>> " + line[:120])
            elif line.startswith("PARAMETER") or line.startswith("TEMPLATE") \
                 or line.startswith("ADAPTER") or line.startswith("LICENSE") \
                 or line.startswith("MESSAGE"):
                print("  " + line[:200])
            else:
                print("  " + line[:200])

    # Campos top-level que importan
    for k in ("details", "model_info", "capabilities"):
        v = d.get(k)
        if v:
            print(f"--- {k} ---")
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if isinstance(vv, (str, int, float, bool)):
                        if len(str(vv)) < 200:
                            print(f"  {kk}: {vv}")
                        else:
                            print(f"  {kk}: {short(str(vv), 120)}")
                    elif isinstance(vv, list) and vv and isinstance(vv[0], str):
                        print(f"  {kk}: {vv}")
            else:
                print(f"  {v}")

print()
print("=" * 78)
print("FIN")
print("=" * 78)
