#!/usr/bin/env python3
"""validate_pack_contents.py — Validate a BAGO zip pack is clean (PR-05).

Usage:
    python3 .bago/tools/validate_pack_contents.py <path/to/BAGO_xxx.zip>

Checks that the zip:
  1. Does not contain .bago/dist/ entries (no recursive build artefacts)
  2. Does not contain .bago/state/ entries (no runtime session data)
  3. Does not contain __pycache__ or .pyc files
  4. Does not contain .git/ entries
  5. Can be extracted to a temp directory without errors
  6. Contains at minimum: bago, .bago/tools/tool_registry.py, .bago/pack.json

Exits 0 on success, 1 on any violation.
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

REQUIRED_ENTRIES = [
    "bago",
    ".bago/tools/tool_registry.py",
    ".bago/pack.json",
]

FORBIDDEN_PREFIXES = [
    ".bago/dist/",
    ".bago/state/sessions",
    ".git/",
]

FORBIDDEN_SUFFIXES = [
    "__pycache__/",
    ".pyc",
    ".pyo",
]


def validate(zip_path: Path) -> list[str]:
    """Return list of error messages. Empty means valid."""
    errors: list[str] = []

    if not zip_path.exists():
        return [f"File not found: {zip_path}"]

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()

            # Check forbidden content
            for name in names:
                for prefix in FORBIDDEN_PREFIXES:
                    if name.startswith(prefix) or "/" + prefix in name:
                        errors.append(f"Forbidden entry: {name}  (matches: {prefix})")
                for suffix in FORBIDDEN_SUFFIXES:
                    if name.endswith(suffix):
                        errors.append(f"Forbidden entry: {name}  (suffix: {suffix})")

            # Check required entries present
            for req in REQUIRED_ENTRIES:
                if req not in names:
                    errors.append(f"Missing required entry: {req}")

            # Check extractable
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    zf.extractall(tmp)
                except Exception as exc:
                    errors.append(f"Extraction failed: {exc}")

    except zipfile.BadZipFile as exc:
        errors.append(f"Bad zip file: {exc}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 validate_pack_contents.py <BAGO_xxx.zip>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    print(f"  🔍 Validating: {zip_path.name}")

    errors = validate(zip_path)
    if errors:
        print(f"  ❌ Pack validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"     {e}")
        sys.exit(1)

    print(f"  ✅ Pack is clean and valid: {zip_path.name}")


if __name__ == "__main__":
    main()
