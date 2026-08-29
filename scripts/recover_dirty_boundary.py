#!/usr/bin/env python3
"""Recover and verify the initial dirty remediation boundary patch."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA = "e76b01b0a0552d8eee7c536f8c4eef25e3a82a42"
RECORDED_SHA256 = "943f59fd339f0f57c63f21beb785c0d3c35f6977ecf7bf569b74c324a523bb79"
RECORDED_SIZE = 13711
OUTPUT_PATCH = ROOT / ".bago" / "audits" / "recovered-dirty-boundary-20260824.patch"
OUTPUT_PROVENANCE = ROOT / ".bago" / "audits" / "recovered-dirty-boundary-20260824.json"
DEFAULT_SESSION_LOG = (
    Path.home()
    / ".codex"
    / "sessions"
    / "2026"
    / "08"
    / "24"
    / "rollout-2026-08-24T00-50-09-01a030d1-2adf-7103-9fcd-1a649215f72e.jsonl"
)
SOURCE_LINES = (571, 577)
FILES = (
    "backend/.bago/api/handlers_jobs.py",
    "backend/.bago/core/config_manager.py",
    "backend/.bago/core/plan_engine.py",
    "backend/.bago/core/session_turn_mixin.py",
    "backend/tests/integrations/pi/test_negatives.py",
    "backend/tests/test_plan_engine_contract.py",
)
SOURCE_LINE_FILES = {
    571: (
        "backend/.bago/api/handlers_jobs.py",
        "backend/.bago/core/plan_engine.py",
        "backend/.bago/core/session_turn_mixin.py",
        "backend/tests/test_plan_engine_contract.py",
    ),
    577: (
        "backend/.bago/core/config_manager.py",
        "backend/tests/integrations/pi/test_negatives.py",
    ),
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _command_output_at(session_log: Path, line_number: int) -> str:
    with session_log.open("r", encoding="utf-8", errors="replace") as stream:
        for current, line in enumerate(stream, 1):
            if current != line_number:
                continue
            payload = json.loads(line).get("payload", {})
            item = payload.get("item", {}) if isinstance(payload, dict) else {}
            if item.get("type") != "CommandExecution":
                raise ValueError(f"line {line_number} is not a CommandExecution")
            output = item.get("stdout") or item.get("aggregated_output") or ""
            if not isinstance(output, str) or "diff --git" not in output:
                raise ValueError(f"line {line_number} has no diff output")
            return output
    raise ValueError(f"line {line_number} not found in {session_log}")


def _diff_chunks(output: str) -> dict[str, str]:
    start = output.find("diff --git")
    if start < 0:
        return {}
    text = output[start:].replace("\r\n", "\n").replace("\r", "\n")
    chunks: dict[str, str] = {}
    for chunk in re.split(r"(?=diff --git )", text):
        if not chunk.startswith("diff --git "):
            continue
        first = chunk.split("\n", 1)[0]
        match = re.match(r"diff --git a/(.*?) b/", first)
        if not match:
            continue
        path = match.group(1)
        if not chunk.endswith("\n"):
            chunk += "\n"
        chunks[path] = chunk
    return chunks


def recover_from_session(session_log: Path) -> bytes:
    if not session_log.is_file():
        raise FileNotFoundError(f"session log missing: {session_log}")
    chunks: dict[str, str] = {}
    for line_number in SOURCE_LINES:
        chunks.update(_diff_chunks(_command_output_at(session_log, line_number)))
    missing = [path for path in FILES if path not in chunks]
    if missing:
        raise ValueError(f"missing recovered diff chunks: {missing}")
    patch_lf = "".join(chunks[path] for path in FILES)
    return patch_lf.replace("\n", "\r\n").encode("utf-8")


def _archive_baseline(destination: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=zip", BASELINE_SHA],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        source.extractall(destination)


def normalized_patch_bytes(patch_bytes: bytes) -> bytes:
    return patch_bytes.replace(b"\r\n", b"\n")


def apply_check(patch_bytes: bytes) -> dict[str, Any]:
    normalized = normalized_patch_bytes(patch_bytes)
    with tempfile.TemporaryDirectory(prefix="bago-dirty-boundary-") as raw:
        root = Path(raw)
        baseline = root / "baseline"
        baseline.mkdir()
        _archive_baseline(baseline)
        patch = root / "dirty-boundary.patch"
        patch.write_bytes(normalized)
        result = subprocess.run(
            ["git", "apply", "--check", str(patch)],
            cwd=baseline,
            capture_output=True,
        )
        stderr = result.stderr.decode("utf-8", "replace")
        return {"ok": result.returncode == 0, "returncode": result.returncode, "stderr": stderr}


def provenance(session_log: Path, patch_bytes: bytes, apply_result: dict[str, Any]) -> dict[str, Any]:
    patch_lf = normalized_patch_bytes(patch_bytes)
    return {
        "contract": "bago.recovered-dirty-boundary.v1",
        "status": "VERIFIED" if apply_result["ok"] else "FAILED",
        "baseline_sha": BASELINE_SHA,
        "recorded_sha256": RECORDED_SHA256,
        "recovered_patch": OUTPUT_PATCH.name,
        "recovered_patch_sha256": sha_bytes(patch_bytes),
        "recovered_patch_size": len(patch_bytes),
        "line_endings": "crlf",
        "normalized_lf_sha256": sha_bytes(patch_lf),
        "normalized_lf_size": len(patch_lf),
        "source_log": str(session_log),
        "source_lines": [
            {"line": line_number, "files": list(SOURCE_LINE_FILES[line_number])}
            for line_number in SOURCE_LINES
        ],
        "files": list(FILES),
        "recovery_method": (
            "Extract diff chunks from recorded CommandExecution stdout, order them by the "
            "original tracked baseline file list, serialize as CRLF, and verify the "
            "recorded SHA-256."
        ),
        "normalized_lf_apply_check": "PASS" if apply_result["ok"] else "FAIL",
        "normalized_lf_apply_stderr": apply_result["stderr"],
        "recovered_at": datetime.now(timezone.utc).isoformat(),
    }


def assert_recovered_patch(patch_bytes: bytes) -> None:
    digest = sha_bytes(patch_bytes)
    if digest != RECORDED_SHA256:
        raise ValueError(f"dirty boundary SHA mismatch: {digest}")
    if len(patch_bytes) != RECORDED_SIZE:
        raise ValueError(f"dirty boundary size mismatch: {len(patch_bytes)}")
    result = apply_check(patch_bytes)
    if not result["ok"]:
        raise ValueError(result["stderr"] or "dirty boundary patch does not apply")


def verify_existing() -> dict[str, Any]:
    patch_bytes = OUTPUT_PATCH.read_bytes()
    assert_recovered_patch(patch_bytes)
    data = json.loads(OUTPUT_PROVENANCE.read_text(encoding="utf-8"))
    if data.get("contract") != "bago.recovered-dirty-boundary.v1":
        raise ValueError("invalid recovered dirty boundary contract")
    if data.get("recorded_sha256") != RECORDED_SHA256:
        raise ValueError("recorded dirty boundary hash mismatch")
    if data.get("recovered_patch_sha256") != RECORDED_SHA256:
        raise ValueError("provenance patch hash mismatch")
    if data.get("status") != "VERIFIED":
        raise ValueError("recovered dirty boundary is not VERIFIED")
    if data.get("line_endings") != "crlf":
        raise ValueError("recovered dirty boundary line-ending identity mismatch")
    normalized = normalized_patch_bytes(patch_bytes)
    if data.get("normalized_lf_sha256") != sha_bytes(normalized):
        raise ValueError("normalized dirty boundary hash mismatch")
    if data.get("normalized_lf_apply_check") != "PASS":
        raise ValueError("normalized dirty boundary apply check missing")
    return {
        "result": "PASS",
        "patch": str(OUTPUT_PATCH),
        "provenance": str(OUTPUT_PROVENANCE),
        "sha256": RECORDED_SHA256,
        "size": RECORDED_SIZE,
    }


def write_recovery(session_log: Path) -> dict[str, Any]:
    patch_bytes = recover_from_session(session_log)
    assert_recovered_patch(patch_bytes)
    apply_result = apply_check(patch_bytes)
    OUTPUT_PATCH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATCH.write_bytes(patch_bytes)
    OUTPUT_PROVENANCE.write_text(
        json.dumps(provenance(session_log, patch_bytes, apply_result), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return verify_existing()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="recover and write the patch/provenance")
    parser.add_argument("--verify-only", action="store_true", help="verify existing artifacts")
    parser.add_argument("--session-log", default=str(DEFAULT_SESSION_LOG))
    args = parser.parse_args()

    try:
        result = write_recovery(Path(args.session_log)) if args.write else verify_existing()
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
