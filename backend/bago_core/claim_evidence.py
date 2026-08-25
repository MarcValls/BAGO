"""Derive and validate candidate-bound gate evidence for claim verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from bago_core.candidate_identity import candidate_from_repo, fingerprint, git
from bago_core.operational_integrity import CandidateIdentity, EvidenceRecord


def derive_candidate(repo: Path) -> CandidateIdentity:
    return candidate_from_repo(repo)


def matches_expected(candidate: CandidateIdentity, args: argparse.Namespace) -> bool:
    return bool(
        candidate.sha == args.sha and candidate.branch == args.branch and candidate.remote == args.remote
        and candidate.upstream == args.upstream
        and (not args.worktree_sha256 or candidate.worktree_sha256 == args.worktree_sha256)
    )


def evidence_from_gate(repo: Path, claim: Any, receipt_path: Path) -> EvidenceRecord:
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    allowed = (root / ".bago" / "evidence" / "remediation-gates").resolve()
    receipt = receipt_path.resolve()
    if allowed not in receipt.parents or not receipt.is_file():
        raise ValueError("el recibo debe proceder de .bago/evidence/remediation-gates")
    raw_bytes = receipt.read_bytes()
    payload = json.loads(raw_bytes)
    if payload.get("contract") != "bago.gate-evidence.v1":
        raise ValueError("contrato de gate desconocido")
    if payload.get("exit_code") != 0:
        raise ValueError("el gate no terminó correctamente sobre un candidato estable")
    try:
        started = datetime.fromisoformat(str(payload["started_at"]).replace("Z", "+00:00"))
        finished = datetime.fromisoformat(str(payload["finished_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("timestamps del gate ausentes o inválidos") from exc
    if started.tzinfo is None or finished.tzinfo is None or finished < started:
        raise ValueError("intervalo temporal del gate inválido")
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict) or not all(runtime.get(key) for key in ("python", "python_executable", "platform")):
        raise ValueError("runtime del gate incompleto")
    command = tuple(str(value) for value in payload.get("command", ()))
    if claim.command not in {shlex.join(command), " ".join(command)}:
        raise ValueError("el comando del gate no coincide con el claim")
    def read_candidate(raw: Any) -> CandidateIdentity:
        if not isinstance(raw, dict):
            raise ValueError("identidad de candidato ausente")
        return CandidateIdentity(
            str(raw.get("sha", "")), str(raw.get("branch", "")),
            str(raw.get("remote") or f"local-only:{root}"), str(raw.get("upstream", "")),
            bool(raw.get("dirty")), str(raw.get("worktree_sha256", "")),
        )
    current = derive_candidate(root)
    before = read_candidate(payload.get("candidate_before"))
    candidate = read_candidate(payload.get("candidate_after"))
    repositories_before = payload.get("candidate_repositories_before")
    repositories_after = payload.get("candidate_repositories_after")
    stable = isinstance(repositories_before, dict) and repositories_before == repositories_after
    if payload.get("candidate_stable") is not True or not stable or before != candidate:
        raise ValueError("el gate no demuestra estabilidad del candidato")
    if before != current or candidate != current:
        raise ValueError("el candidato del gate no coincide con Git actual")
    for repository_path, recorded_repository in repositories_after.items():
        if not isinstance(recorded_repository, dict) or fingerprint(Path(repository_path)) != recorded_repository:
            raise ValueError(f"el repositorio ligado al gate ha cambiado: {repository_path}")
    expected = {
        str((receipt.parent / str(payload.get("stdout", ""))).resolve()): str(payload.get("stdout_sha256", "")),
        str((receipt.parent / str(payload.get("stderr", ""))).resolve()): str(payload.get("stderr_sha256", "")),
    }
    hashes: list[str] = []
    for artifact in claim.artifacts:
        resolved = str(Path(artifact).resolve())
        if resolved not in expected:
            raise ValueError("los artefactos del claim no están ligados al recibo")
        hashes.append(expected[resolved])
    return EvidenceRecord(
        claim=claim.claim, action=claim.command, artifacts=tuple(claim.artifacts), command=command,
        exit_code=0, timestamp=str(payload.get("finished_at", "")), candidate=candidate,
        artifact_sha256=tuple(hashes), receipt_id=hashlib.sha256(raw_bytes).hexdigest(), gate_receipt=str(receipt),
    )
