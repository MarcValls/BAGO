#!/usr/bin/env python3
"""Release seal helper: produce checksums, release.json, release.sig, tags/v4.1.5.json
for BAGO 4.1.5 including bago_supervisor.py.

Usage:
    python scripts\\seal_release_415.py
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = Path.home() / ".bago" / "launch"
VERSIONS = Path.home() / ".bago" / "versions" / "4.1.5"
TAGS = ROOT / "bago_core" / "tags"
SUPERVISOR = "scripts/bago_supervisor.py"
SIG_ALG = "chained-sha256"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _kb_stats() -> dict:
    """Pull knowledge.db row counts. Schema may differ across versions; degrade gracefully."""
    candidates = [
        Path.home() / ".bago" / "knowledge" / "knowledge.db",
        Path.home() / ".bago" / "knowledge" / "kb.db",
        Path.home() / ".bago" / "knowledge" / "rag.db",
    ]
    for db in candidates:
        if not db.exists():
            continue
        try:
            c = sqlite3.connect(str(db))
            cur = c.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            stats: dict = {"db": str(db), "total": 0, "by_table": {}, "real_embeddings": 0, "fallback": 0}
            for t in sorted(tables):
                if t.startswith("sqlite_"):
                    continue
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                n = cur.fetchone()[0]
                stats["by_table"][t] = n
                stats["total"] += n
                # BAGO 4.1.5 schema: topic=real-ingested, session_arc=fallback, etc.
                if t == "topic":
                    stats["real_embeddings"] += n
                elif t in ("session_arc", "simulation"):
                    stats["fallback"] += n
                else:
                    stats["fallback"] += n
            return stats
        except Exception as exc:
            return {"db": str(db), "error": str(exc)}
    return {"db": None, "total": 0, "by_table": {}, "real_embeddings": 0, "fallback": 0}


def _checksums(root: Path, out: Path) -> int:
    """Re-hash the BAGO source root, excluding build/release artifacts. Returns file count."""
    excluded_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules", ".vite",
                     "release", "dist", "build", "PLAN_VERTICE", ".bago/state", ".bago/logs"}
    forbidden = {"credentials.json", "install_config.json", ".env", ".env.local"}
    out.write_text("", encoding="utf-8")
    files: list[tuple[str, str]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        parts = set(rel.parts)
        if parts & excluded_dirs:
            continue
        if rel.name in forbidden:
            continue
        files.append((_sha256_file(p), rel.as_posix()))
    files.sort(key=lambda x: x[1])
    with out.open("w", encoding="utf-8") as f:
        for h, rel in files:
            f.write(f"{h}  {rel}\n")
    return len(files)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _release_payload(stats: dict) -> dict:
    return {
        "checksums": str(LAUNCH / "checksums.sha256"),
        "bundle_id": "bago.v4.1.5",
        "promoted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "default_model": "llama3.2:3b",
        "fallback_chain": [
            {"provider": "ollama-local", "model": "llama3.2:3b"},
            {"provider": "cpp-local", "model": "bago-cpp-local"},
        ],
        "launcher": r"C:\Program Files\BAGO\bago.ps1",
        "version": "4.1.5",
        "evidence": "historical-evidence-not-shipped",
        "target": r"C:\Program Files\BAGO",
        "routing": r"BAGO\docs\contracts\bago_v4_routing_presets.json",
        "source": str(ROOT),
        "supervisor": {
            "script": SUPERVISOR,
            "always_on": True,
            "stop_signal": "sentinel_file",
            "max_grace_seconds": 10,
        },
        "knowledge": {
            "kb_rows_total": stats.get("total", 0),
            "by_table": stats.get("by_table", {}),
            "fallback": stats.get("fallback", 0),
            "embedding_model": stats.get("embedding_model", "llama3.2:3b"),
            "real_embeddings": stats.get("real_embeddings", 0),
            "source_db": stats.get("db"),
        },
    }


def _chained_sig(release: dict, checksums: str) -> dict:
    """chained-sha256: key = sha256(release_json_bytes); seal = sha256(key || checksums_sha)."""
    body = json.dumps(release, sort_keys=True, ensure_ascii=False).encode("utf-8")
    key = _sha256_bytes(body)
    check = _sha256_bytes(checksums.encode("utf-8"))
    seal = _sha256_bytes((key + check).encode("ascii"))
    return {
        "algorithm": SIG_ALG,
        "signed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "release_sha256": key,
        "key_sha256": key,
        "checksums_sha256": check,
        "seal_sha256": seal,
    }


def _tag_snapshot(release: dict, sig: dict) -> dict:
    return {
        "tag": "v4.1.5",
        "version": "4.1.5",
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "release": release,
        "signature": sig,
        "components": {
            "supervisor": SUPERVISOR,
            "launchers": [
                r"C:\Program Files\BAGO\bago.ps1",
                r"C:\Program Files\BAGO\bago.cmd",
                r"C:\Users\AMTEC_Terminal_1º\.bago\bago.ps1",
                r"C:\Users\AMTEC_Terminal_1º\.bago\bago.cmd",
                r"C:\Users\AMTEC_Terminal_1º\BAGO\bago.ps1",
                r"C:\Users\AMTEC_Terminal_1º\BAGO\bago.cmd",
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-checksums", action="store_true",
                        help="Don't recompute checksums (use existing)")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    args = parser.parse_args(argv)

    if not ROOT.exists():
        print(f"root missing: {ROOT}")
        return 1
    if not (ROOT / SUPERVISOR).exists():
        print(f"supervisor missing: {ROOT / SUPERVISOR}")
        return 1

    LAUNCH.mkdir(parents=True, exist_ok=True)
    VERSIONS.mkdir(parents=True, exist_ok=True)
    TAGS.mkdir(parents=True, exist_ok=True)

    n = 0
    if not args.skip_checksums:
        n = _checksums(ROOT, LAUNCH / "checksums.sha256")
        # Also stage the same into versions/4.1.5
        shutil.copy2(LAUNCH / "checksums.sha256", VERSIONS / "checksums.sha256")
        print(f"checksums: {n} files")

    stats = _kb_stats()
    release = _release_payload(stats)
    sig = _chained_sig(release, (LAUNCH / "checksums.sha256").read_text(encoding="utf-8"))
    tag = _tag_snapshot(release, sig)

    print(f"release_sha256: {sig['release_sha256']}")
    print(f"checksums_sha:  {sig['checksums_sha256']}")
    print(f"seal_sha256:    {sig['seal_sha256']}")
    print(f"knowledge:      total={stats.get('total')} real={stats.get('real_embeddings')} "
          f"fallback={stats.get('fallback')}")

    if args.dry_run:
        return 0

    (LAUNCH / "release.json").write_text(
        json.dumps(release, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (LAUNCH / "release.sig").write_text(
        json.dumps(sig, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copy2(LAUNCH / "release.json", VERSIONS / "release.json")
    shutil.copy2(LAUNCH / "release.sig", VERSIONS / "release.sig")
    (TAGS / "v4.1.5.json").write_text(
        json.dumps(tag, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote:")
    print(f"  {LAUNCH / 'release.json'}")
    print(f"  {LAUNCH / 'release.sig'}")
    print(f"  {LAUNCH / 'checksums.sha256'}")
    print(f"  {VERSIONS / 'release.json'}")
    print(f"  {VERSIONS / 'release.sig'}")
    print(f"  {TAGS / 'v4.1.5.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
