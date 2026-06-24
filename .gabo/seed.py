"""
.gabo/ seeder for BAG4.8 — all paths are ROOT-RELATIVE.

The seed is portable across drive letters and OSes: every path written to
JSON or Markdown is relative to the workspace root. Absolute paths live ONLY
in `live.json` (where we resolve the launcher and the install_selection) and
ONLY as informational metadata — never as a key an agent has to read.

Usage:
    python seed.py                       # cwd is the root; depth=3
    python seed.py --depth 5             # deeper scan (max 8)
    python seed.py --root 'D:\\repos\\BAG4.8'
    python seed.py --depth 3 --ref 'D:\\releases\\BAGO'   # also write diff

Outputs (under <root>/.gabo/):
    tree.json                root-relative file tree (sorted, excludes caches)
    live.json                absolute paths only in *_abs fields (informational)
    manifests/<area>.json    root-relative paths only
    diffs/vs_<ref>.json      root-relative
    index.md                 root-relative

Excludes: __pycache__, node_modules, .pytest_cache, .git, *.pyc, electron_run.log
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


EXCLUDE_DIRS = {"__pycache__", "node_modules", ".pytest_cache", ".git", "node_modules_cache"}
EXCLUDE_FILES = {"electron_run.log"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def detect_root(arg_root: str | None) -> Path:
    if arg_root:
        return Path(arg_root).resolve()
    env = os.environ.get("SEED_DIR")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def collect_files(root: Path, depth: int):
    rows = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        rel_parts = p.relative_to(root).parts
        if any(seg in EXCLUDE_DIRS for seg in rel_parts):
            continue
        if p.name in EXCLUDE_FILES or p.suffix == ".pyc":
            continue
        if len(rel_parts) > depth:
            continue
        try:
            st = p.stat()
            rows.append({
                "path": "/".join(rel_parts),  # ROOT-RELATIVE
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
        except OSError:
            continue
    rows.sort(key=lambda r: r["path"])
    return rows


def write_tree(root: Path, depth: int):
    files = collect_files(root, depth)
    payload = {
        "workspace_root_rel": ".",
        "depth": depth,
        "max_depth_supported": 8,
        "paths_are": "root-relative",
        "exclude_dirs": sorted(EXCLUDE_DIRS),
        "exclude_files": sorted(EXCLUDE_FILES),
        "count": len(files),
        "files": files,
    }
    (root / ".gabo" / "tree.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_live(root: Path):
    """Absolute paths live ONLY in *_abs fields, marked informational."""
    sel_path = Path.home() / ".bago" / "install_selection.json"
    active_short = ""
    if sel_path.exists():
        sel = json.loads(sel_path.read_text(encoding="utf-8"))
        active_short = sel["roles"]["active"]["path"]

    active_resolved = ""
    if active_short:
        try:
            active_resolved = str(Path(active_short).resolve())
        except OSError:
            active_resolved = active_short

    is_active = bool(active_resolved) and active_resolved.lower() == str(root).lower()

    version_path = root / "release_version.txt"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "unknown"

    payload = {
        "command": "bago",
        "workspace_root_rel": ".",
        "paths_are": "root-relative except *_abs (informational only)",
        "version": version,
        "captured_at": now_iso(),
        "launcher_abs": str(Path.home() / "AppData" / "Local" / "BAGO" / "bago.ps1"),
        "install_selection_active_abs": active_short,
        "install_selection_active_resolved_abs": active_resolved,
        "workspace_matches_active": is_active,
        "note_on_short_form": "active_abs uses short form (AMTEC_~1) to avoid PowerShell 5.1 ANSI bug on 'º'",
    }
    (root / ".gabo" / "live.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


EXPECTED_HANDLERS = [
    "handlers_chat", "handlers_command", "handlers_switch", "handlers_status",
    "handlers_router", "handlers_providers", "handlers_models", "handlers_files",
    "handlers_history", "handlers_memory", "handlers_menu", "handlers_subagents",
    "handlers_rl", "handlers_schedule", "handlers_simulation", "handlers_session",
    "handlers_catalog",
]
API_SUPPORT = ["api_auth", "api_dispatch", "api_serializers", "request_context", "bridge", "__init__"]


def discover_api_canon(ref_path: Path | None) -> list[str]:
    """Discover the canonical api modules by reading --ref's .bago/api directory.

    Falls back to EXPECTED_HANDLERS + API_SUPPORT if ref is missing.
    This makes the seeder robust: the canon follows the upstream copy the
    user points at, not a hardcoded list. If upstream grows or shrinks,
    the seed reflects it on the next run.
    """
    fallback = sorted(set(EXPECTED_HANDLERS + API_SUPPORT))
    if ref_path is None:
        return fallback
    api_dir = ref_path / ".bago" / "api"
    if not api_dir.is_dir():
        return fallback
    return sorted(p.stem for p in api_dir.glob("*.py"))


def write_manifest_api(root: Path, canon: list[str]):
    api_rel = Path(".bago/api")
    api = root / api_rel
    if not api.exists():
        return {"area": "api", "root_rel": api_rel.as_posix(), "exists": False,
                "broken": True, "missing": canon, "canon_source": "missing workspace"}
    observed = sorted({p.stem for p in api.glob("*.py")})
    missing = [name for name in canon if name not in observed]
    extra = [name for name in observed if name not in canon]
    payload = {
        "area": "api",
        "root_rel": api_rel.as_posix(),
        "paths_are": "root-relative",
        "canon_count": len(canon),
        "observed_count": len(observed),
        "canon": canon,
        "observed": observed,
        "missing": missing,
        "extra": extra,
        "broken": bool(missing),
        "note": "broken=true means a canon module is missing in workspace. extra=observed modules not in canon (e.g. local extractions like bridge_handler).",
    }
    (root / ".gabo" / "manifests" / "api.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_manifest_dir(root: Path, area: str, rel: str, file_glob: str = "*"):
    d_rel = Path(rel)
    d = root / d_rel
    if not d.exists():
        payload = {"area": area, "root_rel": d_rel.as_posix(), "paths_are": "root-relative",
                   "exists": False, "broken": True, "files": []}
    else:
        files = sorted(p.relative_to(d).as_posix() for p in d.glob(file_glob) if p.is_file())
        payload = {
            "area": area,
            "root_rel": d_rel.as_posix(),
            "paths_are": "root-relative",
            "exists": True,
            "broken": False,
            "file_count": len(files),
            "files": files,
        }
    (root / ".gabo" / "manifests" / f"{area}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_manifest_recursive(root: Path, area: str, rel: str):
    d_rel = Path(rel)
    d = root / d_rel
    if not d.exists():
        payload = {"area": area, "root_rel": d_rel.as_posix(), "paths_are": "root-relative",
                   "exists": False, "broken": True, "tree": {}}
        (root / ".gabo" / "manifests" / f"{area}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return payload
    tree = {}
    for p in sorted(d.rglob("*")):
        if p.is_dir():
            continue
        if any(seg in EXCLUDE_DIRS for seg in p.relative_to(d).parts):
            continue
        if p.suffix == ".pyc" or p.name in EXCLUDE_FILES:
            continue
        rel_p = p.relative_to(d).as_posix()
        tree[rel_p] = p.stat().st_size
    payload = {
        "area": area,
        "root_rel": d_rel.as_posix(),
        "paths_are": "root-relative",
        "exists": True,
        "broken": False,
        "file_count": len(tree),
        "tree": tree,
    }
    (root / ".gabo" / "manifests" / f"{area}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_manifest_tools_sprints(root: Path):
    """Index tools/sprints/ by subdir — used for grouped orphan scripts."""
    d_rel = Path("tools/sprints")
    d = root / d_rel
    if not d.exists():
        payload = {"area": "tools_sprints", "root_rel": d_rel.as_posix(),
                   "paths_are": "root-relative", "exists": False, "broken": True, "groups": {}}
        (root / ".gabo" / "manifests" / "tools_sprints.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return payload
    groups = {}
    total = 0
    for sub in sorted(d.iterdir()):
        if not sub.is_dir():
            continue
        files = sorted(p.name for p in sub.iterdir() if p.is_file())
        groups[sub.name] = {
            "file_count": len(files),
            "files": files,
        }
        total += len(files)
    payload = {
        "area": "tools_sprints",
        "root_rel": d_rel.as_posix(),
        "paths_are": "root-relative",
        "exists": True,
        "broken": False,
        "group_count": len(groups),
        "file_count": total,
        "groups": groups,
    }
    (root / ".gabo" / "manifests" / "tools_sprints.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_diff(root: Path, ref_path: Path):
    if not ref_path.exists():
        return None
    ref_files = set()
    for p in ref_path.rglob("*"):
        if p.is_dir():
            continue
        if any(seg in EXCLUDE_DIRS for seg in p.relative_to(ref_path).parts):
            continue
        if p.suffix == ".pyc" or p.name in EXCLUDE_FILES:
            continue
        ref_files.add(p.relative_to(ref_path).as_posix())

    dst_files = set()
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(seg in EXCLUDE_DIRS for seg in p.relative_to(root).parts):
            continue
        if p.suffix == ".pyc" or p.name in EXCLUDE_FILES:
            continue
        dst_files.add(p.relative_to(root).as_posix())

    missing = sorted(ref_files - dst_files)
    by_top = defaultdict(int)
    for m in missing:
        by_top[m.split("/")[0]] += 1

    safe_name = ref_path.name.replace(" ", "_").replace("\\", "_").replace(":", "")
    payload = {
        "ref_abs": str(ref_path),
        "ref_basename": ref_path.name,
        "dst_rel": ".",
        "dst_abs": str(root),
        "paths_are": "root-relative",
        "missing_count": len(missing),
        "by_top_dir": dict(sorted(by_top.items(), key=lambda kv: -kv[1])),
        "missing": missing,
        "captured_at": now_iso(),
    }
    (root / ".gabo" / "diffs" / f"vs_{safe_name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_index(root: Path, manifests: dict, live: dict, diff_payload, depth: int):
    lines = []
    lines.append("# BAG4.8 — context seed (`.gabo/`)")
    lines.append("")
    lines.append(f"- **Captured**: {now_iso()}")
    lines.append(f"- **Workspace root**: `.` (all paths below are relative to the workspace root)")
    lines.append(f"- **Tree depth**: {depth} (max supported: 8 — re-seed with `python .gabo/seed.py --depth N`)")
    lines.append(f"- **Version**: **{live['version']}**")
    lines.append(f"- **Workspace matches active install**: **{'YES' if live['workspace_matches_active'] else 'NO'}**")
    lines.append("")
    lines.append("## Manifests")
    lines.append("")
    lines.append("| area | path (root-relative) | broken | files |")
    lines.append("|---|---|---|---|")
    for area, m in manifests.items():
        if not m:
            continue
        if m.get("exists") is False:
            lines.append(f"| {area} | `{m.get('root_rel', '?')}` | ⚠️ missing dir | – |")
        else:
            broken = "⚠️ **YES**" if m.get("broken") else "no"
            if "group_count" in m:
                count = f"{m.get('file_count', '–')} ({m.get('group_count', '–')} groups)"
            else:
                count = m.get("file_count", m.get("present_count", "–"))
            lines.append(f"| {area} | `{m.get('root_rel', '?')}` | {broken} | {count} |")
    lines.append("")
    if diff_payload:
        lines.append("## Diff vs reference")
        lines.append("")
        lines.append(f"- ref basename: **{diff_payload['ref_basename']}**")
        lines.append(f"- missing files (root-relative paths): **{diff_payload['missing_count']}**")
        lines.append("")
        lines.append("Top missing top-level dirs:")
        lines.append("")
        lines.append("| top dir | missing count |")
        lines.append("|---|---|")
        for d, c in list(diff_payload["by_top_dir"].items())[:10]:
            lines.append(f"| `{d}` | {c} |")
        lines.append("")
    lines.append("## Next step")
    lines.append("")
    api_m = manifests.get("api", {})
    if api_m and api_m.get("broken"):
        lines.append("- **`.bago/api/` is BROKEN** — see `manifests/api.json`.")
        lines.append("- Re-seed afterwards: `python .gabo/seed.py --depth 3 --ref '<path-to-good-copy>'`")
    else:
        lines.append("- Bridge looks intact. Continue with the task at hand.")
    lines.append("")
    lines.append("## How to re-seed deeper")
    lines.append("")
    lines.append("```")
    lines.append("python .gabo/seed.py --depth 5")
    lines.append("python .gabo/seed.py --depth 8 --root 'D:\\other\\BAG4.8'")
    lines.append("```")
    lines.append("")
    (root / ".gabo" / "index.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--root", type=str, default=None)
    p.add_argument("--ref", type=str, default=r"C:\Program Files\BAGO")
    args = p.parse_args()
    depth = max(1, min(args.depth, 8))
    root = detect_root(args.root)

    seed_dir = root / ".gabo"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "manifests").mkdir(parents=True, exist_ok=True)
    (seed_dir / "diffs").mkdir(parents=True, exist_ok=True)

    print(f"[seed] depth={depth} root={root}")
    tree = write_tree(root, depth)
    print(f"[seed] tree.json: {tree['count']} files")

    live = write_live(root)
    print(f"[seed] live.json: v={live['version']} matches={live['workspace_matches_active']}")

    manifests = {}
    canon = discover_api_canon(Path(args.ref) if args.ref else None)
    manifests["api"] = write_manifest_api(root, canon)
    print(f"[seed] api.json: canon={manifests['api']['canon_count']} observed={manifests['api']['observed_count']} broken={manifests['api']['broken']} extra={len(manifests['api'].get('extra', []))}")
    manifests["tools_sprints"] = write_manifest_tools_sprints(root)
    if manifests["tools_sprints"].get("exists"):
        print(f"[seed] tools_sprints.json: {manifests['tools_sprints']['file_count']} files in {manifests['tools_sprints']['group_count']} groups")
    for area, rel in [
        ("bago_core", "bago_core"),
        ("ui_react", "ui-react"),
        ("agents", ".bago/agents"),
        ("tools", ".bago/tools"),
        ("providers", ".bago/providers"),
        ("roles", ".bago/roles"),
        ("workflows", ".bago/workflows"),
        ("knowledge", ".bago/knowledge"),
        ("prompts", ".bago/prompts"),
        ("mcp", ".bago/mcp"),
        ("chat", ".bago/chat"),
        ("extensions", ".bago/extensions"),
        ("templates", ".bago/templates"),
        ("core", ".bago/core"),
        ("state_example", ".bago/state.example"),
    ]:
        if area in ("bago_core", "ui_react"):
            manifests[area] = write_manifest_recursive(root, area, rel)
        else:
            manifests[area] = write_manifest_dir(root, area, rel)
        print(f"[seed] {area}.json: files={manifests[area].get('file_count', manifests[area].get('present_count', '?'))}")

    diff_payload = write_diff(root, Path(args.ref))
    if diff_payload:
        print(f"[seed] diff/vs_*.json: missing={diff_payload['missing_count']}")

    write_index(root, manifests, live, diff_payload, depth)
    print(f"[seed] index.md written")


if __name__ == "__main__":
    main()