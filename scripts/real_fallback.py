#!/usr/bin/env python3
"""
real_fallback.py — Demuestra el contrato `quality` con fallback real de
ollama-local a cpp-local.

Uso:
    python scripts\\real_fallback.py --prompt "BAGO release notes"
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Asegurar que el binario stub esté resoluble vía `bago-cpp-local` cuando se
# exporta al PATH del usuario (caso real de la cadena de fallback).
_STUB_DIR = Path(__file__).resolve().parent
if str(_STUB_DIR) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_STUB_DIR) + os.pathsep + os.environ.get("PATH", "")


def _ollama_call(model: str, prompt: str, base_url: str) -> tuple[bool, str, float]:
    """Llama a ollama /api/generate y mide latencia. Devuelve ok=False si no responde."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return True, (body.get("response") or "").strip(), time.time() - t0
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return False, f"ollama unreachable: {e}", time.time() - t0
    except Exception as e:
        return False, f"ollama error: {e}", time.time() - t0


def _cpp_call(prompt: str, model: str = "bago-cpp-local") -> tuple[bool, str, float]:
    """Llama al binario cpp-local (`bago-cpp-local.cmd` o `bago_cpp_local.py`)."""
    candidates = [
        "bago-cpp-local",
        "bago-cpp-local.cmd",
        "bago-cpp-local.exe",
    ]
    exe: str | None = None
    for c in candidates:
        p = shutil.which(c)
        if p:
            exe = p
            break
    if not exe:
        # Fallback: invocar el stub python directamente
        stub = _STUB_DIR / "bago_cpp_local.py"
        if stub.exists():
            cmd = [sys.executable, str(stub), "--prompt", prompt, "--model", model]
        else:
            return False, "cpp-local binary not in PATH", 0.0
    else:
        cmd = [exe, "--prompt", prompt, "--model", model]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as e:
        return False, f"cpp-local failed: {e}", time.time() - t0
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip(), time.time() - t0
    return True, proc.stdout.strip(), time.time() - t0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--max-tokens", type=int, default=120)
    args = parser.parse_args(argv)

    chain = [("ollama-local", args.model, _ollama_call), ("cpp-local", "bago-cpp-local", _cpp_call)]
    print(json.dumps({"chain": [c[0] for c in chain]}, indent=2))
    for provider, model, fn in chain:
        if fn is _ollama_call:
            ok, text, ms = fn(model, args.prompt, args.base_url)
        else:
            ok, text, ms = fn(args.prompt, model)
        print(json.dumps({"provider": provider, "model": model, "ok": ok, "latency_ms": round(ms * 1000), "output_preview": text[:args.max_tokens]}, indent=2, ensure_ascii=False))
        if ok:
            return 0
    print(json.dumps({"status": "fallback_exhausted"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
