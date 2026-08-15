#!/usr/bin/env python3
"""cosecha.py — W9 harvest tool for closing an exploration block.

The script captures three answers, records a closed harvest session, writes a
CHG and an EVD artifact, and updates the global state inventory plus
knowledge_base.last_harvest.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS_FILE = Path(__file__).resolve()
TOOLS_DIR = THIS_FILE.parent
CORE_DIR = TOOLS_DIR.parent / "core"
for _path in (TOOLS_DIR, CORE_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from bago_utils import get_scan_root, load_json, timestamp_iso  # noqa: E402


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _now() -> str:
    return timestamp_iso()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _unique_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _validate_session_id(session_id: str) -> str:
    value = _clean_text(session_id)
    if not SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("session_id inválido")
    return value


def _git_modified_files(project_root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return []
    if completed.returncode != 0:
        return []

    files: list[str] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.rstrip()
        if len(line) < 4:
            continue
        candidate = line[3:].strip()
        if " -> " in candidate:
            candidate = candidate.split(" -> ", 1)[1].strip()
        if candidate:
            files.append(candidate.replace("\\", "/"))
    # Preserve order while de-duplicating.
    return list(dict.fromkeys(files))


def _merge_modified_files(project_root: Path, explicit: list[str]) -> list[str]:
    files = [_clean_text(item).replace("\\", "/") for item in explicit if _clean_text(item)]
    if not files:
        files = _git_modified_files(project_root)
    return list(dict.fromkeys(files))


def _default_global_state() -> dict[str, Any]:
    template = THIS_FILE.parent.parent / "state.example" / "global_state.json"
    data = load_json(template, {})
    return data if isinstance(data, dict) else {}


def _resolve_state_root(project_root: Path, explicit: str | None) -> Path:
    if explicit and _clean_text(explicit):
        return Path(explicit).expanduser().resolve()
    env_state = os.environ.get("BAGO_STATE_DIR", "").strip()
    if env_state:
        return Path(env_state).expanduser().resolve()
    return (project_root / ".bago" / "state").resolve()


def _load_global_state(state_root: Path) -> dict[str, Any]:
    path = state_root / "global_state.json"
    if path.exists():
        data = load_json(path, {})
        return data if isinstance(data, dict) else {}
    return _default_global_state()


def _question(prompt: str, fallback: str) -> str:
    try:
        value = input(prompt).strip()
    except EOFError:
        value = ""
    return _clean_text(value) or fallback


def _build_summary(decision: str, discard: str, next_step: str) -> str:
    return f"Harvest W9. Decisión: {decision}. Descarte: {discard}. Próximo: {next_step}."


def _session_paths(state_root: Path, session_id: str) -> tuple[Path, Path]:
    session_dir = state_root / "sessions" / session_id
    session_file = state_root / "sessions" / f"{session_id}.json"
    return session_dir, session_file


def _write_session_artifacts(
    state_root: Path,
    project_root: Path,
    *,
    session_id: str,
    decision: str,
    discard: str,
    next_step: str,
    modified_files: list[str],
    summary: str,
    change_id: str,
    evidence_id: str,
) -> dict[str, Path]:
    session_dir, session_file = _session_paths(state_root, session_id)
    now = _now()
    meta = {
        "session_id": session_id,
        "session_title": "Harvest W9",
        "task_type": "harvest",
        "selected_workflow": "w9_cosecha",
        "roles_activated": ["role_auditor"],
        "status": "closed",
        "archived": False,
        "created_at": now,
        "updated_at": now,
        "project_root": str(project_root),
        "authorized_root": str(project_root),
        "persistent_goal": summary,
        "decisions": [decision, discard],
        "next_step": next_step,
        "summary": summary,
        "change_id": change_id,
        "evidence_id": evidence_id,
        "modified_files": modified_files,
    }
    session_payload = {
        **meta,
        "active_conversation_id": "main",
        "conversation_count": 1,
        "provider": "manual",
        "model": "manual",
    }
    _atomic_write_json(session_dir / "meta.json", meta)
    _atomic_write_json(session_dir / "tokens.json", {"prompt": 0, "completion": 0, "total": 0})
    _atomic_write_text(
        session_dir / "context.jsonl",
        json.dumps({
            "role": "assistant",
            "content": summary,
            "timestamp": now,
        }, ensure_ascii=False) + "\n",
    )
    _atomic_write_text(
        session_dir / "timeline.jsonl",
        json.dumps({
            "event": "harvest_closed",
            "session_id": session_id,
            "timestamp": now,
        }, ensure_ascii=False) + "\n",
    )
    _atomic_write_json(session_file, session_payload)

    change_payload = {
        "change_id": change_id,
        "title": "W9 harvest closure",
        "type": "harvest",
        "severity": "patch",
        "status": "validated",
        "motivation": "Formalizar una exploración madura y cerrar la sesión.",
        "scope": modified_files,
        "impacts": ["sessions", "changes", "evidences", "global_state", "knowledge_base"],
        "requires_migration": False,
        "validation_result": "Harvest written, closed and indexed.",
        "source_path": str(session_file),
        "source_format": "json",
        "raw_markdown_preserved": False,
        "created_at": now,
        "updated_at": now,
        "session_id": session_id,
        "summary": summary,
        "details": {
            "decision": decision,
            "discard": discard,
            "next_step": next_step,
            "modified_files": modified_files,
        },
    }
    evidence_payload = {
        "evidence_id": evidence_id,
        "type": "closure",
        "related_to": [session_id, change_id],
        "summary": "W9 harvest recorded and closed.",
        "details": {
            "decision": decision,
            "discard": discard,
            "next_step": next_step,
        },
        "status": "recorded",
        "recorded_at": now,
        "summary_text": summary,
    }
    _atomic_write_json(state_root / "changes" / f"{change_id}.json", change_payload)
    _atomic_write_json(state_root / "evidences" / f"{evidence_id}.json", evidence_payload)

    return {
        "session_dir": session_dir,
        "session_file": session_file,
        "change_file": state_root / "changes" / f"{change_id}.json",
        "evidence_file": state_root / "evidences" / f"{evidence_id}.json",
    }


def _update_global_state(
    state_root: Path,
    *,
    session_id: str,
    change_id: str,
    evidence_id: str,
    summary: str,
    modified_files: list[str],
) -> Path:
    global_state_path = state_root / "global_state.json"
    data = _load_global_state(state_root)
    if not isinstance(data.get("health"), dict):
        data["health"] = {"score": 0, "max": 100, "status": "unknown"}
    if not isinstance(data.get("sprint_status"), dict):
        data["sprint_status"] = {
            "active_workflow": None,
            "pending_w2_task": "none",
            "last_completed_workflow": None,
        }
    if not isinstance(data.get("inventory"), dict):
        data["inventory"] = {"sessions": 0, "changes": 0, "evidences": 0}
    if not isinstance(data.get("unresolved"), dict):
        data["unresolved"] = {"stashes": 0, "note": ""}

    data["inventory"] = {
        "sessions": len(list((state_root / "sessions").glob("*.json"))),
        "changes": len(list((state_root / "changes").glob("*.json"))),
        "evidences": len(list((state_root / "evidences").glob("*.json"))),
    }
    data["last_validation"] = {
        "kind": "w9_harvest",
        "status": "validated",
        "session_id": session_id,
        "change_id": change_id,
        "evidence_id": evidence_id,
        "summary": summary,
        "modified_files": modified_files,
        "updated_at": _now(),
    }
    knowledge_base = data.get("knowledge_base")
    if not isinstance(knowledge_base, dict):
        knowledge_base = {}
    knowledge_base["last_harvest"] = _now()
    knowledge_base["last_harvest_session_id"] = session_id
    knowledge_base["last_harvest_change_id"] = change_id
    knowledge_base["last_harvest_evidence_id"] = evidence_id
    data["knowledge_base"] = knowledge_base

    notes = data.get("notes")
    if not isinstance(notes, list):
        notes = []
    notes.append(summary)
    data["notes"] = notes[-10:]

    _atomic_write_json(global_state_path, data)
    return global_state_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a W9 harvest and persist its closure artifacts.")
    parser.add_argument("--root", default="", help="Project root to inspect for changed files")
    parser.add_argument("--state-root", default="", help="Explicit mutable state root")
    parser.add_argument("--session-id", default="", help="Optional fixed harvest session id")
    parser.add_argument("--decision", default="", help="Answer to question 1")
    parser.add_argument("--discard", default="", help="Answer to question 2")
    parser.add_argument("--next-step", default="", help="Answer to question 3")
    parser.add_argument("--summary", default="", help="Optional summary override")
    parser.add_argument("--modified-file", action="append", default=[], help="Explicit modified file path")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    return parser


def run_harvest(args: argparse.Namespace) -> dict[str, Any]:
    project_root = get_scan_root(args.root or None)
    state_root = _resolve_state_root(project_root, args.state_root or None)

    decision = _clean_text(args.decision) or _question("1/3 ¿Qué decidiste en esta exploración? ", "No se registró una decisión explícita.")
    discard = _clean_text(args.discard) or _question("2/3 ¿Qué descartaste y por qué? ", "No se descartó ninguna opción explícitamente.")
    next_step = _clean_text(args.next_step) or _question("3/3 ¿Cuál es el próximo paso concreto? ", "Pendiente de definir.")
    summary = _clean_text(args.summary) or _build_summary(decision, discard, next_step)
    modified_files = _merge_modified_files(project_root, list(args.modified_file or []))

    session_id = _clean_text(args.session_id) or _unique_id("harvest")
    session_id = _validate_session_id(session_id)
    change_id = _unique_id("CHG")
    evidence_id = _unique_id("EVD")

    paths = _write_session_artifacts(
        state_root,
        project_root,
        session_id=session_id,
        decision=decision,
        discard=discard,
        next_step=next_step,
        modified_files=modified_files,
        summary=summary,
        change_id=change_id,
        evidence_id=evidence_id,
    )
    global_state_path = _update_global_state(
        state_root,
        session_id=session_id,
        change_id=change_id,
        evidence_id=evidence_id,
        summary=summary,
        modified_files=modified_files,
    )
    return {
        "ok": True,
        "task_type": "harvest",
        "status": "closed",
        "workflow": "w9_cosecha",
        "session_id": session_id,
        "change_id": change_id,
        "evidence_id": evidence_id,
        "project_root": str(project_root),
        "state_root": str(state_root),
        "modified_files": modified_files,
        "decision": decision,
        "discard": discard,
        "next_step": next_step,
        "summary": summary,
        "artifacts": {key: str(value) for key, value in paths.items()},
        "global_state": str(global_state_path),
    }


def run_self_tests() -> int:
    import tempfile

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        project = root / "project"
        state = root / "state"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")
        _atomic_write_json(state / "global_state.json", _default_global_state())
        args = argparse.Namespace(
            root=str(project),
            state_root=str(state),
            session_id="",
            decision="Decidir semánticamente",
            discard="Descartar el reloj de 30 minutos",
            next_step="Implementar cosecha portable",
            summary="",
            modified_file=["src/app.py"],
            test=False,
        )
        result = run_harvest(args)
        record("cosecha:ok", result["ok"] is True, result["status"])
        record("cosecha:session", (state / "sessions").exists(), result["session_id"])
        record("cosecha:global_state", (state / "global_state.json").exists(), result["global_state"])

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

    try:
        result = run_harvest(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
