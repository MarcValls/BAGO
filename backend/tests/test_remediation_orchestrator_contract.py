from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / ".codex" / "bago-remediation" / "VerificationVerdict.psm1"
SUPERVISOR = REPO_ROOT / ".codex" / "bago-remediation" / "Run-Remediation.ps1"
PLAN = REPO_ROOT / ".codex" / "bago-remediation" / "remediation-plan.json"
WORKPACK_MANIFEST = REPO_ROOT / ".codex" / "bago-workpack" / "manifest.json"
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


def test_candidate_bound_pass_maps_to_preverified_case_insensitively() -> None:
    result = _invoke_verdict(
        "PASS\n"
        "Evidence summary\n"
        f"BAGO_CANDIDATE_SHA: {CANDIDATE.upper()}\n"
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


def test_plan_declares_non_relaxable_safety_policy_and_15_fronts() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    policy = plan["execution_policy"]
    assert plan["schema_version"] == "1.1"
    assert policy["mode"] == "sequential_dependency_safe"
    assert policy["implementation_task"] == "20-implement-approved-pr"
    assert policy["verification_task"] == "22-verify-change"
    assert policy["close_only_on_verified"] is True
    assert policy["auto_merge_only_after_ci"] is True
    assert policy["self_certification_forbidden"] is True
    assert policy["failure_policy"] == "stop_and_block"
    assert policy["evidence_required"] is True
    assert policy["required_pr_workflows"] == [
        "Canonical CI",
        "Validate Expected",
        "njsscan sarif",
    ]
    assert [front["id"] for front in plan["fronts"]] == [f"F{i:02d}" for i in range(1, 16)]
    assert all(front["priority"] in {"P0", "P1", "P2", "P3"} for front in plan["fronts"])
    assert all(front["acceptance"] and all(front["acceptance"]) for front in plan["fronts"])


def test_plan_selected_workpack_roles_preserve_separation_of_duties() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    manifest = json.loads(WORKPACK_MANIFEST.read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in manifest["tasks"]}
    implementation = tasks[plan["execution_policy"]["implementation_task"]]
    verification = tasks[plan["execution_policy"]["verification_task"]]

    assert implementation["sandbox"] == "workspace-write"
    assert implementation["agent"].startswith("bago_")
    assert implementation["agent"].endswith("_worker")
    assert implementation["requires_extra"] is True
    assert verification["sandbox"] == "read-only"
    assert verification["agent"] == "bago_final_verifier"
    assert verification["requires_extra"] is True
    assert implementation["id"] != verification["id"]


def test_supervisor_contains_required_authority_and_remote_gates() -> None:
    text = SUPERVISOR.read_text(encoding="utf-8")

    required_fragments = [
        'ExpectedRepository = "MarcValls/BAGO"',
        'ExpectedPlanSchema = "1.1"',
        'WorkpackManifestPath',
        'Assert-PlanContract',
        'Assert-WorkpackTaskContract',
        'Plan must keep self_certification_forbidden=true',
        'Verification task \'$VerificationTaskId\' must use read-only sandbox',
        'Verification task \'$VerificationTaskId\' must use bago_final_verifier',
        '$implementationTask = [string]$Plan.execution_policy.implementation_task',
        '$verificationTask = [string]$Plan.execution_policy.verification_task',
        '$implementationRunId = "$safeRunId-$($front.id)-impl"',
        '$verificationRunId = "$safeRunId-$($front.id)-verify"',
        '("reports\\$verificationRunId\\" + $verificationTask + ".md")',
        'run_id_safe = $safeRunId',
        'bago-remediation-runs\\run-',
        'RunId resolves to an unsafe physical path segment',
        'maximum physical length is 64 characters',
        'Unknown StartAt',
        'required_pr_workflows',
        'Wait-ForRequiredWorkflowRuns',
        'gh run list --repo $ExpectedRepository --commit $CandidateSha --event pull_request',
        "Required PR workflow '$required' concluded",
        'function Wait-ForCompletePrChecks',
        'if ($checksExit -eq 0) { return }',
        'if ($checksExit -ne 8) { throw "PR checks failed for pr=$PrNumber (gh pr checks exit code $checksExit)" }',
        'Wait-ForCompletePrChecks -PrNumber $prNumber',
        r'^(?:https://|ssh://git@|git@)?github\.com[:/]MarcValls/BAGO(?:\.git)?/?$',
        'first non-empty line must be exactly PASS, FAIL, or BLOCKED',
        'BAGO_VERDICT: PREVERIFIED',
        'Get-BagoPreverificationVerdict',
        'candidate HEAD changed during read-only verification',
        'PR head moved after preverification',
        '--match-head-commit $candidateSha',
        'Wait-ForConfirmedMerge',
        '$view.state -eq "MERGED"',
        'PR base branch moved: expected $($Plan.base_branch) got $($prView.baseRefName)',
        'PR base branch moved while awaiting merge confirmation: expected $ExpectedBaseBranch got $($view.baseRefName)',
        '-ExpectedBaseBranch $Plan.base_branch',
        'GitHub confirmed MERGED',
        'Evidence/worktree is preserved',
        'NoMerge stops after VERIFIED front',
        '$safeRunId',
    ]
    for fragment in required_fragments:
        assert fragment in text

    # The task IDs are plan authority, not supervisor constants.
    assert '-Task "20-implement-approved-pr"' not in text
    assert '-Task "22-verify-change"' not in text
    assert "22-verify-change.md" not in text

    # Raw RunId must not reach the workpack or report filesystem paths.
    assert '-RunId "$RunId-' not in text
    assert 'reports\\$RunId-' not in text

    # Avoid a known registration race: the supervisor must not immediately
    # enter gh-pr-checks watch mode before GitHub has registered the required
    # workflow runs for the exact candidate SHA.
    assert "gh pr checks $prNumber --repo $ExpectedRepository --watch" not in text

    # The origin check must be anchored (no leading `^`) so a lookalike host
    # such as "evilgithub.com" cannot satisfy it merely by containing
    # "github.com" as a substring further into the URL.
    assert "if ($originUrl -notmatch '(?i)github\\.com[:/]MarcValls/BAGO(?:\\.git)?$')" not in text


    # Avoid a partial-success hazard: branch deletion must not be fused into
    # the merge command, because a cleanup failure could obscure a successful
    # remote merge.
    assert "--squash --delete-branch" not in text
