from __future__ import annotations

import hashlib
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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_bundle_manifest_and_checksums(bundle: Path, provider: str, repo: Path) -> None:
    identity = fingerprint(repo)
    files = []
    for item in sorted(bundle.rglob("*")):
        if item.is_file() and item.name not in {"manifest.json", "checksums.sha256"}:
            files.append({
                "path": item.relative_to(bundle).as_posix(),
                "sha256": _digest(item),
                "size_bytes": item.stat().st_size,
            })
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({
        "status": "pass",
        "checks": [{"id": "provider-response", "status": "pass", "detail": "ok"}],
        "files": files,
    })
    manifest.setdefault("details", {})["provider"] = provider
    manifest["details"]["candidate_identity"] = {
        "repo_root": str(repo),
        "git_head": str(identity["sha"]),
        "git_branch": str(identity["branch"]),
        "git_dirty": False,
        "worktree_fingerprint": str(identity["worktree_sha256"]),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checksum_files = [*files, {
        "path": "manifest.json",
        "sha256": _digest(manifest_path),
    }]
    lines = [f"{entry['sha256']}  {entry['path']}" for entry in checksum_files]
    (bundle / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_minimal_provider_bundle(tmp_path: Path, provider: str, repo: Path) -> Path:
    bundle = tmp_path / provider
    bundle.mkdir()
    (bundle / "artifact.txt").write_text(f"{provider} evidence\n", encoding="utf-8")
    (bundle / "manifest.json").write_text("{}", encoding="utf-8")
    _rewrite_bundle_manifest_and_checksums(bundle, provider, repo)
    return bundle


def _make_valid_provider_bundle(tmp_path: Path, provider: str, source: Path, repo: Path) -> Path:
    bundle = tmp_path / provider
    shutil.copytree(source, bundle)
    _rewrite_bundle_manifest_and_checksums(bundle, provider, repo)
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


def test_governed_receipt_rejects_empty_manifest_checks(tmp_path: Path) -> None:
    repo = _make_clean_git_repo(tmp_path)
    bundle = _make_minimal_provider_bundle(tmp_path, "codex", repo)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checks"] = []
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [
        f"{_digest(bundle / 'artifact.txt')}  artifact.txt",
        f"{_digest(manifest_path)}  manifest.json",
    ]
    (bundle / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    output = tmp_path / "receipt-empty-checks"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--provider-bundle", f"codex={bundle}", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["summary"]["verdict"] == "INCOMPLETE"
    assert "el manifest debe declarar checks no vacíos" in receipt["checks"][0]["reason"]


def test_governed_receipt_rejects_manifest_inventory_without_checksum(tmp_path: Path) -> None:
    repo = _make_clean_git_repo(tmp_path)
    bundle = _make_minimal_provider_bundle(tmp_path, "codex", repo)
    (bundle / "artifact.txt").unlink()
    checksums = (bundle / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    (bundle / "checksums.sha256").write_text(
        "\n".join(line for line in checksums if "artifact.txt" not in line) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "receipt-missing-artifact"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--provider-bundle", f"codex={bundle}", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["summary"]["verdict"] == "INCOMPLETE"
    assert "faltan checksums declarados: artifact.txt" in receipt["checks"][0]["reason"]


def test_governed_receipt_rejects_unignored_output_inside_repo(tmp_path: Path) -> None:
    repo = _make_clean_git_repo(tmp_path)
    bundle = _make_minimal_provider_bundle(tmp_path, "codex", repo)
    output = repo / "governance-receipt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--provider-bundle", f"codex={bundle}", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "--output dentro del repositorio" in result.stderr
    assert not (output / "receipt.json").exists()


def test_governed_receipt_sha256sums_paths_are_resolvable_and_unique(tmp_path: Path) -> None:
    repo = _make_clean_git_repo(tmp_path)
    codex = _make_minimal_provider_bundle(tmp_path, "codex", repo)
    copilot = _make_minimal_provider_bundle(tmp_path, "copilot", repo)
    output = tmp_path / "receipt-resolvable"
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--repo", str(repo),
            "--provider-bundle", f"codex={codex}",
            "--provider-bundle", f"copilot={copilot}",
            "--output", str(output),
        ],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    seen = set()
    for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(None, 1)
        assert relative not in seen
        seen.add(relative)
        target = output / relative
        assert target.is_file(), relative
        assert _digest(target) == expected
    assert "providers/codex/manifest.json" in seen
    assert "providers/copilot/manifest.json" in seen
