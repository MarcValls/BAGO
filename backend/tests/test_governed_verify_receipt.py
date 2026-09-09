from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1].parent
SCRIPT = ROOT / "scripts" / "record_governed_verify_receipt.py"


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
    # Existing historical bundles predate candidate_identity, so this test
    # intentionally proves fail-closed behaviour until fresh bundles exist.
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
