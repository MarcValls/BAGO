#!/usr/bin/env python3
"""Fail closed when any derived product version drifts from release_version.txt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _json_version(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8")).get("version")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing version in {path}")
    return value.strip()


def versions(root: Path) -> dict[str, str]:
    authority = (root / "release_version.txt").read_text(encoding="utf-8").strip()
    if not authority:
        raise ValueError("release_version.txt is empty")
    return {
        "release_version.txt": authority,
        "package.json": _json_version(root / "package.json"),
        "frontend/package.json": _json_version(root / "frontend" / "package.json"),
        "electron-viewer/package.json": _json_version(root / "electron-viewer" / "package.json"),
        "backend/release_version.txt": (root / "backend" / "release_version.txt").read_text(encoding="utf-8").strip(),
        "frontend/public/ui_config.json": _json_version(root / "frontend" / "public" / "ui_config.json"),
    }


def validate(root: Path, *, tag: str = "", is_tag: bool = False) -> None:
    resolved = versions(root)
    authority = resolved["release_version.txt"]
    drift = {path: value for path, value in resolved.items() if value != authority}
    if drift:
        detail = ", ".join(f"{path}={value!r}" for path, value in drift.items())
        raise ValueError(f"Version drift against release_version.txt={authority!r}: {detail}")
    if is_tag and tag != f"v{authority}":
        raise ValueError(f"Tag {tag!r} does not match release_version.txt={authority!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag", default="")
    parser.add_argument("--is-tag", choices=("true", "false"), default="false")
    args = parser.parse_args()
    try:
        validate(args.root.resolve(), tag=args.tag, is_tag=args.is_tag == "true")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"Version consistency PASS: {versions(args.root.resolve())['release_version.txt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
