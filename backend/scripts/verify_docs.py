#!/usr/bin/env python3
"""
verify_docs.py — Sweep de docs y scripts para detectar menciones obsoletas de
`granite3.2:8b` o `llama3.2:latest` que no estén marcadas como ejemplos
explícitos (e.g. backup modelo grande).

Uso:
    python scripts\\verify_docs.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CANONICAL_DEFAULT = "llama3.2:3b"
OBSOLETE = ["granite3.2:8b", "llama3.2:latest"]
ALLOWED_FILES = {"model_equivalence.py"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-bago", default=None)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    if not repo.exists():
        print(f"path missing: {repo}")
        return 1
    failures: list[str] = []
    patterns = ["*.md", "*.ps1", "*.cmd", "*.py", "*.json"]
    files: list[Path] = []
    for pat in patterns:
        for p in repo.rglob(pat):
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            if p.is_file() and p.name not in ("verify_docs.py",):
                files.append(p)
    total_obs = 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if p.name in ALLOWED_FILES:
            continue
        for obs in OBSOLETE:
            for m in re.finditer(re.escape(obs), text):
                line_no = text.count("\n", 0, m.start()) + 1
                line = text.splitlines()[line_no - 1] if line_no - 1 < len(text.splitlines()) else ""
                # Permitimos menciones en secciones que documentan el backup
                # explícitamente (e.g. "BAGO accepts granite3.2:8b as alternate")
                if "example" in line.lower() or "alternate" in line.lower() or "RL" in line:
                    continue
                failures.append(f"{p}:{line_no}: {obs}: {line.strip()[:80]}")
                total_obs += 1
    if failures:
        print(f"docs:DRIFT ({total_obs} occurrences)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"docs:ok (canonical={CANONICAL_DEFAULT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
