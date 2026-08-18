"""bench_warmup.py — Re-prueba los modelos que hicieron timeout con warm-up
previo (la primera llamada carga el modelo en RAM, las siguientes son rápidas).
"""
import json
import time
import urllib.request


def query(model, prompt, timeout_s=180):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2, "num_predict": 128},
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            d = json.load(r)
            return d.get("response", ""), time.time() - t0, None
    except Exception as exc:
        return "", time.time() - t0, f"{type(exc).__name__}: {exc}"


SUSPECTS = ["qwen3.6:latest", "bago-llama32-bago-persona:latest", "granite3.2:8b"]

print("Warm-up: 2 calls por modelo con prompt trivial 'hi'")
for m in SUSPECTS:
    print(f"\n--- {m} ---")
    # warm-up
    for i in (1, 2):
        text, dt, err = query(m, "hi", timeout_s=240)
        print(f"  warmup {i}: {dt:.1f}s  err={err}  resp={text[:60]!r}")
        if err:
            break
    # medida real
    text, dt, err = query(m, "Di hola en una sola frase.", timeout_s=60)
    if err:
        print(f"  real: ERROR {err} ({dt:.1f}s)")
    else:
        ok = (sum(c.isalpha() or c.isspace() for c in text) / max(len(text), 1)) > 0.4
        verdict = "✅ OK" if ok else "💥 degenerate"
        print(f"  real: [{verdict}] {dt:.1f}s  len={len(text)}  >> {text[:200]!r}")
