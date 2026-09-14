"""Regression coverage for separate BAGO and gestor audit candidates."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "package_remediation_audit.py"
SPEC = importlib.util.spec_from_file_location("package_remediation_audit", MODULE_PATH)
assert SPEC and SPEC.loader
PACKAGE_AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE_AUDIT
SPEC.loader.exec_module(PACKAGE_AUDIT)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _repository(repo: Path, initial: str, changed: str) -> tuple[str, str]:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@bago.local")
    _git(repo, "config", "user.name", "BAGO tests")
    tracked = repo / "tracked.txt"
    tracked.write_text(initial, encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    baseline = _git(repo, "rev-parse", "HEAD")
    tracked.write_text(changed, encoding="utf-8")
    _git(repo, "commit", "-am", "candidate")
    return baseline, _git(repo, "rev-parse", "HEAD")


def test_omitted_gestor_candidate_uses_its_own_head_for_distinct_bago_sha(tmp_path: Path, monkeypatch) -> None:
    bago = tmp_path / "bago"
    bago_baseline, bago_sha = _repository(bago, "bago baseline\n", "bago candidate\n")
    gestor = tmp_path / "gestor"
    gestor_baseline, gestor_sha = _repository(gestor, "gestor baseline\n", "gestor candidate\n")

    handoff = bago / ".bago" / "audits" / "remediation-handoff-20260824.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text("test handoff\n", encoding="utf-8")
    _git(bago, "add", ".bago/audits/remediation-handoff-20260824.md")
    _git(bago, "commit", "-m", "add audit handoff")
    bago_sha = _git(bago, "rev-parse", "HEAD")
    assert bago_sha != gestor_sha
    monkeypatch.setattr(PACKAGE_AUDIT, "ROOT", bago)
    monkeypatch.setattr(
        PACKAGE_AUDIT,
        "ingest_recovered_dirty_boundary",
        lambda _destination, _baseline: {"recovered_patch_sha256": "a" * 64, "normalized_lf_sha256": "b" * 64},
    )

    package = tmp_path / "audit.zip"
    PACKAGE_AUDIT.build(
        package,
        gestor,
        None,
        bago_baseline,
        gestor_baseline,
        bago_sha,
        None,
        None,
    )

    with zipfile.ZipFile(package) as archive:
        contract = json.loads(archive.read("audit/bundle-contract.json"))
        gestor_provenance = json.loads(archive.read("audit/gestor-provenance.json"))
    assert contract["repository_candidates"] == {"bago": bago_sha, "gestor": gestor_sha}
    assert gestor_provenance["candidate_sha"] == gestor_sha
