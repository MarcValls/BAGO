#!/usr/bin/env python3
"""Capture current sink evidence and render the BAGO editorial audit PDF."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "architecture" / "bago_context_audit_editorial.md"
MAP = ROOT / "docs" / "architecture" / "bago_mind_map.data.json"
SCANNER = ROOT / "backend" / ".bago" / "tools" / "effect_sink_inventory.py"
REGISTRY = ROOT / "backend" / ".bago" / "contracts" / "bago.effect-registry.v1.json"
RENDERER = ROOT / "scripts" / "editorial" / "render_markdown.py"


def run(*args: str, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=capture, check=False)


def fingerprint() -> str:
    diff = run("git", "diff", "--binary", "HEAD").stdout.encode("utf-8")
    untracked = run("git", "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    material = bytearray(diff)
    for relative in sorted(path for path in untracked if path):
        content = (ROOT / relative).read_bytes()
        material.extend(b"\0UNTRACKED\0")
        material.extend(relative.replace("\\", "/").encode("utf-8"))
        material.extend(b"\0")
        material.extend(hashlib.sha256(content).hexdigest().encode("ascii"))
    return hashlib.sha256(material).hexdigest()


def git_text(*args: str) -> str:
    result = run("git", *args)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def capture_inventory(directory: Path) -> dict:
    before = (git_text("rev-parse", "HEAD"), fingerprint())
    inventory = run(sys.executable, str(SCANNER), "--json")
    if inventory.returncode:
        raise RuntimeError(inventory.stderr or inventory.stdout)
    raw_path = directory / "sink_inventory.json"
    raw_path.write_text(inventory.stdout, encoding="utf-8")
    data = json.loads(inventory.stdout)
    classification = run(sys.executable, str(SCANNER), "--strict-classification")
    runtime = run(sys.executable, str(SCANNER), "--strict-runtime")
    after = (git_text("rev-parse", "HEAD"), fingerprint())
    if before != after:
        raise RuntimeError("HEAD o fingerprint del worktree cambio durante el inventario; se descarta esta captura")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    version = (ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
    meta = {
        "repo_root": str(ROOT),
        "branch": git_text("branch", "--show-current"),
        "head": before[0],
        "worktree_state": "dirty" if run("git", "status", "--porcelain").stdout.strip() else "clean",
        "fingerprint": before[1],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": version,
        "scanner_sha256": hashlib.sha256(SCANNER.read_bytes()).hexdigest(),
        "registry_sha256": hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
        "registry_version": registry.get("version", "unknown"),
        "inventory": data,
        "strict_classification_exit": classification.returncode,
        "strict_runtime_exit": runtime.returncode,
    }
    if classification.returncode not in (0, 1, 2) or runtime.returncode not in (0, 1, 2):
        raise RuntimeError("Un gate devolvio un error de ejecucion no interpretable")
    return meta


def inline(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().replace("|", "\\|")


def map_markdown() -> tuple[str, int]:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    count = 0

    def branch_nodes(nodes: list[dict], depth: int = 0) -> list[str]:
        nonlocal count
        rows = []
        for node in nodes:
            count += 1
            title = inline(node.get("title", "(sin titulo)"))
            status = inline(node.get("status", ""))
            detail = inline(node.get("detail", ""))
            suffix = f" · _{status}_" if status else ""
            suffix += f" — {detail}" if detail else ""
            rows.append(f"{'  ' * depth}- **{title}**{suffix}")
            rows.extend(branch_nodes(node.get("children", []), depth + 1))
        return rows

    chunks = []
    for branch in data.get("branches", []):
        chunks.append(f"## {inline(branch.get('title', 'Rama'))}\n")
        if branch.get("summary"):
            chunks.append(f"_{inline(branch['summary'])}_\n")
        chunks.extend(branch_nodes(branch.get("children", [])))
        chunks.append("")
    return "\n".join(chunks), count


def fill_template(template: str, meta: dict, node_map: str) -> str:
    summary = meta["inventory"]["summary"]
    replacements = {
        "repo_root": meta["repo_root"], "branch": meta["branch"], "head": meta["head"],
        "version": meta["version"], "worktree_state": meta["worktree_state"],
        "fingerprint": meta["fingerprint"], "timestamp": meta["timestamp"],
        "scanner_sha256": meta["scanner_sha256"], "registry_version": meta["registry_version"],
        "registry_sha256": meta["registry_sha256"], "total_sinks": summary["total_sinks"],
        "runtime_unbound": summary["runtime_unbound_sinks"],
        "gateway_owned": meta["inventory"].get("summary", {}).get("by_binding", {}).get("gateway_owned", 0),
        "unclassified": summary["unclassified_scope_sinks"] + summary["unclassified_binding_sinks"],
        "unclassified_scope": summary["unclassified_scope_sinks"],
        "unclassified_binding": summary["unclassified_binding_sinks"],
        "unbound_sinks": summary["unbound_sinks"],
        "high_confidence_unbound": summary["high_confidence_unbound_sinks"],
        "classification_exit": meta["strict_classification_exit"],
        "runtime_exit": meta["strict_runtime_exit"],
        "mind_map": node_map,
    }
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", str(value))
    unresolved = re.findall(r"\{\{[^}]+\}\}", template)
    if unresolved:
        raise RuntimeError(f"Quedan marcadores sin resolver: {unresolved}")
    return template


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "pdf")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = "BAGO_contexto_auditoria_editorial_2026-09-27"
    with tempfile.TemporaryDirectory(prefix="bago-editorial-") as temp:
        temp_dir = Path(temp)
        meta = capture_inventory(temp_dir)
        tree, node_count = map_markdown()
        markdown = fill_template(SOURCE.read_text(encoding="utf-8"), meta, tree)
        md_path = out / f"{base}.md"
        snapshot_path = out / f"{base}.snapshot.json"
        inventory_path = out / f"{base}.inventory.json"
        pdf_path = out / f"{base}.pdf"
        html_path = out / f"{base}.html"
        md_path.write_text(markdown, encoding="utf-8")
        inventory_bytes = (temp_dir / "sink_inventory.json").read_bytes()
        inventory_path.write_bytes(inventory_bytes)
        snapshot = {key: value for key, value in meta.items() if key != "inventory"}
        snapshot["inventory_summary"] = meta["inventory"]["summary"]
        snapshot["inventory_file"] = inventory_path.name
        snapshot["inventory_sha256"] = hashlib.sha256(inventory_bytes).hexdigest()
        snapshot["mind_map_nodes"] = node_count
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        command = [sys.executable, str(RENDERER), str(md_path), str(pdf_path), "--html", str(html_path), "--family", "informe", "--engine", "browser"]
        rendered = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if rendered.returncode:
            raise RuntimeError(rendered.stderr or rendered.stdout)
        import fitz
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        missing = [node["title"] for branch in json.loads(MAP.read_text(encoding="utf-8"))["branches"] for node in branch.get("children", []) if node.get("title", "") not in text]
        if missing:
            raise RuntimeError(f"El PDF no contiene nodos requeridos del mapa: {missing[:8]}")
        print(rendered.stdout.strip())
        print(f"PAGES {len(doc)} | MIND_MAP_NODES {node_count} | PDF_BYTES {pdf_path.stat().st_size}")
        print(f"SNAPSHOT {snapshot_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
