"""Validación de pack BAGO y ZIP distribuible."""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import re
import tempfile
import zipfile
from pathlib import Path


def validate_pack_full(root: Path, validate_manifest, validate_state) -> int:
    """Full pack validation: manifest + state + legacy-ref scan + role family checks."""
    if validate_manifest(root) != 0:
        return 1
    if validate_state(root) != 0:
        return 1

    excluded_prefixes = [
        "docs/migration/", "docs/migration/legacy/",
        "state/migrated_changes/", "state/migrated_sessions/",
        "docs/V2_PROPUESTA.md", "ImageStudio/", "tools/dist/",
    ]
    legacy_re = re.compile(
        r"(?:\bV2\.1(?:\.[0-9]+)?\b|\bv2_1\b|\bBAGO[-_\s]+2\.1(?:\.[0-9]+)?\b)",
        re.IGNORECASE,
    )

    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("._") or p.name == ".DS_Store":
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if any(rel.startswith(px) for px in excluded_prefixes):
            continue
        if p.suffix.lower() not in {".md", ".json", ".txt", ".py"}:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        if legacy_re.search(text):
            print("KO")
            print(f"legacy 2.1 reference found outside migration/legacy: {rel}")
            return 1

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
            return 1
        text = p.read_text(encoding="utf-8")
        match = role_family_re.search(text)
        if not match:
            print("KO")
            print(f"role without parseable family: {rel}")
            return 1
        declared = match.group(1).strip()
        if declared != physical_family:
            print("KO")
            print(f"role family mismatch for {rel}: declared={declared} physical={physical_family}")
            return 1

    print("GO pack")
    return 0


_REQUIRED_ZIP_ENTRIES = [
    "bago",
    ".bago/tools/tool_registry.py",
    ".bago/pack.json",
]
_FORBIDDEN_ZIP_PREFIXES = [".bago/dist/", ".bago/state/", ".git/"]
_FORBIDDEN_ZIP_SUFFIXES = ["__pycache__/", ".pyc", ".pyo"]


def validate_contents(zip_path: Path) -> list[str]:
    """Validate a BAGO distributable ZIP. Returns list of errors."""
    errors: list[str] = []
    if not zip_path.exists():
        return [f"File not found: {zip_path}"]
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            root_prefix = None
            if names:
                first = names[0]
                if "/" in first:
                    candidate = first.split("/")[0] + "/"
                    if all(n.startswith(candidate) or n == candidate.rstrip("/") for n in names):
                        root_prefix = candidate
            if root_prefix:
                names = [n[len(root_prefix):] if n.startswith(root_prefix) else n for n in names]
            for name in names:
                for prefix in _FORBIDDEN_ZIP_PREFIXES:
                    if name.startswith(prefix) or "/" + prefix in name:
                        errors.append(f"Forbidden entry: {name}  (matches: {prefix})")
                for suffix in _FORBIDDEN_ZIP_SUFFIXES:
                    if name.endswith(suffix):
                        errors.append(f"Forbidden entry: {name}  (suffix: {suffix})")
            for req in _REQUIRED_ZIP_ENTRIES:
                if req not in names:
                    errors.append(f"Missing required entry: {req}")
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    zf.extractall(tmp)
                except Exception as exc:
                    errors.append(f"Extraction failed: {exc}")
    except zipfile.BadZipFile as exc:
        errors.append(f"Bad zip file: {exc}")
    return errors


def cmd_contents(args: list[str]) -> int:
    if not args:
        print("Usage: validate contents <BAGO_xxx.zip>")
        return 1
    zip_path = Path(args[0])
    print(f"  Validating: {zip_path.name}")
    errors = validate_contents(zip_path)
    if errors:
        print(f"  Pack validation FAILED ({len(errors)} error(s)):")
        for error in errors:
            print(f"     {error}")
        return 1
    print(f"  Pack is clean and valid: {zip_path.name}")
    return 0


def main() -> int:
    from validate import main as validate_main
    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
