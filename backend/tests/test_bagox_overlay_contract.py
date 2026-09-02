from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_bagox_overlay.py"
SPEC = importlib.util.spec_from_file_location("verify_bagox_overlay", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text(
        "BAGOx Behavior Package v1.3-RC1-FIX2\n"
        "Resolve the canonical product version from `release_version.txt`.\n",
        encoding="utf-8",
    )
    (repo / "release_version.txt").write_text("4.9.1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=BAGO", "-c", "user.email=bago@example.test", "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()

    package = tmp_path / "package"
    package.mkdir()
    fragment = package / "codex"
    fragment.mkdir()
    fragment_file = fragment / "AGENTS_BAGOX_FRAGMENT.md"
    fragment_file.write_text("fragment\n", encoding="utf-8")
    manifest = package / "MANIFEST.sha256"
    manifest.write_text(f"{_sha256(fragment_file)}  ./codex/AGENTS_BAGOX_FRAGMENT.md\n", encoding="utf-8")
    agents = repo / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8") + f"`{_sha256(manifest)}`\n", encoding="utf-8")

    state = tmp_path / "PROJECT_STATE.json"
    state.write_text(
        json.dumps(
            {
                "commit": head,
                "fingerprint": {"commit": head},
                "last_verification": {"commit": head},
            }
        ),
        encoding="utf-8",
    )
    handoff = tmp_path / "ACTIVE_HANDOFF.md"
    handoff.write_text(f"Candidate: {head}\n", encoding="utf-8")
    return repo, package, state, handoff


def test_overlay_contract_accepts_one_current_candidate(tmp_path: Path):
    repo, package, state, handoff = _fixture_repo(tmp_path)
    assert MODULE.verify(repo, package, state, handoff) == []


def test_overlay_contract_rejects_mixed_candidate_identity(tmp_path: Path):
    repo, package, state, handoff = _fixture_repo(tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["candidate_sha"] = "0" * 40
    state.write_text(json.dumps(payload), encoding="utf-8")
    errors = MODULE.verify(repo, package, state, handoff)
    assert "state candidate_sha conflicts with current HEAD" in errors


def test_overlay_contract_requires_receipt_only_after_bootstrap(tmp_path: Path):
    repo, package, state, handoff = _fixture_repo(tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))
    del payload["last_verification"]
    state.write_text(json.dumps(payload), encoding="utf-8")
    assert MODULE.verify(repo, package, state, handoff) == []
    assert MODULE.verify(repo, package, state, handoff, require_verification=True) == [
        "state has no current verification receipt"
    ]
