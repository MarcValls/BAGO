"""
bump_version.py — bump BAGO version across all version-relevant files.

Parametrizable replacement of Program Files\\BAGO\\bump_to_4_8_0.py.

Usage:
    python bump_version.py --to 4.8.0 --root . --include-package-json --dry-run
    python bump_version.py --to 4.8.0 --root 'D:\\other\\BAGO' --include-package-json

Touches (in order):
    1. release_version.txt          → VERSION
    2. pyproject.toml               → version = "VERSION"  (project table)
    3. versions.json                → "current": "VERSION"  (history untouched)
    4. CHANGELOG.md                 → inserts ## [VERSION] - <today> entry at top
    5. BAGO.pyproj                  → BAGO vVERSION
    6. bago.egg-info/PKG-INFO       → Version: VERSION  + # BAGO vVERSION
    7. package.json (optional)      → "version": "VERSION"   (only if --include-package-json)

Safe substitutions only: never touches ui-react dist bundles, audit bundles,
node_modules, or build artifacts. The script never deletes — it only
overwrites specific lines and prepends to CHANGELOG.md. Rollback is:
    - Re-run with the previous version, OR
    - Restore from .gabo/backups/<stamp>/ (do that manually).
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def log(msg: str, dry: bool):
    prefix = "[DRY-RUN] " if dry else ""
    print(f"{prefix}{msg}", flush=True)


def update_release_version(root: Path, version: str, dry: bool) -> bool:
    p = root / "release_version.txt"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    if dry:
        log(f"  would update: {p}  ->  '{version}\\n'", dry)
        return True
    p.write_text(f"{version}\n", encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def update_pyproject(root: Path, version: str, dry: bool) -> bool:
    p = root / "pyproject.toml"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    text = p.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r'^version\s*=\s*"[\d.]+"',
        f'version = "{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n == 0:
        log(f"  no-op (no version line): {p}", dry)
        return False
    if dry:
        log(f"  would update: {p}  ({n} replacement)", dry)
        return True
    p.write_text(new_text, encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def update_versions_json(root: Path, version: str, dry: bool) -> bool:
    p = root / "versions.json"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    text = p.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r'"current"\s*:\s*"[\d.]+"',
        f'"current": "{version}"',
        text,
        count=1,
    )
    if n == 0:
        log(f"  no-op (no current key): {p}", dry)
        return False
    if dry:
        log(f"  would update: {p}  ({n} replacement)", dry)
        return True
    p.write_text(new_text, encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def update_changelog(root: Path, version: str, dry: bool) -> bool:
    p = root / "CHANGELOG.md"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    text = p.read_text(encoding="utf-8")
    header = f"## [{version}] - {today_iso()}\n\n### Bumped by bump_version.py\n\n"
    if text.startswith("# Changelog\n\n"):
        new_text = text.replace("# Changelog\n\n", "# Changelog\n\n" + header, 1)
    else:
        new_text = header + text
    if dry:
        log(f"  would prepend to: {p}  (header {len(header)} chars)", dry)
        return True
    p.write_text(new_text, encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def update_pyproj(root: Path, version: str, dry: bool) -> bool:
    p = root / "BAGO.pyproj"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    text = p.read_text(encoding="utf-8")
    new_text, n = re.subn(r'BAGO v[\d.]+', f'BAGO v{version}', text, count=1)
    if n == 0:
        log(f"  no-op (no BAGO v line): {p}", dry)
        return False
    if dry:
        log(f"  would update: {p}  ({n} replacement)", dry)
        return True
    p.write_text(new_text, encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def update_egg_info(root: Path, version: str, dry: bool) -> bool:
    p = root / "bago.egg-info" / "PKG-INFO"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    text = p.read_text(encoding="utf-8")
    new_text, n1 = re.subn(r'^Version:\s*[\d.]+', f'Version: {version}', text, count=1, flags=re.MULTILINE)
    new_text, n2 = re.subn(r'^#\s*BAGO v[\d.]+', f'# BAGO v{version}', new_text, count=1, flags=re.MULTILINE)
    if (n1 + n2) == 0:
        log(f"  no-op (no Version/BAGO v line): {p}", dry)
        return False
    if dry:
        log(f"  would update: {p}  ({n1} Version, {n2} BAGO v)", dry)
        return True
    p.write_text(new_text, encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def update_package_json(root: Path, version: str, dry: bool) -> bool:
    p = root / "package.json"
    if not p.exists():
        log(f"  skip (not found): {p}", dry)
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log(f"  error (invalid JSON): {p}  ({e})", dry)
        return False
    if data.get("version") == version:
        log(f"  no-op (already {version}): {p}", dry)
        return True
    if dry:
        log(f"  would update: {p}  ->  version='{version}'", dry)
        return True
    data["version"] = version
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  updated: {p}", dry)
    return True


def main():
    ap = argparse.ArgumentParser(description="Bump BAGO version across files.")
    ap.add_argument("--to", required=True, help="Target version (e.g. 4.8.0)")
    ap.add_argument("--root", default=".", help="Repo root (default: cwd)")
    ap.add_argument("--include-package-json", action="store_true",
                    help="Also bump package.json (NOT touched by the original bump_to_4_8_0.py)")
    ap.add_argument("--dry-run", action="store_true", help="Preview only, do not write")
    args = ap.parse_args()

    version = args.to.strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(f"error: --to must be X.Y.Z, got {version!r}", file=sys.stderr)
        sys.exit(2)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: --root is not a directory: {root}", file=sys.stderr)
        sys.exit(2)

    dry = args.dry_run
    print(f"bump_version.py  to={version}  root={root}  dry={dry}  pkg_json={args.include_package_json}")
    print(f"timestamp: {now_iso()}")

    touched = 0
    touched += update_release_version(root, version, dry)
    touched += update_pyproject(root, version, dry)
    touched += update_versions_json(root, version, dry)
    touched += update_changelog(root, version, dry)
    touched += update_pyproj(root, version, dry)
    touched += update_egg_info(root, version, dry)
    if args.include_package_json:
        touched += update_package_json(root, version, dry)

    print(f"\nDone. Files touched: {touched}")
    if dry:
        print("(dry-run — no changes written)")
    else:
        print(f"BAGO bumped to {version}.")


if __name__ == "__main__":
    main()