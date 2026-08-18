#!/usr/bin/env python3
"""Canonical BAGO runtime wrapper.

This script is the small, uniform entry point expected by the `bago-core` skill.
It delegates to the real modules below and records verification evidence under
.bago/runtime/ and .bago/state/.

Commands:
    status    Show project lifecycle state, version, active handoff and conflicts.
    verify    Run a real check command and record its result.
    doctor    Run the portable project doctor.
    handoff   Set or read the active handoff note.

Usage examples:
    python backend/.bago/bin/bago.py status
    python backend/.bago/bin/bago.py verify -- pytest backend/tests
    python backend/.bago/bin/bago.py doctor
    python backend/.bago/bin/bago.py handoff --set "Blocked waiting for API key"
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Make .bago/tools and bago_core importable without mutating the project tree.
_THIS = Path(__file__).resolve()
BAGO_ROOT = _THIS.parent.parent
REPO_ROOT = BAGO_ROOT.parent.parent
TOOLS_DIR = BAGO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _path_helper import ensure_core_path  # noqa: E402

ensure_core_path()

RUNTIME_DIR = BAGO_ROOT / "runtime"
STATE_DIR = BAGO_ROOT / "state"
DECISIONS_DIR = BAGO_ROOT / "decisions"
CONFLICTS_DIR = BAGO_ROOT / "conflicts"

ACTIVE_HANDOFF = RUNTIME_DIR / "ACTIVE_HANDOFF.md"
DECISIONS_FILE = DECISIONS_DIR / "DECISIONS.md"
CONFLICTS_FILE = CONFLICTS_DIR / "CONFLICTS.md"
PROJECT_STATE_FILE = STATE_DIR / "PROJECT_STATE.json"


def _ensure_dirs() -> None:
    for d in (RUNTIME_DIR, STATE_DIR, DECISIONS_DIR, CONFLICTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _git_sha() -> str | None:
    candidates = [REPO_ROOT, BAGO_ROOT, REPO_ROOT / "backend"]
    for cwd in candidates:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            sha = result.stdout.strip()[:12]
            if sha:
                return sha
        except Exception:
            continue
    return None


def _read_version() -> str:
    # bago_core.versioning.repo_root() points to backend/, so pass that root.
    backend_root = REPO_ROOT / "backend"
    try:
        from bago_core.versioning import current  # type: ignore
        return current(backend_root)
    except Exception:
        pass
    # Fallback: read release_version.txt under backend/.
    for rel in ("backend/release_version.txt", "backend/.gabo/release_version.txt"):
        p = REPO_ROOT / rel
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return "unknown"


def _resolve_runtime_root() -> Path:
    """Return absolute repo/backend root resolving pack.json/link.json root_rel entries."""
    # Prefer link.json because it declares the project root relative to the repo root.
    link_json = BAGO_ROOT / "link.json"
    if link_json.exists():
            try:
                data = json.loads(link_json.read_text(encoding="utf-8", errors="ignore"))
                rel = data.get("project_root_rel")
                if rel:
                    resolved = (REPO_ROOT / rel).resolve()
                    if resolved.exists():
                        return resolved
            except Exception:
                pass
    # pack.json lives under backend/.bago/ and may declare root_rel == '.' from its own dir.
    pack_json = BAGO_ROOT / "pack.json"
    if pack_json.exists():
            try:
                data = json.loads(pack_json.read_text(encoding="utf-8", errors="ignore"))
                rel = data.get("root_rel")
                if rel:
                    resolved = (pack_json.parent / rel).resolve()
                    # pack.json root_rel == '.' resolves to backend/.bago; project root is one level up.
                    if resolved.name == ".bago" and (resolved.parent).exists():
                        return resolved.parent
                    if resolved.exists():
                        return resolved
            except Exception:
                pass
    return REPO_ROOT / "backend"


def _read_context_tree_summary() -> dict[str, Any]:
    tree_path = BAGO_ROOT / "context" / "context-tree.json"
    if not tree_path.exists():
        return {"exists": False}
    try:
        data = json.loads(tree_path.read_text(encoding="utf-8", errors="ignore"))
        nodes = data.get("nodes", {})
        active = sum(1 for n in nodes.values() if n.get("status") == "active")
        conflicts = sum(1 for n in nodes.values() if n.get("conflictNodeIds"))
        return {"exists": True, "nodes": len(nodes), "active": active, "conflicts": conflicts}
    except Exception as exc:
        return {"exists": True, "error": str(exc)}


def _read_handoff() -> str:
    if ACTIVE_HANDOFF.exists():
        return ACTIVE_HANDOFF.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


def _write_handoff(note: str) -> None:
    ACTIVE_HANDOFF.write_text(
        f"<!-- Active handoff updated {_now()} -->\n{note}\n",
        encoding="utf-8",
    )


def _load_project_state() -> dict[str, Any]:
    if PROJECT_STATE_FILE.exists():
        try:
            return json.loads(PROJECT_STATE_FILE.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass
    return {"lifecycle": "unknown", "notes": []}


def _save_project_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    state["updated_from"] = str(_THIS.relative_to(REPO_ROOT))
    PROJECT_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_status(args: argparse.Namespace) -> int:
    state = _load_project_state()
    version = _read_version()
    ctx = _read_context_tree_summary()
    handoff = _read_handoff()
    output = {
        "lifecycle": state.get("lifecycle", "unknown"),
        "version": version,
        "git_sha": _git_sha(),
        "context_tree": ctx,
        "handoff": handoff[:200] + "..." if len(handoff) > 200 else handoff,
        "decisions_exists": DECISIONS_FILE.exists(),
        "conflicts_exists": CONFLICTS_FILE.exists(),
    }
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"BAGO status: {output['lifecycle']}")
        print(f"Version: {output['version']}")
        print(f"Git SHA: {output['git_sha'] or 'n/a'}")
        print(f"Context tree: {ctx['nodes']} nodes ({ctx.get('active', 0)} active, {ctx.get('conflicts', 0)} conflicts)")
        print(f"Handoff: {output['handoff'] or 'none'}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    if not args.command:
        print("verify requires a command: python .bago/bin/bago.py verify -- <command>", file=sys.stderr)
        return 2
    # Verification commands are executed from the repository root so that relative
    # paths (e.g. backend/...) resolve correctly regardless of where the wrapper
    # lives inside the monorepo.
    verify_root = REPO_ROOT
    # Record the command before running it.
    run_id = _now().replace(":", "-").replace("+", "-")
    # argparse.REMAINDER leaves the leading '--' in the list; drop it if present.
    cmd = args.command[1:] if args.command and args.command[0] == "--" else args.command
    evidence = {
        "id": f"verify-{run_id}",
        "started_at": _now(),
        "command": cmd,
        "cwd": str(verify_root),
        "git_sha": _git_sha(),
    }
    print(f"[verify] running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=verify_root,
            capture_output=True,
            text=True,
        )
        evidence["returncode"] = result.returncode
        evidence["stdout"] = result.stdout
        evidence["stderr"] = result.stderr
        evidence["finished_at"] = _now()
        evidence["status"] = "passed" if result.returncode == 0 else "failed"
    except Exception as exc:
        evidence["returncode"] = 2
        evidence["stderr"] = str(exc)
        evidence["finished_at"] = _now()
        evidence["status"] = "error"

    evidence_file = RUNTIME_DIR / f"{evidence['id']}.json"
    evidence_file.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    state = _load_project_state()
    state["last_verification"] = evidence["id"]
    _save_project_state(state)

    if evidence["status"] == "passed":
        print(f"[verify] PASSED → evidence: {evidence_file.relative_to(REPO_ROOT)}")
        return 0
    print(f"[verify] {evidence['status'].upper()} (rc={evidence['returncode']}) → evidence: {evidence_file.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        import doctor
        runtime_root = _resolve_runtime_root()
        argv = ["--root", str(runtime_root), "--json"]
        rc = doctor.main(argv)
        state = _load_project_state()
        state["last_doctor_run"] = _now()
        state["last_doctor_rc"] = rc
        _save_project_state(state)
        # Render the JSON result ourselves to keep CLI behavior consistent.
        try:
            import json as _json
            result_text = (RUNTIME_DIR / "doctor_last.json").read_text(encoding="utf-8", errors="ignore")
            result = _json.loads(result_text)
        except Exception:
            result = {"total": -1, "errors": -1, "warnings": -1, "findings": []}
        if args.json:
            print(_json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if not args.quiet:
                for item in result.get("findings", []):
                    sev = item.get("severity", "info").upper()
                    print(f"[{sev}] {item.get('code')} {item.get('path')} - {item.get('detail')}")
            else:
                for item in result.get("findings", []):
                    if item.get("severity") == "error":
                        print(f"[ERROR] {item.get('code')} {item.get('path')} - {item.get('detail')}")
            print(f"Summary: total={result['total']} errors={result['errors']} warnings={result['warnings']}")
        if args.fix and result.get("findings"):
            print("Fix hints:")
            seen = []
            for item in result["findings"]:
                code = item.get("code")
                if code and code not in seen:
                    seen.append(code)
            hints = {
                "DR-E001": "Fix Python syntax errors and re-run the tool.",
                "DR-E002": "Repair invalid JSON with a JSON formatter or parser.",
                "DR-E003": "Re-save the file as UTF-8 without invalid bytes.",
                "DR-W001": "Move large artifacts out of source tree or add them to ignore rules.",
                "DR-W002": "Delete leftover backup or conflict files if they are no longer needed.",
            }
            for code in seen:
                print(f"  {code}: {hints.get(code, 'Review the file and fix the issue.')}")
        return rc
    except Exception as exc:
        print(f"[doctor] failed: {exc}", file=sys.stderr)
        return 2


def cmd_handoff(args: argparse.Namespace) -> int:
    if args.set:
        _write_handoff(args.set)
        print("[handoff] updated")
        return 0
    print(_read_handoff() or "[handoff] empty")
    return 0


def main(argv: list[str] | None = None) -> int:
    _ensure_dirs()
    # Shared flags must be available both before and after the subcommand.
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="Output JSON where supported")

    parser = argparse.ArgumentParser(prog="bago", description="BAGO canonical runtime wrapper")
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_status = subparsers.add_parser("status", help="Project lifecycle status", parents=[shared])
    p_status.set_defaults(func=cmd_status)

    p_verify = subparsers.add_parser("verify", help="Run a verification command and record evidence", parents=[shared])
    p_verify.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --")
    p_verify.set_defaults(func=cmd_verify)

    p_doctor = subparsers.add_parser("doctor", help="Run portable project doctor", parents=[shared])
    p_doctor.add_argument("--quiet", action="store_true")
    p_doctor.add_argument("--fix", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    p_handoff = subparsers.add_parser("handoff", help="Set or read active handoff note", parents=[shared])
    p_handoff.add_argument("--set", default="", help="Update the handoff note")
    p_handoff.set_defaults(func=cmd_handoff)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
