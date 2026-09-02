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


def test_candidate_bound_pass_maps_to_preverified() -> None:
    result = _invoke_verdict(
        "PASS\n"
        "Evidence summary\n"
        f"BAGO_CANDIDATE_SHA: {CANDIDATE}\n"
        "BAGO_VERDICT: PREVERIFIED\n"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("PREVERIFIED")


@pytest.mark.parametrize(
    "report",
    [
        f"Evidence summary\nBAGO_CANDIDATE_SHA: {CANDIDATE}\nBAGO_VERDICT: PREVERIFIED\n",
        f"PASS\nBAGO_CANDIDATE_SHA: {CANDIDATE}\nThis candidate is NOT PREVERIFIED\n",
        f"PASS\nBAGO_CANDIDATE_SHA: {CANDIDATE}\nBAGO_VERDICT: VERIFIED\n",
        (
            "PASS\n"
            f"BAGO_CANDIDATE_SHA: {CANDIDATE}\n"
            "BAGO_VERDICT: PREVERIFIED\n"
            "BAGO_VERDICT: BLOCKED\n"
        ),
        f"PASS\nBAGO_CANDIDATE_SHA: {CANDIDATE}\nBAGO_VERDICT: BLOCKED\n",
        f"FAIL\nBAGO_CANDIDATE_SHA: {CANDIDATE}\nBAGO_VERDICT: PREVERIFIED\n",
    ],
)
def test_ambiguous_or_inconsistent_verdicts_fail_closed(report: str) -> None:
    result = _invoke_verdict(report)
    assert result.returncode != 0


def test_candidate_sha_mismatch_fails_closed() -> None:
    result = _invoke_verdict(
        f"PASS\nBAGO_CANDIDATE_SHA: {'b' * 40}\nBAGO_VERDICT: PREVERIFIED\n"
    )
    assert result.returncode != 0


@pytest.mark.parametrize(
    ("task_verdict", "machine_verdict", "expected"),
    [
        ("BLOCKED", "BLOCKED", "BLOCKED"),
        ("FAIL", "FAILED", "FAILED"),
    ],
)
def test_nonpass_workpack_verdicts_are_machine_readable(
    task_verdict: str, machine_verdict: str, expected: str
) -> None:
    result = _invoke_verdict(
        f"{task_verdict}\n"
        f"BAGO_CANDIDATE_SHA: {CANDIDATE}\n"
        f"BAGO_VERDICT: {machine_verdict}\n"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith(expected)


def test_supervisor_contains_required_authority_and_remote_gates() -> None:
    text = SUPERVISOR.read_text(encoding="utf-8")

    required_fragments = [
        'ExpectedRepository = "MarcValls/BAGO"',
        'Unknown StartAt',
        'first non-empty line must be exactly PASS, FAIL, or BLOCKED',
        'BAGO_VERDICT: PREVERIFIED',
        'Get-BagoPreverificationVerdict',
        'candidate HEAD changed during read-only verification',
        'PR head moved after preverification',
        'gh pr checks',
        '--match-head-commit $candidateSha',
        'Wait-ForConfirmedMerge',
        '$view.state -eq "MERGED"',
        'GitHub confirmed MERGED',
        'Evidence/worktree is preserved',
        'NoMerge stops after VERIFIED front',
        '$safeRunId',
    ]
    for fragment in required_fragments:
        assert fragment in text

    # Avoid a partial-success hazard: branch deletion must not be fused into
    # the merge command, because a cleanup failure could obscure a successful
    # remote merge.
    assert "--squash --delete-branch" not in text
