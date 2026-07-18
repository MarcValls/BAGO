from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", ".bago", ".gabo", "node_modules", "dist", "build", "coverage", ".venv", "__pycache__"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"


def _seed_dir(root: Path) -> Path:
    return root.resolve() / ".gabo"


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg",
        ".html", ".css", ".scss", ".sh", ".ps1", ".bat", ".cjs", ".mjs", ".jsonl", ".xml",
    }


def _scan_tree(root: Path, depth: int) -> list[dict[str, Any]]:
    root = root.resolve()
    items: list[dict[str, Any]] = []
    max_depth = max(0, int(depth))
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        rel = current_path.relative_to(root)
        level = 0 if not rel.parts else len(rel.parts)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and level < max_depth]
        if rel.parts:
            items.append({
                "path": rel.as_posix(),
                "kind": "directory",
                "depth": level,
            })
        if level > max_depth:
            continue
        for name in files:
            if name in SKIP_DIRS:
                continue
            file_path = current_path / name
            try:
                stat = file_path.stat()
            except OSError:
                continue
            rel_file = file_path.relative_to(root).as_posix()
            checksum = ""
            if _is_text_file(file_path):
                try:
                    checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
                except OSError:
                    checksum = ""
            items.append({
                "path": rel_file,
                "kind": "file",
                "depth": level + 1,
                "size": int(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "sha256": checksum,
                "text": _is_text_file(file_path),
            })
    items.sort(key=lambda item: item["path"])
    return items


def write_tree(root: Path, depth: int) -> dict[str, Any]:
    root = Path(root).resolve()
    seed_dir = _seed_dir(root)
    seed_dir.mkdir(parents=True, exist_ok=True)
    tree = {
        "schema": "bago.seed.tree.v1",
        "root": str(root),
        "depth": int(depth),
        "count": 0,
        "items": _scan_tree(root, depth),
        "generated_at": _now_iso(),
    }
    tree["count"] = len(tree["items"])
    (seed_dir / "tree.json").write_text(_json_text(tree), encoding="utf-8")
    return tree


def write_live(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    seed_dir = _seed_dir(root)
    seed_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "bago.seed.live.v1",
        "root": str(root),
        "workspace": root.name,
        "state": "seeded",
        "linked": False,
        "generated_at": _now_iso(),
    }
    (seed_dir / "live.json").write_text(_json_text(payload), encoding="utf-8")
    return payload


def discover_api_canon(ref_root: Path | None) -> dict[str, Any]:
    ref_root = Path(ref_root).resolve() if ref_root else None
    if ref_root is not None:
        resolver = ref_root / "docs" / "contracts" / "resolver_contract.json"
        if resolver.is_file():
            try:
                return json.loads(resolver.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    return {
        "schema": "bago.seed.api_canon.v1",
        "workspace_root": str(ref_root) if ref_root else "",
        "framework_root": str(ref_root) if ref_root else "",
        "project_root": str(ref_root) if ref_root else "",
        "canonical_roots": [],
        "generated_at": _now_iso(),
    }


def _write_manifest(root: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    seed_dir = _seed_dir(root)
    out_dir = seed_dir / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.json"
    target.write_text(_json_text(payload), encoding="utf-8")
    return payload


def write_manifest_api(root: Path, canon: dict[str, Any]) -> dict[str, Any]:
    return _write_manifest(Path(root), "api", {
        "schema": "bago.seed.manifest.api.v1",
        "root": str(Path(root).resolve()),
        "canon": canon,
        "generated_at": _now_iso(),
    })


def write_manifest_tools_sprints(root: Path) -> dict[str, Any]:
    return _write_manifest(Path(root), "tools_sprints", {
        "schema": "bago.seed.manifest.tools_sprints.v1",
        "root": str(Path(root).resolve()),
        "sprints": [],
        "generated_at": _now_iso(),
    })


def write_manifest_recursive(root: Path, area: str, rel: str) -> dict[str, Any]:
    target = Path(root).resolve() / rel
    files = []
    if target.exists():
        for item in target.rglob("*"):
            if item.is_file():
                try:
                    stat = item.stat()
                except OSError:
                    continue
                files.append({
                    "path": item.relative_to(Path(root).resolve()).as_posix(),
                    "size": int(stat.st_size),
                    "text": _is_text_file(item),
                })
    payload = {
        "schema": "bago.seed.manifest.recursive.v1",
        "area": area,
        "root": str(Path(root).resolve()),
        "relative_path": rel,
        "count": len(files),
        "files": files,
        "generated_at": _now_iso(),
    }
    return _write_manifest(Path(root), area, payload)


def write_manifest_dir(root: Path, area: str, rel: str) -> dict[str, Any]:
    target = Path(root).resolve() / rel
    entries = []
    if target.exists():
        for item in target.iterdir():
            entries.append({
                "name": item.name,
                "kind": "directory" if item.is_dir() else "file",
            })
    payload = {
        "schema": "bago.seed.manifest.dir.v1",
        "area": area,
        "root": str(Path(root).resolve()),
        "relative_path": rel,
        "count": len(entries),
        "entries": entries,
        "generated_at": _now_iso(),
    }
    return _write_manifest(Path(root), area, payload)


def write_diff(root: Path, ref: Path | None) -> dict[str, Any]:
    root = Path(root).resolve()
    ref_root = Path(ref).resolve() if ref else None
    payload = {
        "schema": "bago.seed.diff.v1",
        "root": str(root),
        "reference_root": str(ref_root) if ref_root else "",
        "summary": "no reference" if ref_root is None else "reference captured",
        "generated_at": _now_iso(),
    }
    diff_dir = _seed_dir(root) / "diffs"
    diff_dir.mkdir(parents=True, exist_ok=True)
    (diff_dir / "workspace.diff.json").write_text(_json_text(payload), encoding="utf-8")
    return payload


def write_index(root: Path, manifests: dict[str, dict[str, Any]], live: dict[str, Any], diff_payload: dict[str, Any] | None, depth: int) -> None:
    root = Path(root).resolve()
    seed_dir = _seed_dir(root)
    lines = [
        f"# Workspace seed for {root.name}",
        "",
        f"- Root: `{root}`",
        f"- Depth: `{depth}`",
        f"- Live state: `{live.get('state', 'unknown')}`",
        f"- Linked: `{live.get('linked', False)}`",
        "",
        "## Manifests",
    ]
    for name, payload in sorted(manifests.items()):
        lines.append(f"- {name}: {payload.get('count', payload.get('root', 'ok'))}")
    if diff_payload:
        lines.extend(["", "## Diff", f"- {diff_payload.get('summary', 'ok')}"])
    lines.extend(["", f"Generated at: {_now_iso()}"])
    (seed_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
