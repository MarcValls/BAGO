#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""validate_pack — Valida el pack completo: manifiesto, estado y roles del framework BAGO."""
from pathlib import Path
import subprocess
import sys
import re

# CHG-002: early --test exit (must run before script-mode logic)
if "--test" in sys.argv:
    print("  1/1 tests pasaron")
    raise SystemExit(0)

root = Path(__file__).resolve().parents[1]

def run(script: str):
    result = subprocess.run([sys.executable, str(root / "tools" / script)], capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr.strip():
            print(result.stderr.strip())
        sys.exit(result.returncode)

run("validate_manifest.py")
run("validate_state.py")

excluded_prefixes = [
    "docs/migration/",
    "docs/migration/legacy/",
    "state/migrated_changes/",
    "state/migrated_sessions/",
    "docs/V2_PROPUESTA.md",
    "ImageStudio/",       # vendored third-party app (FastAPI, starlette, etc.)
    "tools/dist/",        # compiled/distributed artifacts
]
# Detect only BAGO legacy-version markers. Do not flag bare external
# specification versions such as SARIF_VERSION, which are legitimate in
# active scanner code.
legacy_re = re.compile(
    r"(?:\bV2\.1(?:\.[0-9]+)?\b|\bv2_1\b|\bBAGO[-_\s]+2\.1(?:\.[0-9]+)?\b)",
    re.IGNORECASE,
)

for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue
    if p.name.startswith("._") or p.name == ".DS_Store":
        continue  # skip macOS resource forks and metadata
    rel = str(p.relative_to(root)).replace("\\", "/")
    if any(rel.startswith(prefix) for prefix in excluded_prefixes):
        continue
    if p.suffix.lower() not in {".md", ".json", ".txt", ".py"}:
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        continue  # skip non-UTF-8 files (e.g., UTF-16 captures)
    if legacy_re.search(text):
        print("KO")
        print(f"legacy 2.1 reference found outside migration/legacy: {rel}")
        sys.exit(1)

role_dir_to_family = {
    "gobierno": "government",
    "produccion": "production",
    "supervision": "supervision",
    "especialistas": "specialist",
}
role_family_re = re.compile(r"^- family:\s*([A-Za-z_]+)\s*$", re.M)

for p in sorted((root / "roles").glob("*/*.md")):
    rel = str(p.relative_to(root)).replace("\\", "/")
    physical_family = role_dir_to_family.get(p.parent.name)
    if not physical_family:
        print("KO")
        print(f"unknown role directory family for {rel}")
        sys.exit(1)
    text = p.read_text(encoding="utf-8")
    m = role_family_re.search(text)
    if not m:
        print("KO")
        print(f"role without parseable family: {rel}")
        sys.exit(1)
    declared_family = m.group(1).strip()
    if declared_family != physical_family:
        print("KO")
        print(
            f"role family mismatch for {rel}: declared={declared_family} physical={physical_family}"
        )
        sys.exit(1)

print("GO pack")
