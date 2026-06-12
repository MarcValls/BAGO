#!/usr/bin/env python3
"""
seal_release.py - create a versioned release seal for a packaged BAGO bundle.

This helper follows the same chained-sha256 convention already used by the
historical release seal scripts, but parameterizes the version and bundle path
for the current release line.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_version() -> str:
    value = (_repo_root() / "release_version.txt").read_text(encoding="utf-8").strip()
    return value.lstrip("v")


def _default_bundle(version: str) -> Path:
    return _repo_root() / "release" / "v4" / f"bago-v{version}.zip"


def _default_checksums(bundle: Path) -> Path:
    return bundle.with_suffix(bundle.suffix + ".sha256")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=_default_version())
    parser.add_argument("--bundle", default="", help="Path to the release zip bundle")
    parser.add_argument("--checksums", default="", help="Path to the bundle sha256 file")
    parser.add_argument("--output-dir", default="", help="Directory to write release.json and release.sig")
    parser.add_argument("--tag-output", default="", help="Optional tag manifest output path")
    return parser


def _release_payload(version: str, bundle: Path, bundle_sha: str, checksums: Path, checksums_sha: str) -> dict:
    return {
        "bundle_id": f"bago.v{version}",
        "version": version,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "bundle": str(bundle),
        "bundle_sha256": bundle_sha,
        "checksums": str(checksums),
        "checksums_sha256": checksums_sha,
        "release_notes": str(_repo_root() / "docs" / f"RELEASE_NOTES_{version}.md"),
        "policy": str(_repo_root() / "docs" / "PUBLIC_RELEASE_POLICY.md"),
    }


def _chained_signature(release: dict, checksums_text: str) -> dict:
    release_body = json.dumps(release, sort_keys=True, ensure_ascii=False).encode("utf-8")
    release_sha = _sha256_bytes(release_body)
    checksums_sha = _sha256_bytes(checksums_text.encode("utf-8"))
    seal_sha = _sha256_bytes((release_sha + checksums_sha).encode("ascii"))
    return {
        "algorithm": "chained-sha256",
        "signed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "release_sha256": release_sha,
        "checksums_sha256": checksums_sha,
        "seal_sha256": seal_sha,
    }


def _tag_manifest(version: str, release: dict, signature: dict) -> dict:
    return {
        "tag": f"v{version}",
        "version": version,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "release": release,
        "signature": signature,
    }


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        bundle = root / "bago-v4.5.0.zip"
        bundle.write_bytes(b"bundle")
        checksums = root / "bago-v4.5.0.zip.sha256"
        checksums.write_text("abc  bago-v4.5.0.zip\n", encoding="utf-8")
        out_dir = root / "seal"
        out_dir.mkdir()
        version = "4.5.0"
        release = _release_payload(version, bundle, _sha256_file(bundle), checksums, _sha256_file(checksums))
        signature = _chained_signature(release, checksums.read_text(encoding="utf-8"))
        tag = _tag_manifest(version, release, signature)
        (out_dir / "release.json").write_text(json.dumps(release, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "release.sig").write_text(json.dumps(signature, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "v4.5.0.json").write_text(json.dumps(tag, indent=2, ensure_ascii=False), encoding="utf-8")
        assert (out_dir / "release.json").exists()
        assert (out_dir / "release.sig").exists()
        assert (out_dir / "v4.5.0.json").exists()
    print("seal_release.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    version = args.version.lstrip("v")
    bundle = Path(args.bundle) if args.bundle else _default_bundle(version)
    checksums = Path(args.checksums) if args.checksums else _default_checksums(bundle)
    out_dir = Path(args.output_dir) if args.output_dir else bundle.parent / "seal"
    tag_output = Path(args.tag_output) if args.tag_output else out_dir / f"v{version}.json"

    if not bundle.exists():
        print(f"missing bundle: {bundle}", file=sys.stderr)
        return 1
    if not checksums.exists():
        print(f"missing checksums: {checksums}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    release = _release_payload(version, bundle, _sha256_file(bundle), checksums, _sha256_file(checksums))
    signature = _chained_signature(release, checksums.read_text(encoding="utf-8"))
    tag = _tag_manifest(version, release, signature)

    (out_dir / "release.json").write_text(json.dumps(release, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "release.sig").write_text(json.dumps(signature, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tag_output.parent.mkdir(parents=True, exist_ok=True)
    tag_output.write_text(json.dumps(tag, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"release_sha256: {signature['release_sha256']}")
    print(f"checksums_sha256: {signature['checksums_sha256']}")
    print(f"seal_sha256: {signature['seal_sha256']}")
    print(f"wrote: {out_dir / 'release.json'}")
    print(f"wrote: {out_dir / 'release.sig'}")
    print(f"wrote: {tag_output}")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(main())
