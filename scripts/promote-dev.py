#!/usr/bin/env python3
"""
promote-dev.py — Promote .bago/dev/ into .bago/launch/ and .bago/versions/X.Y.Z/.

Uso:
    python scripts\\promote-dev.py --version X.Y.Z
    python scripts\\promote-dev.py --version X.Y.Z --note "RL engine bump"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import sys
from pathlib import Path


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _user_bago_root() -> Path:
    return Path.home() / ".bago"


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _checksums(root: Path, out: Path) -> None:
    out.write_text("", encoding="utf-8")
    lines: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            lines.append(f"{_sha256(p)}  {rel}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-bago", default=None, help="Path to .bago (default: ~/.bago)")
    parser.add_argument("--version", required=True, help="Target version (e.g. X.Y.Z)")
    parser.add_argument("--note", default="", help="Release note")
    args = parser.parse_args(argv)
    user_bago = Path(args.user_bago or str(_user_bago_root()))
    dev = user_bago / "dev"
    launch = user_bago / "launch"
    versions = user_bago / "versions" / args.version
    if not dev.exists():
        print(f"missing source: {dev}")
        return 1
    _copytree(dev, launch)
    _copytree(dev, versions)
    _checksums(launch, launch / "checksums.sha256")
    release = {
        "version": args.version,
        "promoted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": str(dev),
        "target_launch": str(launch),
        "target_versions": str(versions),
        "note": args.note,
        "checksums": str(launch / "checksums.sha256"),
    }
    (launch / "release.json").write_text(
        json.dumps(release, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"promoted {dev} -> {launch} and {versions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
