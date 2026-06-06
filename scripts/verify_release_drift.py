#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _normalize_version(value: str) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(_read_text(path))


def _first_existing_version(root: Path, rels: tuple[str, ...]) -> str:
    for rel in rels:
        path = root / rel
        if path.is_file():
            if path.suffix.lower() == ".json":
                data = _read_json(path)
                for key in ("current", "version", "release_version", "tag"):
                    value = data.get(key)
                    if value:
                        return _normalize_version(str(value))
            value = _read_text(path).strip()
            if value:
                return _normalize_version(value)
    return ""


def _record(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "ok" if ok else "drift", "detail": detail})


def _contains_version(path: Path, version: str) -> bool:
    text = _read_text(path)
    return version in text or f"v{version}" in text


def _read_version_fallback(root: Path) -> str:
    source = _read_text(root / "bago_core" / "version.py")
    match = re.search(r'return\s+["\']([^"\']+)["\']', source)
    return _normalize_version(match.group(1)) if match else ""


def build_report(root: Path, runtime_dir: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, str]] = []

    release_version = _first_existing_version(root, ("release_version.txt",))
    versions_current = _normalize_version(str(_read_json(root / "versions.json").get("current", "")))
    package_version = _normalize_version(str(_read_json(root / "package.json").get("version", "")))
    fallback_version = _read_version_fallback(root)

    expected = release_version
    _record(checks, "release_version_present", bool(expected), f"release_version={expected or 'missing'}")
    _record(checks, "versions_json_current", versions_current == expected, f"versions.json={versions_current}")
    _record(checks, "package_json_version", package_version == expected, f"package.json={package_version}")
    _record(checks, "version_py_fallback", fallback_version == expected, f"fallback={fallback_version}")

    for rel in ("README.md", "MANUAL.md", "index.html"):
        _record(checks, f"{rel}:version", _contains_version(root / rel, expected), f"expected={expected}")

    tag_file = root / "bago_core" / "tags" / f"v{expected}.json"
    tag_version = _normalize_version(str(_read_json(tag_file).get("version", ""))) if tag_file.is_file() else ""
    _record(checks, "tag_manifest", tag_version == expected, f"{tag_file.relative_to(root)}={tag_version or 'missing'}")

    remote = _read_text(root / "install-remote.ps1")
    _record(checks, "remote_installer_stable_default", "-not $_.prerelease" in remote, "stable release filter")
    _record(checks, "remote_installer_bundle_version_check", "La version del bundle" in remote, "bundle tag/version match")
    _record(checks, "remote_installer_checksum_pair", "Get-PairedBundle" in remote and '".sha256"' in remote, "ZIP + SHA256 pair")

    checklist = _read_text(root / "RELEASE_CHECKLIST.md").lower()
    for token in ("drift", "rollback", "uninstall", "lock", "process health"):
        _record(checks, f"checklist:{token}", token in checklist, token)

    readme = _read_text(root / "README.md")
    claims = _read_text(root / "docs" / "CLAIMS.md")
    mvp = _read_text(root / "docs" / "MVP.md")
    _record(checks, "ui_not_authority", "React UI | Optional surface" in readme and "UI is not system authority" in claims, "UI optional")
    _record(checks, "autonomy_not_stable", "Agents and autopilot | Experimental" in readme and "Agents/autopilot can execute work | Experimental" in claims, "autonomy experimental")
    _record(checks, "rl_shadow_boundary", "shadow/off by default" in readme and "no execution authority" in mvp, "RL shadow/off")

    if runtime_dir is not None:
        runtime_version = _first_existing_version(
            runtime_dir,
            ("release_version.txt", ".bago/release_version.txt", "versions.json"),
        )
        _record(
            checks,
            "runtime_version",
            runtime_version == expected,
            f"{runtime_dir}={runtime_version or 'missing'} expected={expected}",
        )

    return {
        "root": str(root),
        "expected_version": expected,
        "status": "ok" if all(item["status"] == "ok" for item in checks) else "drift",
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify BAGO release/install drift gates.")
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--runtime-dir", default="", help="Optional installed runtime path to compare.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runtime = Path(args.runtime_dir) if args.runtime_dir else None
    report = build_report(Path(args.repo), runtime)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"release-drift:{report['status']} version={report['expected_version']}")
        for check in report["checks"]:
            marker = "OK" if check["status"] == "ok" else "DRIFT"
            print(f"{marker} {check['name']}: {check['detail']}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
