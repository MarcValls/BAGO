#!/usr/bin/env python3
"""
bago_cpp_local.py — Stub determinista del binario `bago-cpp-local`.

Actúa como provider extremo en la cadena de fallback. Devuelve JSON con
`{ok, model, output}` y mide latencia simulada.

Uso:
    python scripts\\bago_cpp_local.py --prompt "BAGO 4.1.5 release notes" --model bago-cpp-local
    set BAGO_CPP_LATENCY_MS=50
    python scripts\\bago_cpp_local.py --prompt "..."
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--model", default="bago-cpp-local")
    parser.add_argument("--seed", type=int, default=None, help="Seed determinista (default: derivado del prompt)")
    args = parser.parse_args(argv)
    seed = args.seed if args.seed is not None else abs(hash(args.prompt)) % (2**31)
    random.seed(seed)
    latency = int(os.environ.get("BAGO_CPP_LATENCY_MS", "0"))
    t0 = time.time()
    if latency > 0:
        time.sleep(latency / 1000.0)
    # Genera un resumen fijo a partir del prompt
    snippet = (args.prompt[:60] + "...") if len(args.prompt) > 60 else args.prompt
    body = f"[cpp-local][seed={seed}][lat={int((time.time()-t0)*1000)}ms] ack: {snippet}"
    out = {
        "ok": True,
        "provider": "cpp-local",
        "model": args.model,
        "latency_ms": int((time.time() - t0) * 1000),
        "output": body,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
