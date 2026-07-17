#!/usr/bin/env python3
"""
ollama_embeddings.py — Wrapper mínimo para /api/embeddings de Ollama.

Uso:
    python scripts\\ollama_embeddings.py --text "BAGO 4.1.5 release"
    python scripts\\ollama_embeddings.py --file README.md
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
import sys
from pathlib import Path


def _embed(text: str, model: str, base_url: str) -> dict:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/embeddings",
        data=json.dumps({"model": model, "prompt": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--dims", type=int, default=None)
    parser.add_argument("--fallback-model", default="llama3.2:3b", help="modelo a usar si el principal no está disponible")
    args = parser.parse_args(argv)
    if not args.text and not args.file:
        print("specify --text or --file")
        return 1
    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="ignore")[:8192]
    for m in (args.model, args.fallback_model):
        if m == args.fallback_model and m == args.model:
            continue
        try:
            data = _embed(text, m, args.base_url)
        except urllib.error.HTTPError as e:
            print(f"model {m!r} failed: HTTP {e.code}")
            continue
        except urllib.error.URLError as e:
            print(f"ollama not reachable: {e}")
            return 2
        else:
            vec = data.get("embedding") or (data.get("embeddings") or [[]])[0]
            if args.dims:
                vec = vec[: args.dims]
            print(json.dumps({"model": m, "dims": len(vec), "vector": vec}, indent=2, ensure_ascii=False))
            return 0
    print("no embedding model available")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
