#!/usr/bin/env python3
"""Portable BAGO project memory manager.

Usage:
    python .bago/tools/project_memory.py init [--root DIR]
    python .bago/tools/project_memory.py status [--root DIR]
    python .bago/tools/project_memory.py link [--root DIR]
    python .bago/tools/project_memory.py --test
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
core_dir = Path(__file__).resolve().parents[1] / "core"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
from bago_utils import get_scan_root
from directory_context import DirectoryContextEngine
from workspace_binding import resolve_framework_root, resolve_workspace_binding

KNOWLEDGE_SUBDIRS = ("topics", "examples", "schemas", "assets")
STATE_SUBDIRS = ("sessions",)
TEST_WORKSPACE = Path(__file__).parent / "_selftest_project_memory"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def find_project_root(start: Path | None = None) -> Path | None:
    """Find a likely project root only when the supplied directory is marked."""
    candidate = Path(start or Path.cwd()).resolve()
    if (candidate / ".gabo").exists():
        return candidate
    if (candidate / ".bago" / "pack.json").exists():
        return candidate
    return None


def resolve_project_root(root: str | Path | None = None, *, allow_fallback_cwd: bool = False) -> Path | None:
    """Resolve the project root for project operations.

    Explicit paths win. Otherwise we try to infer a real project from the
    current location. If no marker exists, return ``None`` unless fallback to
    cwd was explicitly requested.
    """
    if root is not None and str(root).strip():
        return Path(root).expanduser().resolve()
    detected = find_project_root()
    if detected is not None:
        return detected
    if allow_fallback_cwd:
        return Path.cwd().resolve()
    return None


def _write_text_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _write_json_if_missing(path: Path, data: dict[str, Any] | list[Any]) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return True


def _pack_payload(root: Path) -> dict[str, Any]:
    return {
        "schema": 1,
        "project": root.name,
        "type": "bago-project",
        "root": str(root),
        "initialized_at": _now_iso(),
    }


def _context_payload(root: Path) -> dict[str, Any]:
    return {
        "project": root.name,
        "root": str(root),
        "sessions_count": 0,
        "tasks_count": 0,
        "learnings_count": 0,
        "linked": False,
    }


def _knowledge_manifest(root: Path) -> dict[str, Any]:
    return {
        "schema": 1,
        "project": root.name,
        "purpose": "Portable project knowledge for BAGO-managed projects.",
        "layout": {name: f"knowledge/{name}/" for name in KNOWLEDGE_SUBDIRS},
    }


def _expected_dirs(root: Path) -> list[Path]:
    bago_dir = root / ".bago"
    dirs = [bago_dir, bago_dir / "state", bago_dir / "knowledge"]
    dirs.extend((bago_dir / "state" / name) for name in STATE_SUBDIRS)
    dirs.extend((bago_dir / "knowledge" / name) for name in KNOWLEDGE_SUBDIRS)
    return dirs


def _expected_files(root: Path) -> dict[str, Path]:
    bago_dir = root / ".bago"
    return {
        "pack": bago_dir / "pack.json",
        "context": bago_dir / "state" / "context.json",
        "tasks": bago_dir / "state" / "tasks.json",
        "learnings": bago_dir / "state" / "learnings.md",
        "state_gitignore": bago_dir / "state" / ".gitignore",
        "manifest": bago_dir / "knowledge" / "manifest.json",
        "topics_index": bago_dir / "knowledge" / "topics" / "index.md",
    }


def init_project(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    created_dirs: list[str] = []
    created_files: list[str] = []

    for directory in _expected_dirs(root):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(directory.relative_to(root)))

    files = _expected_files(root)
    if _write_json_if_missing(files["pack"], _pack_payload(root)):
        created_files.append(str(files["pack"].relative_to(root)))
    if _write_json_if_missing(files["context"], _context_payload(root)):
        created_files.append(str(files["context"].relative_to(root)))
    if _write_json_if_missing(files["tasks"], []):
        created_files.append(str(files["tasks"].relative_to(root)))
    if _write_text_if_missing(
        files["learnings"],
        f"# Learnings - {root.name}\n\nAdd project-specific learnings here.\n",
    ):
        created_files.append(str(files["learnings"].relative_to(root)))
    if _write_text_if_missing(
        files["state_gitignore"],
        "sessions/\ncontext.json\ntasks.json\n",
    ):
        created_files.append(str(files["state_gitignore"].relative_to(root)))
    if _write_json_if_missing(files["manifest"], _knowledge_manifest(root)):
        created_files.append(str(files["manifest"].relative_to(root)))
    if _write_text_if_missing(
        files["topics_index"],
        "# Knowledge Index\n\n- project-patterns\n- learned-lessons\n",
    ):
        created_files.append(str(files["topics_index"].relative_to(root)))

    return {
        "root": str(root),
        "created_dirs": sorted(created_dirs),
        "created_files": sorted(created_files),
        "bago_dir": str(root / ".bago"),
    }


def _update_context_link_flag(root: Path, linked: bool) -> None:
    context_path = root / ".bago" / "state" / "context.json"
    data: dict[str, Any] = {}
    context_path.parent.mkdir(parents=True, exist_ok=True)
    if context_path.exists():
        try:
            data = json.loads(context_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not data:
        data = _context_payload(root)
    data["linked"] = linked
    context_path.write_text(_json_text(data), encoding="utf-8")


def link_project(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    init_project(root)
    bago_dir = root / ".bago"
    marker_path = bago_dir / "link.json"
    marker: dict[str, Any] = {
        "schema": 1,
        "project_root": str(root),
        "tools_dir": str(Path(__file__).resolve().parent),
        "linked_at": _now_iso(),
        "mode": "marker",
    }

    bundle_link = bago_dir / "bundle"
    if not bundle_link.exists():
        try:
            bundle_link.symlink_to(Path(__file__).resolve().parent.parent, target_is_directory=True)
            marker["mode"] = "symlink+marker"
            marker["symlink"] = str(bundle_link)
        except Exception:
            marker["mode"] = "marker"
    elif bundle_link.is_symlink():
        marker["mode"] = "symlink+marker"
        marker["symlink"] = str(bundle_link)

    marker_path.write_text(_json_text(marker), encoding="utf-8")
    _update_context_link_flag(root, linked=True)
    return status_data(root)


def status_data(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    bago_dir = root / ".bago"
    files = _expected_files(root)
    link_marker = bago_dir / "link.json"
    bundle_link = bago_dir / "bundle"

    directories = {str(path.relative_to(root)): path.exists() for path in _expected_dirs(root)[1:]}
    file_map = {name: path.exists() for name, path in files.items()}
    linked = link_marker.exists()
    link_mode = "none"
    if linked:
        try:
            link_mode = json.loads(link_marker.read_text(encoding="utf-8")).get("mode", "marker")
        except Exception:
            link_mode = "marker"
    elif bundle_link.is_symlink():
        link_mode = "symlink"

    return {
        "root": str(root),
        "exists": bago_dir.exists(),
        "directories": directories,
        "files": file_map,
        "configured": all(file_map.values()),
        "linked": linked or bundle_link.is_symlink(),
        "link_mode": link_mode,
        "marker": str(link_marker),
        "symlink": str(bundle_link),
    }


def _load_scan_directory_module():
    script = Path(__file__).resolve().parents[2] / "scripts" / "scan_directory.py"
    if not script.exists():
        return None
    spec = importlib.util.spec_from_file_location("bago_scan_directory", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bago_scan_directory"] = module
    spec.loader.exec_module(module)
    return module


def _load_seed_module():
    script = Path(__file__).resolve().parents[2] / ".gabo" / "seed.py"
    if not script.exists():
        return None
    spec = importlib.util.spec_from_file_location("bago_seed", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bago_seed"] = module
    spec.loader.exec_module(module)
    return module


def _detect_stack(root: Path) -> list[str]:
    stack: list[str] = []
    if (root / "package.json").exists() or (root / "package-lock.json").exists():
        stack.append("node")
    if any((root / name).exists() for name in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")):
        stack.append("python")
    if any((root / name).exists() for name in ("electron", "manager", "ui-react")):
        stack.append("electron")
    if any((root / name).exists() for name in ("README.md", "MANUAL.md", "docs")):
        stack.append("docs")
    return stack


def analyze_data(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    data = status_data(root)
    stack = _detect_stack(root)
    suggestions: list[str] = []
    issues: list[str] = []

    if "python" in stack:
        suggestions.append("python -m pytest -q")
        suggestions.append("python -m py_compile bago_core .bago")

    if "node" in stack:
        suggestions.append("npm test")
        suggestions.append("npm run build")

    if "electron" in stack:
        suggestions.append("npm run manager:build-ui")

    if not data["configured"]:
        suggestions.append("bago project init")
        issues.append("La estructura portable .bago no está inicializada del todo.")

    scan_module = _load_scan_directory_module()
    tree = ""
    if scan_module is not None and hasattr(scan_module, "scan_directory"):
        try:
            tree = scan_module.scan_directory(str(root), max_depth=2)
        except Exception as exc:  # noqa: BLE001
            tree = f"Error al escanear el directorio: {exc}"

    return {
        **data,
        "stack": stack,
        "suggestions": suggestions,
        "issues": issues,
        "tree": tree,
    }


def seed_project(root: Path, *, depth: int = 3, ref: str | Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    seed_mod = _load_seed_module()
    if seed_mod is None:
        raise FileNotFoundError("No se pudo cargar .bago/seed.py")

    seed_dir = root / ".gabo"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "manifests").mkdir(parents=True, exist_ok=True)
    (seed_dir / "diffs").mkdir(parents=True, exist_ok=True)

    tree = seed_mod.write_tree(root, depth)
    live = seed_mod.write_live(root)
    ref_path = Path(ref).resolve() if ref else None
    canon = seed_mod.discover_api_canon(ref_path)
    manifests: dict[str, dict[str, Any]] = {}
    manifests["api"] = seed_mod.write_manifest_api(root, canon)
    manifests["tools_sprints"] = seed_mod.write_manifest_tools_sprints(root)
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
        if area in {"bago_core", "ui_react"}:
            manifests[area] = seed_mod.write_manifest_recursive(root, area, rel)
        else:
            manifests[area] = seed_mod.write_manifest_dir(root, area, rel)

    diff_payload = seed_mod.write_diff(root, ref_path) if ref_path is not None else None
    seed_mod.write_index(root, manifests, live, diff_payload, depth)

    binding = resolve_workspace_binding(root)
    workspace_payload = {
        "schema": "bago.workspace.v1",
        "workspace_id": binding.workspace_id,
        "framework_root": resolve_framework_root().as_posix(),
        "project_root": str(root),
        "workspace_state_root": str(seed_dir),
        "workspace_scope_root": str(root),
        "binding_confirmed": binding.binding_confirmed,
        "binding_reason": binding.binding_reason,
        "seed_depth": depth,
        "seed_profile": "deep" if depth >= 8 else "normal",
        "seed_tool_version": "bago.seed.v1",
    }
    (seed_dir / "workspace.json").write_text(_json_text(workspace_payload), encoding="utf-8")
    binding = resolve_workspace_binding(root)
    workspace_payload["binding_confirmed"] = binding.binding_confirmed
    workspace_payload["binding_reason"] = binding.binding_reason
    (seed_dir / "workspace.json").write_text(_json_text(workspace_payload), encoding="utf-8")
    link_marker = seed_dir / "link.json"
    if not link_marker.exists():
        link_marker.write_text(_json_text({
            "schema": 1,
            "project_root": str(root),
            "tools_dir": str(Path(__file__).resolve().parent),
            "linked_at": _now_iso(),
            "mode": "seed+marker",
            "seeded": True,
        }), encoding="utf-8")
    _update_context_link_flag(root, linked=True)

    engine = DirectoryContextEngine(root, seed_dir / "context")
    snapshot = engine.build()
    file_terms = [
        Path(item.get("path", "")).stem
        for item in snapshot.get("files", [])
        if isinstance(item, dict) and item.get("kind") == "file" and item.get("path")
    ]
    query_terms = ["workspace", "seed", *[term for term in file_terms[:8] if term]]
    query = " ".join(dict.fromkeys(term for term in query_terms if term))
    fragments, working_set = engine.retrieve(query, limit_files=8, limit_symbols=12)

    working_set_size = max(
        len(working_set.get("files", [])),
        len(working_set.get("symbols", [])),
        len(working_set.get("evidence", [])),
        len(fragments),
    )
    meta = {
        "schema": "bago.seed.meta.v1",
        "execution_id": str(uuid.uuid4()),
        "workspace_root": str(root),
        "workspace_state_root": str(seed_dir),
        "seed_depth": depth,
        "seed_profile": "deep" if depth >= 8 else "normal",
        "files_scanned": int(tree.get("count", 0)),
        "files_indexed": len(snapshot.get("files", [])),
        "symbols_indexed": len(snapshot.get("symbols", [])),
        "dependencies_indexed": sum(len(v) for v in (snapshot.get("graph", {}) or {}).get("imports", {}).values()),
        "working_set_size": working_set_size,
        "warnings": [],
        "errors": [],
        "snapshot_id": snapshot.get("repository_map", {}).get("captured_at", ""),
        "seed_tool_version": "bago.seed.v1",
        "workspace_id": binding.workspace_id,
        "binding_confirmed": binding.binding_confirmed,
    }
    (seed_dir / "seed.meta.json").write_text(_json_text(meta), encoding="utf-8")
    (seed_dir / "events.jsonl").write_text(
        json.dumps({
            "event": "seed",
            "execution_id": meta["execution_id"],
            "workspace_root": str(root),
            "seed_depth": depth,
            "files_scanned": meta["files_scanned"],
            "symbols_indexed": meta["symbols_indexed"],
            "working_set_size": meta["working_set_size"],
        }, ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )

    return {
        "root": str(root),
        "depth": depth,
        "tree": tree,
        "live": live,
        "manifests": manifests,
        "diff": diff_payload,
        "workspace": workspace_payload,
        "meta": meta,
        "context_root": str(seed_dir / "context"),
        "working_set": working_set,
        "fragments": fragments,
    }


def format_analysis(data: dict[str, Any]) -> str:
    lines = [
        f"Project root: {data['root']}",
        f"Configured: {'yes' if data['configured'] else 'no'}",
        f"Linked: {'yes' if data['linked'] else 'no'} ({data['link_mode']})",
        f"Stack detected: {', '.join(data.get('stack', [])) or 'unknown'}",
    ]
    if data.get("issues"):
        lines.append("Issues:")
        for item in data["issues"]:
            lines.append(f"  - {item}")
    if data.get("suggestions"):
        lines.append("Suggested next checks:")
        for item in data["suggestions"]:
            lines.append(f"  - {item}")
    if data.get("tree"):
        lines.append("")
        lines.append("Directory snapshot:")
        lines.append(data["tree"])
    return "\n".join(lines)


def format_status(data: dict[str, Any]) -> str:
    lines = [
        f"Project root: {data['root']}",
        f".bago present: {'yes' if data['exists'] else 'no'}",
        f"Configured: {'yes' if data['configured'] else 'no'}",
        f"Linked: {'yes' if data['linked'] else 'no'} ({data['link_mode']})",
        "Directories:",
    ]
    for name, exists in sorted(data["directories"].items()):
        lines.append(f"  [{'OK' if exists else '--'}] {name}")
    lines.append("Files:")
    for name, exists in sorted(data["files"].items()):
        lines.append(f"  [{'OK' if exists else '--'}] {name}")
    lines.append(f"Marker: {data['marker']}")
    lines.append(f"Symlink: {data['symlink']}")
    return "\n".join(lines)


def cmd_init(root: str | None = None) -> int:
    project_root = resolve_project_root(root, allow_fallback_cwd=False)
    if project_root is None:
        print("Error: no se detecta un proyecto. Usa --root <ruta>.")
        return 1
    report = init_project(project_root)
    print(f"Initialized project memory at: {report['bago_dir']}")
    print(f"Created directories: {len(report['created_dirs'])}")
    print(f"Created files: {len(report['created_files'])}")
    return 0


def cmd_status(root: str | None = None) -> int:
    project_root = resolve_project_root(root, allow_fallback_cwd=False)
    if project_root is None:
        print("Error: no se detecta un proyecto. Usa --root <ruta>.")
        return 1
    print(format_status(status_data(project_root)))
    return 0


def cmd_link(root: str | None = None) -> int:
    project_root = resolve_project_root(root, allow_fallback_cwd=False)
    if project_root is None:
        print("Error: no se detecta un proyecto. Usa --root <ruta>.")
        return 1
    data = link_project(project_root)
    print(f"Linked project memory at: {data['root']}")
    print(f"Link mode: {data['link_mode']}")
    print(f"Marker: {data['marker']}")
    return 0


def cmd_analyze(root: str | None = None) -> int:
    project_root = resolve_project_root(root, allow_fallback_cwd=False)
    if project_root is None:
        print("Error: no se detecta un proyecto. Usa --root <ruta>.")
        return 1
    data = analyze_data(project_root)
    print(format_analysis(data))
    return 0


def cmd_seed(root: str | None = None, *, depth: int = 3, ref: str | None = None) -> int:
    project_root = resolve_project_root(root, allow_fallback_cwd=False)
    if project_root is None:
        print("Error: no se detecta un proyecto. Usa --root <ruta>.")
        return 1
    report = seed_project(project_root, depth=depth, ref=ref)
    print(f"Seeded workspace at: {report['root']}")
    print(f"Tree files: {report['tree']['count']}")
    print(f"Files indexed: {report['meta']['files_indexed']}")
    print(f"Symbols indexed: {report['meta']['symbols_indexed']}")
    print(f"Working set size: {report['meta']['working_set_size']}")
    return 0


def _reset_workspace() -> Path:
    if TEST_WORKSPACE.exists():
        shutil.rmtree(TEST_WORKSPACE)
    TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return TEST_WORKSPACE


def _capture_output(func, *args):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = func(*args)
    return result, buffer.getvalue()


def _snapshot(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted((root / ".bago").rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return out


def run_self_tests() -> int:
    workspace = _reset_workspace()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        results.append((name, condition, detail))

    project_root = workspace / "sample_project"
    init_project(project_root)
    check("init_dirs", (project_root / ".bago" / "state" / "sessions").is_dir(), "init creates state/sessions")
    check("init_files", (project_root / ".bago" / "pack.json").exists(), "init creates pack.json")

    _, status_output = _capture_output(cmd_status, str(project_root))
    check("status_output", "Project root:" in status_output and "Configured: yes" in status_output, "status prints summary")

    link_project(project_root)
    check("link_marker", (project_root / ".bago" / "link.json").exists(), "link creates marker")

    before = _snapshot(project_root)
    second = init_project(project_root)
    after = _snapshot(project_root)
    check("init_idempotent", before == after and not second["created_files"], "init is idempotent")

    _, link_output = _capture_output(cmd_link, str(project_root))
    check("link_output", "Link mode:" in link_output, "link command prints mode")

    (_, analyze_output) = _capture_output(cmd_analyze, str(project_root))
    check("analyze_output", "Suggested next checks:" in analyze_output, "analyze prints suggestions")

    env_root = workspace / "env_project"
    os.environ["BAGO_SCAN_ROOT"] = str(env_root)
    try:
        rc, env_output = _capture_output(main, ["init"])
    finally:
        os.environ.pop("BAGO_SCAN_ROOT", None)
    check("env_root", rc == 0 and (env_root / ".bago").exists(), "env root fallback works")

    shutil.rmtree(workspace, ignore_errors=True)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable BAGO project memory")
    parser.add_argument("--root", default="", help="Project root (default: BAGO_SCAN_ROOT or cwd)")
    parser.add_argument("--depth", type=int, default=3, help="Seed scan depth")
    parser.add_argument("--ref", default="", help="Reference root for diff generation")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("init", help="Initialize .bago structure")
    sub.add_parser("status", help="Show .bago status")
    sub.add_parser("link", help="Create project link marker")
    sub.add_parser("analyze", help="Analyze the project and suggest next checks")
    seed_parser = sub.add_parser("seed", help="Run workspace seed and write .gabo artifacts")
    seed_parser.add_argument("--root", default="", help="Project root (default: BAGO_SCAN_ROOT or cwd)")
    seed_parser.add_argument("--depth", type=int, default=3, help="Seed scan depth")
    seed_parser.add_argument("--ref", default="", help="Reference root for diff generation")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()
    if args.action == "init":
        return cmd_init(args.root)
    if args.action == "status":
        return cmd_status(args.root)
    if args.action == "link":
        return cmd_link(args.root)
    if args.action == "analyze":
        return cmd_analyze(args.root)
    if args.action == "seed":
        return cmd_seed(args.root, depth=max(1, min(getattr(args, "depth", 3), 8)), ref=getattr(args, "ref", "") or None)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
