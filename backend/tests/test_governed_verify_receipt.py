from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(ROOT / "backend"))
from bago_core.candidate_identity import fingerprint  # noqa: E402

SCRIPT = ROOT / "scripts" / "record_governed_verify_receipt.py"


def _make_clean_git_repo(base: Path) -> Path:
    repo = base / "clean-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "codex/objetivos01"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    (repo / "README.md").write_text("clean candidate\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def _make_valid_provider_bundle(tmp_path: Path, provider: str, source: Path, repo: Path) -> Path:
    bundle = tmp_path / provider
    shutil.copytree(source, bundle)
    identity = fingerprint(repo)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["details"]["provider"] = provider
    manifest["details"]["candidate_identity"] = {
        "repo_root": str(repo),
        "git_head": str(identity["sha"]),
        "git_branch": str(identity["branch"]),
        "git_dirty": False,
        "worktree_fingerprint": str(identity["worktree_sha256"]),
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = []
    for path in sorted(bundle.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            lines.append(f"{__import__('hashlib').sha256(path.read_bytes()).hexdigest()}  {path.relative_to(bundle).as_posix()}")
    (bundle / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return bundle


def test_governed_receipt_records_both_provider_checks_and_candidate_identity(tmp_path: Path) -> None:
    codex = ROOT / "output" / "evidence-real-codex-after-reset-20260909"
    copilot = ROOT / "output" / "evidence-real-copilot-bound-final-20260909"
    if not (codex / "manifest.json").is_file() or not (copilot / "manifest.json").is_file():
        return
    output = tmp_path / "receipt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--codex-bundle", str(codex), "--copilot-bundle", str(copilot), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode in (0, 2)
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "bago.verify.run.v1"
    assert set(receipt["identity"]) == {"start", "end"}
    assert {item["check_id"] for item in receipt["checks"]} == {
        "provider-codex-candidate-bound", "provider-copilot-candidate-bound"
    }
    assert len(receipt["identity"]["start"]["git_head"]) == 40
    assert len(receipt["identity"]["start"]["worktree_fingerprint"]) == 64
    assert (output / "SHA256SUMS").is_file()


def test_governed_receipt_accepts_alternative_provider_bundle(tmp_path: Path) -> None:
    source = ROOT / "output" / "evidence-real-copilot-governed-20260910-candidate-75273b45"
    if not source.is_dir():
        return
    repo = _make_clean_git_repo(tmp_path)
    bundle = _make_valid_provider_bundle(tmp_path, "ollama-cloud", source, repo)
    output = tmp_path / "receipt-alt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--provider-bundle", f"ollama-cloud={bundle}", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["summary"]["verdict"] == "VERIFIED"
    assert {item["check_id"] for item in receipt["checks"]} == {"provider-ollama-cloud-candidate-bound"}
