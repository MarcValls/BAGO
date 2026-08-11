from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def rebuild_manifest(package_root: Path) -> None:
    manifest_path = package_root / "bago.package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = []
    for path in sorted(item for item in package_root.rglob("*") if item.is_file() and item != manifest_path):
        content = path.read_bytes()
        files.append({
            "path": path.relative_to(package_root).as_posix(),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    manifest["files"] = files
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    for root in sorted(path for path in ROOT.iterdir() if path.is_dir() and (path / "bago.package.json").is_file()):
        rebuild_manifest(root)
        print(root.name)
