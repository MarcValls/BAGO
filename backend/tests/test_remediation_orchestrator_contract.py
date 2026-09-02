from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / ".codex" / "bago-remediation" / "VerificationVerdict.psm1"
SUPERVISOR = REPO_ROOT / ".codex" / "bago-remediation" / "Run-Remediation.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
CANDIDATE = "a" * 40


def _invoke_verdict(report: str, expected_sha: str = CANDIDATE) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        pytest.skip("PowerShell is required for the remediation supervisor contract test")

    env = os.environ.copy()
    env["BAGO_TEST_REPORT"] = report
    env["BAGO_TEST_SHA"] = expected_sha
    module = str(MODULE).replace("'", "''")
    command = (
        f"Import-Module '{module}' -Force; "
        "$v = Get-BagoPreverificationVerdict "
        "-ReportText $env:BAGO_TEST_REPORT -ExpectedCandidateSha $env:BAGO_TEST_SHA; "
        "Write-Output $v"
    )
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_candidate_bound_preverified_machine_contract_accepts_exact_report() -> None:
    result = _invoke_verdict(
        "Evidence summary\n"
        f"BAGO_CANDIDATE_SHA: {CANDIDATE}\n"
        "BAGO_VERDICT: PREVERIFIED\n"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("PREVERIFIED")


@pytest.mark.parametrize(
    "report",
    [
        f"BAGO_CANDIDATE_SHA: {CANDIDATE}\nThis candidate is NOT PREVERIFIED\n",
        f"BAGO_CANDIDATE_SHA: {CANDIDATE}\nBAGO_VERDICT: VERIFIED\n",
        (
            f"BAGO_CANDIDATE_SHA: {CANDIDATE}\n"
            "BAGO_VERDICT: PREVERIFIED\n"
            "BAGO_VERDICT: BLOCKED\n"
        ),
    ],
)
def test_ambiguous_or_noncontract_verdicts_fail_closed(report: str) -> None:
    result = _invoke_verdict(report)
    assert result.returncode != 0


def test_candidate_sha_mismatch_fails_closed() -> None:
    result = _invoke_verdict(
        f"BAGO_CANDIDATE_SHA: {'b' * 40}\nBAGO_VERDICT: PREVERIFIED\n"
    )
    assert result.returncode != 0


def test_blocked_verdict_is_machine_readable_but_not_preverified() -> None:
    result = _invoke_verdict(
        f"BAGO_CANDIDATE_SHA: {CANDIDATE}\nBAGO_VERDICT: BLOCKED\n"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("BLOCKED")


def test_supervisor_contains_required_authority_and_remote_gates() -> None:
    text = SUPERVISOR.read_text(encoding="utf-8")

    required_fragments = [
        'ExpectedRepository = "MarcValls/BAGO"',
        'Unknown StartAt',
        'BAGO_VERDICT: PREVERIFIED|BLOCKED|FAILED',
        'Get-BagoPreverificationVerdict',
        'candidate HEAD changed during read-only verification',
        'PR head moved after preverification',
        'gh pr checks',
        'Wait-ForConfirmedMerge',
        '$view.state -eq "MERGED"',
        'GitHub confirmed MERGED',
        'Evidence/worktree is preserved',
        '$safeRunId',
    ]
    for fragment in required_fragments:
        assert fragment in text

    # Avoid a known partial-success hazard: merge and local branch deletion must
    # not be fused into one gh command whose cleanup failure could obscure a
    # successful remote merge.
    assert "gh pr merge $prNumber --repo $ExpectedRepository --squash --delete-branch" not in text
